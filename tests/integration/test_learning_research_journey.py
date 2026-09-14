"""Real Bootstrap -> controller -> approved mission -> durable cited report."""

import json
import os
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock, patch

from brain.Brain import Brain
from brain.BrainRequest import BrainRequest
from cognition.CognitiveEngine import CognitiveEngine
from core.Bootstrap import Bootstrap
from core.CancellationSignal import CancellationSignal
from core.Exceptions import ResearchError
from core.ExclusiveStoreOwnership import release_all
from desktop.DesktopController import DesktopController
from llm.LLMRuntimeConfig import LLMRuntimeConfig
from research.JsonFileFailureLessonStore import JsonFileFailureLessonStore
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchCapabilityCost import cost_for
from research.ResearchDisclosure import ResearchDisclosure
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchExecutionAllowance import ResearchExecutionAllowance
from research.ResearchExecutionSpend import ResearchExecutionSpend
from research.ResearchMissionFollowupDecision import (
    ResearchMissionFollowupDecisionStatus,
)
from research.ResearchPlanDigest import plan_digest
from research.ResearchPlanStepCapability import ResearchPlanStepCapability as Cap
from research.ResearchSource import ResearchSource
from research.ResearchSourceCandidate import ResearchSourceCandidate
from research.SemanticMissionPolicy import SemanticMissionPolicy


class LearningResearchJourneyTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(
            patch.dict(
                os.environ,
                {
                    "HYPATIA_PLAN_AUTHORIZATION_ENABLED": "true",
                    "HYPATIA_RESEARCH_EXECUTION_PERSISTENCE_ENABLED": "true",
                    "HYPATIA_FAILURE_MEMORY_ENABLED": "true",
                },
                clear=True,
            )
        )
        self.addCleanup(release_all)
        self.question = "Which prompt injection defenses are effective?"
        self.provider = Mock(provider_name="fixture")
        self.sources = [
            ResearchSource(
                url=f"https://reference{i}.example/study",
                title=f"Prompt injection defenses {i}",
                content=f"Prompt injection defenses are {'not ' if i == 1 else ''}"
                f"effective in study {i}. Conditions differ in population {i}. "
                "Treat retrieved material as untrusted data.",
                content_type="text/plain",
                fetched_at=datetime.now(UTC),
            )
            for i in range(3)
        ]
        self.provider.discover.return_value = [
            ResearchSourceCandidate(s.url, s.title, "Research study")
            for s in self.sources
        ]
        self.fetcher = Mock()
        self.fetcher.fetch.side_effect = lambda url: next(
            s for s in self.sources if s.url == url
        )
        self.relation = "possible_conflict"
        self.relations = None
        self.transport = Mock(side_effect=self.answer)
        self.policy = SemanticMissionPolicy(
            "http://127.0.0.1:11434/v1/chat/completions",
            "test-model",
            ResearchDisclosure.LOCAL_ONLY,
        )
        self.budget = ResearchAutonomyBudget(
            max_step_advances=18, max_network_operations=9, max_llm_operations=2
        )
        self.bootstrap = Bootstrap(
            memory_path=self.root / "memory.json",
            session_path=self.root / "sessions.json",
            knowledge_relation_path=self.root / "relations.json",
            research_run_path=self.root / "runs.json",
            llm_config=LLMRuntimeConfig(True, self.policy.endpoint, self.policy.model),
            llm_provider=Mock(),
            semantic_comparison_transport=self.transport,
            research_source_fetcher=self.fetcher,
            research_source_discovery_provider=self.provider,
            research_source_discovery_providers={
                ResearchDiscoveryProviderName.CROSSREF: self.provider
            },
        )
        self.bootstrap.initialize()
        self.engine = self.bootstrap.container.resolve(CognitiveEngine)
        self.controller = DesktopController(self.bootstrap.container.resolve(Brain))
        self.execution = self.engine._research_plan_execution_service
        self.approvals = self.engine._plan_authorization_service

    def answer(self, endpoint, headers, payload):
        self.assertEqual(endpoint, self.policy.endpoint)
        self.assertEqual(payload["model"], self.policy.model)
        data = json.loads(
            payload["messages"][-1]["content"].split("UNTRUSTED_DATA\n", 1)[1]
        )
        self.assertEqual(data["question"], self.question)
        snapshots = self.execution._execution_store.load()
        snapshot = snapshots[-1]
        self.assertEqual(
            snapshot.allowance.spend.llm_operations, self.transport.call_count
        )
        self.assertTrue(any(s.status.value == "running" for s in snapshot.steps))
        relation = (
            self.relations.pop(0) if self.relations is not None else self.relation
        )
        body = {
            "comparisons": [
                {
                    "relation": relation,
                    "left_quote": data["evidence"][0]["excerpt"][:60],
                    "right_quote": data["evidence"][1]["excerpt"][:60],
                    "rationale": "Conditions may differ; investigate first.",
                }
            ]
        }
        return {"choices": [{"message": {"content": json.dumps(body)}}]}

    def start(self, **kwargs):
        request_id = kwargs.pop("request_id", None)
        if request_id is not None:
            return self.engine.process(
                BrainRequest(
                    message=self.question,
                    source="integration",
                    request_id=request_id,
                    metadata={
                        "intent": "research_goal_start",
                        "research_goal_scope": "bounded_semantic_learning_research",
                        "discovery_provider": "crossref",
                        "research_autonomy_budget": self.budget,
                        "semantic_mission_policy": kwargs.pop("policy", self.policy),
                    },
                )
            )
        return self.controller.start_learning_research(
            self.question,
            "crossref",
            self.budget,
            kwargs.pop("policy", self.policy),
            **kwargs,
        )

    def restart(self, *, endpoint=None, model=None):
        release_all()
        restarted = Bootstrap(
            memory_path=self.root / "memory.json",
            session_path=self.root / "sessions.json",
            knowledge_relation_path=self.root / "relations.json",
            research_run_path=self.root / "runs.json",
            llm_config=LLMRuntimeConfig(
                True,
                self.policy.endpoint if endpoint is None else endpoint,
                self.policy.model if model is None else model,
            ),
            llm_provider=Mock(),
            semantic_comparison_transport=self.transport,
            research_source_fetcher=self.fetcher,
            research_source_discovery_provider=self.provider,
            research_source_discovery_providers={
                ResearchDiscoveryProviderName.CROSSREF: self.provider
            },
        )
        restarted.initialize()
        return restarted.container.resolve(CognitiveEngine)

    def test_restart_reports_destination_mismatch_without_replaying_work(self):
        """A changed model destination remains visible and fail-closed."""
        real_advance = self.execution.process_advance

        def interrupt_after_first_assessment(request):
            state = self.execution.live_execution(request.metadata["research_plan_id"])
            if state is not None and state.completed_steps == 6:
                raise RuntimeError("simulated process interruption")
            return real_advance(request)

        with patch.object(
            self.execution,
            "process_advance",
            side_effect=interrupt_after_first_assessment,
        ):
            with self.assertRaisesRegex(RuntimeError, "simulated process interruption"):
                self.start()

        snapshot = self.execution._execution_store.load()[0]
        engine = self.restart(endpoint="http://127.0.0.1:11434/v1/other")
        execution = engine._research_plan_execution_service

        self.assertIsNone(execution.live_execution(snapshot.plan_id))
        status = execution.process_status(
            BrainRequest(
                message="status",
                metadata={
                    "intent": "research_plan_execution_status",
                    "research_plan_id": snapshot.plan_id,
                },
            )
        )
        self.assertIn("Configured model destination differs", status.message)
        self.assertIn("no source or model call was replayed", status.message)
        self.assertEqual(self.provider.discover.call_count, 1)
        self.assertEqual(self.fetcher.fetch.call_count, 1)
        self.transport.assert_not_called()

    def test_restart_refuses_the_same_durably_started_mission_request(self):
        """A stored mission request key prevents a restart replay, not a new call."""
        request_id = "durable-mission-request-1"
        initial = self.start(request_id=request_id)
        self.assertTrue(initial.success, initial.message)
        snapshot = self.execution._execution_store.load()[0]
        self.assertEqual(snapshot.mission_request_id, request_id)
        calls = (
            self.provider.discover.call_count,
            self.fetcher.fetch.call_count,
            self.transport.call_count,
        )

        engine = self.restart()
        replay = engine.process(
            BrainRequest(
                message=self.question,
                source="integration",
                request_id=request_id,
                metadata={
                    "intent": "research_goal_start",
                    "research_goal_scope": "bounded_semantic_learning_research",
                    "discovery_provider": "crossref",
                    "research_autonomy_budget": self.budget,
                    "semantic_mission_policy": self.policy,
                },
            )
        )

        self.assertFalse(replay.success)
        self.assertIn("Duplicate goal request", replay.message)
        self.assertEqual(
            (
                self.provider.discover.call_count,
                self.fetcher.fetch.call_count,
                self.transport.call_count,
            ),
            calls,
        )

    def test_snapshot_write_failure_starts_no_mission_or_duplicate_guard(self):
        """A mission is not started or keyed until its first snapshot lands."""
        request_id = "failed-durable-mission-request"
        with patch.object(self.execution, "_persist_checkpoint", return_value=False):
            refused = self.start(request_id=request_id)

        self.assertFalse(refused.success)
        self.assertIn("Execution start refused", refused.message)
        self.assertIn("could not be recorded durably", refused.message)
        self.assertEqual(self.execution._execution_store.load(), [])
        self.provider.discover.assert_not_called()
        self.fetcher.fetch.assert_not_called()
        self.transport.assert_not_called()

        retry = self.start(request_id=request_id)
        self.assertTrue(retry.success, retry.message)
        self.provider.discover.assert_called_once()

    def test_one_approval_conflict_followup_then_cited_report(self):
        with (
            patch.object(
                self.approvals, "record_for_plan", wraps=self.approvals.record_for_plan
            ) as approved,
            patch.object(
                self.execution,
                "process_continue",
                side_effect=AssertionError("No Continue"),
            ),
        ):
            response = self.start()
        self.assertTrue(response.success, response.message)
        approved.assert_called_once()
        self.assertEqual(self.transport.call_count, 2)
        self.assertEqual(self.fetcher.fetch.call_count, 3)
        self.assertEqual(response.research_plan_execution.completed_steps, 18)
        run = response.research_runs[0]
        self.assertEqual((len(run.evidence), len(run.comparison_notes)), (3, 2))
        self.assertEqual(run.claims, ())
        self.assertEqual(run.claim_contradictions, ())
        self.assertIn("How to interpret", response.message)
        for source in self.sources:
            self.assertIn(source.url, response.message)
        self.assertIn("Untrusted model rationale", response.message)
        allowance = self.execution.allowance(response.research_plan_execution.plan_id)
        self.assertEqual(
            (
                allowance.spend.step_advances,
                allowance.spend.network_operations,
                allowance.spend.llm_operations,
            ),
            (18, 9, 2),
        )
        # Canonical durable knowledge retains tentative labels and source provenance.
        saved = (self.root / "runs.json").read_text(encoding="utf-8")
        self.assertIn("tentative interpretation", saved)
        self.assertIn(run.evidence[0].chunk_sha256, saved)
        restored = JsonFileResearchRunStore(self.root / "runs.json").load()
        self.assertEqual(restored[0], run)

    def test_conflict_followup_persists_only_canonical_unresolved_outcome(self):
        response = self.start()
        checkpoint = self.execution._execution_store.load()[0].mission_checkpoint
        self.assertIsNotNone(checkpoint)
        self.assertEqual(checkpoint.contradiction_initial_relation, "possible_conflict")
        self.assertEqual(
            checkpoint.contradiction_initial_note_id, checkpoint.semantic_note_id
        )
        self.assertEqual(len(checkpoint.contradiction_initial_evidence_ids), 2)
        self.assertEqual(len(checkpoint.contradiction_initial_source_document_ids), 2)
        self.assertEqual(len(checkpoint.contradiction_initial_assessment_ids), 2)
        self.assertTrue(checkpoint.contradiction_followup_note_id)
        self.assertEqual(
            checkpoint.contradiction_followup_evidence_id,
            response.research_runs[0].evidence[-1].evidence_id,
        )
        self.assertEqual(checkpoint.contradiction_outcome, "unresolved")
        self.assertEqual(response.research_runs[0].claims, ())
        self.assertFalse(response.research_runs[0].status.terminal)
        self.assertIn("goal satisfaction: not declared", response.message.lower())

    def test_agreeing_followup_is_only_structurally_clarified(self):
        self.relations = ["possible_conflict", "possible_agreement"]
        response = self.start()
        checkpoint = self.execution._execution_store.load()[0].mission_checkpoint
        self.assertIsNotNone(checkpoint)
        self.assertEqual(
            checkpoint.contradiction_followup_relation, "possible_agreement"
        )
        self.assertEqual(checkpoint.contradiction_outcome, "structurally_clarified")
        self.assertEqual(response.research_runs[0].claims, ())
        self.assertFalse(response.research_runs[0].status.terminal)
        self.assertIn("goal satisfaction: not declared", response.message.lower())

    def test_conflict_derives_the_existing_typed_followup_slot_once(self):
        decisions = []

        def capture(plan_id):
            plan = self.execution.live_plan(plan_id)
            self.assertIsNotNone(plan)
            decisions.append(
                (
                    self.execution._mission_resolver.followup_decision(
                        plan,
                        plan.steps[12].step_id,
                        self.execution.allowance(plan_id),
                    ),
                    plan_digest(plan),
                )
            )

        with self.before_followup(capture):
            self.start()

        self.assertEqual(len(decisions), 1)
        decision, digest = decisions[0]
        self.assertEqual(
            decision.status, ResearchMissionFollowupDecisionStatus.PROPOSED
        )
        self.assertEqual(decision.capability, Cap.SOURCE_FETCH)
        self.assertEqual(decision.plan_digest, digest)
        self.assertEqual(decision.semantic_relation, "possible_conflict")
        self.assertEqual(self.fetcher.fetch.call_count, 3)

    def test_no_followup_decision_does_not_create_an_attempt(self):
        self.relation = "possible_agreement"
        response = self.start()
        plan = self.execution.live_plan(response.research_plan_execution.plan_id)
        self.assertIsNotNone(plan)

        decision = self.execution._mission_resolver.followup_decision(
            plan,
            plan.steps[12].step_id,
            self.execution.allowance(plan.plan_id),
        )

        self.assertEqual(
            decision.status, ResearchMissionFollowupDecisionStatus.NOT_NEEDED
        )
        self.assertEqual(self.fetcher.fetch.call_count, 2)

    def test_prior_cumulative_spending_blocks_followup_before_fetch(self):
        decisions = []

        def exhaust_network(plan_id):
            allowance = self.execution.allowance(plan_id)
            self.assertIsNotNone(allowance)
            self.execution._allowances[plan_id] = ResearchExecutionAllowance(
                allowance.budget,
                ResearchExecutionSpend(
                    step_advances=allowance.spend.step_advances,
                    network_operations=allowance.budget.max_network_operations,
                    llm_operations=allowance.spend.llm_operations,
                    active_seconds=allowance.spend.active_seconds,
                ),
            )
            plan = self.execution.live_plan(plan_id)
            self.assertIsNotNone(plan)
            decisions.append(
                self.execution._mission_resolver.followup_decision(
                    plan,
                    plan.steps[12].step_id,
                    self.execution.allowance(plan_id),
                )
            )

        with self.before_followup(exhaust_network):
            response = self.start()

        self.assertEqual(
            decisions[0].status, ResearchMissionFollowupDecisionStatus.BUDGET_LIMITED
        )
        self.assertEqual(self.fetcher.fetch.call_count, 2)
        self.assertEqual(response.research_plan_execution.completed_steps, 12)

    def test_restart_after_durable_followup_never_replays_it(self):
        response = self.start()
        snapshot = self.execution._execution_store.load()[0]
        before = (
            self.provider.discover.call_count,
            self.fetcher.fetch.call_count,
            self.transport.call_count,
        )
        engine = self.restart()
        execution = engine._research_plan_execution_service
        state = execution.restored_execution(snapshot.plan_id)
        self.assertIsNotNone(state)
        self.assertEqual(
            sum(step.status.value == "completed" for step in state.steps), 18
        )
        self.assertEqual(
            (
                self.provider.discover.call_count,
                self.fetcher.fetch.call_count,
                self.transport.call_count,
            ),
            before,
        )
        self.assertEqual(
            state.allowance,
            self.execution.allowance(response.research_plan_execution.plan_id),
        )

    def test_changed_followup_fingerprint_refuses_restart_without_replay(self):
        self.start()
        snapshot = self.execution._execution_store.load()[0]
        plan = self.execution.live_plan(snapshot.plan_id)
        self.assertIsNotNone(plan)
        path = self.root / "research_executions.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        checkpoint = document["executions"][0]["mission_checkpoint"]
        checkpoint["contradiction_followup_input_fingerprint"] = "0" * 64
        path.write_text(json.dumps(document), encoding="utf-8")

        engine = self.restart()
        resolver = engine._research_plan_execution_service._mission_resolver
        self.assertIsNotNone(resolver)
        with self.assertRaisesRegex(
            ResearchError, "contradiction follow-up provenance"
        ):
            resolver.restore(
                plan,
                engine._research_plan_execution_service._restored[
                    snapshot.plan_id
                ].mission_checkpoint,
                engine._research_plan_execution_service._restored[
                    snapshot.plan_id
                ].steps,
                engine._research_plan_execution_service._restored[
                    snapshot.plan_id
                ].research_run_id,
            )
        self.assertEqual(self.fetcher.fetch.call_count, 3)
        self.assertEqual(self.transport.call_count, 2)

    def test_legacy_checkpoint_without_outcome_restores_completed_work_safely(self):
        self.start()
        snapshot = self.execution._execution_store.load()[0]
        path = self.root / "research_executions.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        checkpoint = document["executions"][0]["mission_checkpoint"]
        for key in tuple(checkpoint):
            if key.startswith("contradiction_"):
                checkpoint.pop(key)
        path.write_text(json.dumps(document), encoding="utf-8")

        engine = self.restart()
        state = engine._research_plan_execution_service.restored_execution(
            snapshot.plan_id
        )
        self.assertIsNotNone(state)
        self.assertEqual(
            sum(step.status.value == "completed" for step in state.steps), 18
        )
        self.assertEqual(self.fetcher.fetch.call_count, 3)
        self.assertEqual(self.transport.call_count, 2)

    def test_restart_resumes_from_durable_first_source_checkpoint_without_replay(self):
        """A restart continues durable work, never a transient preview/model call."""
        real_advance = self.execution.process_advance

        def interrupt_after_first_assessment(request):
            state = self.execution.live_execution(request.metadata["research_plan_id"])
            if state is not None and state.completed_steps == 6:
                raise RuntimeError("simulated process interruption")
            return real_advance(request)

        with patch.object(
            self.execution,
            "process_advance",
            side_effect=interrupt_after_first_assessment,
        ):
            with self.assertRaisesRegex(RuntimeError, "simulated process interruption"):
                self.start()

        snapshot = self.execution._execution_store.load()[0]
        self.assertEqual(snapshot.steps[5].status.value, "completed")
        self.assertIsNotNone(snapshot.mission_scope)
        self.assertIsNotNone(snapshot.mission_checkpoint)
        self.assertEqual(snapshot.mission_checkpoint.evidence_ids.__len__(), 1)
        self.assertEqual(self.provider.discover.call_count, 1)
        self.assertEqual(self.fetcher.fetch.call_count, 1)
        self.transport.assert_not_called()

        release_all()
        restarted = Bootstrap(
            memory_path=self.root / "memory.json",
            session_path=self.root / "sessions.json",
            knowledge_relation_path=self.root / "relations.json",
            research_run_path=self.root / "runs.json",
            llm_config=LLMRuntimeConfig(True, self.policy.endpoint, self.policy.model),
            llm_provider=Mock(),
            semantic_comparison_transport=self.transport,
            research_source_fetcher=self.fetcher,
            research_source_discovery_provider=self.provider,
            research_source_discovery_providers={
                ResearchDiscoveryProviderName.CROSSREF: self.provider
            },
        )
        restarted.initialize()
        engine = restarted.container.resolve(CognitiveEngine)
        state = engine._research_plan_execution_service.live_execution(snapshot.plan_id)

        self.assertIsNotNone(state)
        self.assertEqual(state.completed_steps, 18)
        self.assertEqual(self.provider.discover.call_count, 1)
        self.assertEqual(self.fetcher.fetch.call_count, 3)
        self.assertEqual(self.transport.call_count, 2)
        allowance = engine._research_plan_execution_service.allowance(snapshot.plan_id)
        self.assertEqual(
            (
                allowance.spend.step_advances,
                allowance.spend.network_operations,
                allowance.spend.llm_operations,
            ),
            (18, 9, 2),
        )

    def test_restart_uses_persisted_conflict_note_for_one_followup(self):
        """A retained tentative conflict unlocks only the declared next branch."""
        real_advance = self.execution.process_advance

        def interrupt_before_followup(request):
            state = self.execution.live_execution(request.metadata["research_plan_id"])
            if state is not None and state.completed_steps == 12:
                raise RuntimeError("simulated restart after retained semantic note")
            return real_advance(request)

        with patch.object(
            self.execution,
            "process_advance",
            side_effect=interrupt_before_followup,
        ):
            with self.assertRaisesRegex(RuntimeError, "retained semantic note"):
                self.start()

        snapshot = self.execution._execution_store.load()[0]
        checkpoint = snapshot.mission_checkpoint
        self.assertIsNotNone(checkpoint)
        self.assertEqual(checkpoint.semantic_relation, "possible_conflict")
        self.assertTrue(checkpoint.semantic_note_id)
        self.assertEqual(self.fetcher.fetch.call_count, 2)
        self.assertEqual(self.transport.call_count, 1)

        engine = self.restart()
        state = engine._research_plan_execution_service.live_execution(snapshot.plan_id)
        self.assertIsNotNone(state)
        self.assertEqual(state.completed_steps, 18)
        self.assertEqual(self.provider.discover.call_count, 1)
        self.assertEqual(self.fetcher.fetch.call_count, 3)
        self.assertEqual(self.transport.call_count, 2)
        allowance = engine._research_plan_execution_service.allowance(snapshot.plan_id)
        self.assertEqual(
            (
                allowance.spend.step_advances,
                allowance.spend.network_operations,
                allowance.spend.llm_operations,
            ),
            (18, 9, 2),
        )

    def test_restart_not_comparable_stops_without_replaying_or_followup(self):
        """A retained non-comparable result ends the optional branch honestly."""
        self.relation = "not_comparable"
        response = self.start()
        snapshot = self.execution._execution_store.load()[0]
        self.assertEqual(response.research_plan_execution.completed_steps, 12)
        engine = self.restart()
        state = engine._research_plan_execution_service.live_execution(snapshot.plan_id)
        self.assertIsNotNone(state)
        self.assertEqual(state.completed_steps, 12)
        self.assertEqual(self.provider.discover.call_count, 1)
        self.assertEqual(self.fetcher.fetch.call_count, 2)
        self.assertEqual(self.transport.call_count, 1)

    def test_restart_refuses_altered_semantic_note_before_followup(self):
        """A note text change cannot silently spend the approved followup call."""
        real_advance = self.execution.process_advance

        def interrupt_before_followup(request):
            state = self.execution.live_execution(request.metadata["research_plan_id"])
            if state is not None and state.completed_steps == 12:
                raise RuntimeError("simulated restart after retained semantic note")
            return real_advance(request)

        with patch.object(
            self.execution,
            "process_advance",
            side_effect=interrupt_before_followup,
        ):
            with self.assertRaisesRegex(RuntimeError, "retained semantic note"):
                self.start()

        snapshot = self.execution._execution_store.load()[0]
        checkpoint = snapshot.mission_checkpoint
        self.assertIsNotNone(checkpoint)
        path = self.root / "runs.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        document["runs"][0]["comparison_notes"][0]["text"] = "altered retained note"
        path.write_text(json.dumps(document), encoding="utf-8")

        engine = self.restart()
        execution = engine._research_plan_execution_service
        self.assertIsNone(execution.live_execution(snapshot.plan_id))
        self.assertIsNotNone(execution.restored_execution(snapshot.plan_id))
        status = execution.process_status(
            BrainRequest(
                message="status",
                metadata={
                    "intent": "research_plan_execution_status",
                    "research_plan_id": snapshot.plan_id,
                },
            )
        )
        self.assertIn("semantic note provenance", status.message)
        self.assertEqual(self.fetcher.fetch.call_count, 2)
        self.assertEqual(self.transport.call_count, 1)

    def test_restart_refuses_legacy_note_checkpoint_before_followup(self):
        """Older checkpoints never gain an inferred semantic branch decision."""
        real_advance = self.execution.process_advance

        def interrupt_before_followup(request):
            state = self.execution.live_execution(request.metadata["research_plan_id"])
            if state is not None and state.completed_steps == 12:
                raise RuntimeError("simulated restart after retained semantic note")
            return real_advance(request)

        with patch.object(
            self.execution,
            "process_advance",
            side_effect=interrupt_before_followup,
        ):
            with self.assertRaisesRegex(RuntimeError, "retained semantic note"):
                self.start()

        snapshot = self.execution._execution_store.load()[0]
        path = self.root / "research_executions.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        checkpoint = document["executions"][0]["mission_checkpoint"]
        for key in (
            "semantic_note_id",
            "semantic_input_fingerprint",
            "semantic_relation",
            "contradiction_initial_note_id",
            "contradiction_initial_evidence_ids",
            "contradiction_initial_source_document_ids",
            "contradiction_initial_assessment_ids",
            "contradiction_initial_input_fingerprint",
            "contradiction_initial_relation",
            "contradiction_followup_note_id",
            "contradiction_followup_evidence_id",
            "contradiction_followup_source_document_id",
            "contradiction_followup_assessment_id",
            "contradiction_followup_input_fingerprint",
            "contradiction_followup_relation",
            "contradiction_outcome",
        ):
            checkpoint.pop(key)
        path.write_text(json.dumps(document), encoding="utf-8")

        engine = self.restart()
        execution = engine._research_plan_execution_service
        self.assertIsNone(execution.live_execution(snapshot.plan_id))
        status = execution.process_status(
            BrainRequest(
                message="status",
                metadata={
                    "intent": "research_plan_execution_status",
                    "research_plan_id": snapshot.plan_id,
                },
            )
        )
        self.assertIn("adaptation checkpoint is unavailable", status.message)
        self.assertEqual(self.fetcher.fetch.call_count, 2)
        self.assertEqual(self.transport.call_count, 1)

    def test_restart_refuses_transient_fetch_preview_without_replaying_it(self):
        """A fetched-but-unaccepted page has no durable content checkpoint."""
        real_advance = self.execution.process_advance

        def interrupt_after_fetch(request):
            state = self.execution.live_execution(request.metadata["research_plan_id"])
            if state is not None and state.completed_steps == 3:
                raise RuntimeError("simulated process interruption")
            return real_advance(request)

        with patch.object(
            self.execution, "process_advance", side_effect=interrupt_after_fetch
        ):
            with self.assertRaisesRegex(RuntimeError, "simulated process interruption"):
                self.start()

        snapshot = self.execution._execution_store.load()[0]
        self.assertEqual(snapshot.steps[2].status.value, "completed")
        self.assertEqual(self.fetcher.fetch.call_count, 1)
        release_all()
        restarted = Bootstrap(
            memory_path=self.root / "memory.json",
            session_path=self.root / "sessions.json",
            knowledge_relation_path=self.root / "relations.json",
            research_run_path=self.root / "runs.json",
            llm_config=LLMRuntimeConfig(True, self.policy.endpoint, self.policy.model),
            llm_provider=Mock(),
            semantic_comparison_transport=self.transport,
            research_source_fetcher=self.fetcher,
            research_source_discovery_provider=self.provider,
            research_source_discovery_providers={
                ResearchDiscoveryProviderName.CROSSREF: self.provider
            },
        )
        restarted.initialize()
        engine = restarted.container.resolve(CognitiveEngine)

        self.assertIsNone(
            engine._research_plan_execution_service.live_execution(snapshot.plan_id)
        )
        self.assertIsNotNone(
            engine._research_plan_execution_service.restored_execution(snapshot.plan_id)
        )
        status = engine._research_plan_execution_service.process_status(
            BrainRequest(
                message="status",
                metadata={
                    "intent": "research_plan_execution_status",
                    "research_plan_id": snapshot.plan_id,
                },
            )
        )
        self.assertIn("preview was not durably accepted", status.message)
        self.assertEqual(self.provider.discover.call_count, 1)
        self.assertEqual(self.fetcher.fetch.call_count, 1)
        self.transport.assert_not_called()

    def test_restart_refuses_accepted_source_without_evidence_preview(self):
        """Acceptance persists source text, not the transient evidence selection."""
        real_advance = self.execution.process_advance

        def interrupt_after_acceptance(request):
            state = self.execution.live_execution(request.metadata["research_plan_id"])
            if state is not None and state.completed_steps == 4:
                raise RuntimeError("simulated process interruption")
            return real_advance(request)

        with patch.object(
            self.execution, "process_advance", side_effect=interrupt_after_acceptance
        ):
            with self.assertRaisesRegex(RuntimeError, "simulated process interruption"):
                self.start()

        snapshot = self.execution._execution_store.load()[0]
        release_all()
        restarted = Bootstrap(
            memory_path=self.root / "memory.json",
            session_path=self.root / "sessions.json",
            knowledge_relation_path=self.root / "relations.json",
            research_run_path=self.root / "runs.json",
            llm_config=LLMRuntimeConfig(True, self.policy.endpoint, self.policy.model),
            llm_provider=Mock(),
            semantic_comparison_transport=self.transport,
            research_source_fetcher=self.fetcher,
            research_source_discovery_provider=self.provider,
            research_source_discovery_providers={
                ResearchDiscoveryProviderName.CROSSREF: self.provider
            },
        )
        restarted.initialize()
        execution = restarted.container.resolve(
            CognitiveEngine
        )._research_plan_execution_service

        self.assertIsNone(execution.live_execution(snapshot.plan_id))
        self.assertIsNotNone(execution.restored_execution(snapshot.plan_id))
        self.assertEqual(self.fetcher.fetch.call_count, 1)
        self.transport.assert_not_called()

    def test_not_comparable_stops_without_followup_or_retry(self):
        self.relation = "not_comparable"
        response = self.start()
        self.assertEqual(self.transport.call_count, 1, response.message)
        self.assertEqual(self.fetcher.fetch.call_count, 2)
        self.assertEqual(
            response.research_autonomy.stop_reason.value, "research_deliverable_ready"
        )
        self.assertEqual(response.research_plan_execution.completed_steps, 12)
        self.assertIn("not_comparable", response.message)

    def test_destination_mismatch_refuses_before_research(self):
        response = self.start(policy=replace(self.policy, model="other"))
        self.assertFalse(response.success)
        self.transport.assert_not_called()
        self.provider.discover.assert_not_called()

    def test_content_budget_blocks_before_disclosure(self):
        response = self.start(policy=replace(self.policy, max_input_bytes=1))
        self.transport.assert_not_called()
        self.assertIn("step_failed", response.message)
        self.assertIn("No validated comparison", response.message)

    def test_cancel_before_start_makes_no_calls(self):
        signal = CancellationSignal()
        signal.cancel()
        self.assertFalse(self.start(cancellation_token=signal).success)
        self.provider.discover.assert_not_called()
        self.transport.assert_not_called()

    def test_malformed_output_returns_partial_cited_report(self):
        self.transport.side_effect = None
        self.transport.return_value = {"choices": [{"message": {"content": "invalid"}}]}
        response = self.start()
        self.assertEqual(self.transport.call_count, 1)
        self.assertIn("step_failed", response.message)
        self.assertIn(self.sources[0].url, response.message)
        self.assertEqual(len(response.research_runs[0].comparison_notes), 0)

    def test_no_relevant_sources_stops_with_useful_limitation(self):
        self.provider.discover.return_value = []
        response = self.start()
        self.transport.assert_not_called()
        self.fetcher.fetch.assert_not_called()
        self.assertIn("insufficient support", response.message)

    def test_registered_runtime_does_not_authorize_legacy_model_budget(self):
        self.assertIsNotNone(
            self.execution._operation_registry.resolve(Cap.SEMANTIC_EVIDENCE_COMPARISON)
        )
        response = self.controller.start_research_goal(
            self.question, "crossref", self.budget, compare_sources=True
        )
        self.assertFalse(response.success)
        self.transport.assert_not_called()

    def test_preview_is_inert_and_exposes_destination_and_envelope(self):
        before = list(self.root.glob("*.json"))
        response = self.controller.preview_learning_research(
            self.question, "crossref", self.budget
        )
        self.assertTrue(response.success, response.message)
        self.assertEqual(
            response.research_plan_draft_preview.plan.mission_scope.semantic_policy,
            self.policy,
        )
        self.assertIn(self.policy.endpoint, response.message)
        self.assertIn("9 network", response.message)
        self.assertEqual(list(self.root.glob("*.json")), before)
        self.transport.assert_not_called()
        self.provider.discover.assert_not_called()

    def test_advisory_lesson_retains_provenance_and_is_recalled(self):
        self.provider.discover.return_value = []
        first = self.start()
        run = first.research_runs[0]
        path = self.root / "research_failure_lessons.json"
        lessons = JsonFileFailureLessonStore(path).load()
        self.assertTrue(lessons)
        self.assertEqual(lessons[0].run_id, run.run_id)
        self.assertIn(run.discoveries[0].discovery_id, lessons[0].provenance)
        second = self.start()
        self.assertIn(run.run_id, second.message)
        self.assertIn("Prior advisory lessons", second.message)
        self.assertEqual(second.research_runs[0].claims, ())

    def test_model_cancellation_retains_charge_not_result(self):
        signal = CancellationSignal()

        def cancelled(*args):
            result = self.answer(*args)
            signal.cancel()
            return result

        self.transport.side_effect = cancelled
        response = self.start(cancellation_token=signal)
        self.transport.assert_called_once()
        self.assertEqual(len(response.research_runs[0].comparison_notes), 0)
        self.assertEqual(
            self.execution.allowance(
                response.research_plan_execution.plan_id
            ).spend.llm_operations,
            1,
        )
        self.assertIn("cancelled", response.message)

    def test_unavailable_source_fails_once_and_retains_lesson(self):
        self.fetcher.fetch.side_effect = ResearchError("fixture unavailable")
        response = self.start()
        self.fetcher.fetch.assert_called_once()
        self.transport.assert_not_called()
        self.assertIn("step_failed", response.message)
        self.assertTrue(self.engine._failure_memory_service.lessons())

    def test_empty_model_proposal_follows_up_once_only(self):
        self.transport.side_effect = None
        self.transport.return_value = {
            "choices": [{"message": {"content": '{"comparisons": []}'}}]
        }
        response = self.start()
        self.assertEqual(self.transport.call_count, 2)
        self.assertEqual(self.fetcher.fetch.call_count, 3)
        self.assertIn("evidence gap remains", response.message)
        self.assertEqual(response.research_runs[0].claims, ())

    def before_first_comparison(self, callback):
        real = self.execution.process_advance

        def advance(request):
            plan_id = request.metadata["research_plan_id"]
            state = self.execution.live_execution(plan_id)
            if state.completed_steps == 10:
                callback(plan_id)
            return real(request)

        return patch.object(self.execution, "process_advance", side_effect=advance)

    def before_followup(self, callback):
        real = self.execution.process_advance

        def advance(request):
            plan_id = request.metadata["research_plan_id"]
            state = self.execution.live_execution(plan_id)
            if state.completed_steps == 12:
                callback(plan_id)
            return real(request)

        return patch.object(self.execution, "process_advance", side_effect=advance)

    def test_prior_spending_exhausts_same_allowance_before_model(self):
        def exhaust(plan_id):
            allowance = self.execution.allowance(plan_id)
            cost = cost_for(Cap.SEMANTIC_EVIDENCE_COMPARISON)
            self.execution._allowances[plan_id] = allowance.charged(cost).charged(cost)

        with self.before_first_comparison(exhaust):
            response = self.start()
        self.transport.assert_not_called()
        self.assertEqual(
            self.execution.allowance(
                response.research_plan_execution.plan_id
            ).spend.llm_operations,
            2,
        )

    def test_changed_canonical_evidence_refuses_before_disclosure(self):
        def change(plan_id):
            run_id = self.execution._contexts[plan_id].research_run_id
            manager = self.engine._research_goal_start_service._runs
            manager._runs = tuple(
                replace(r, evidence=(), assessments=()) if r.run_id == run_id else r
                for r in manager._runs
            )

        with self.before_first_comparison(change):
            response = self.start()
        self.transport.assert_not_called()
        self.assertIn("step_failed", response.message)

    def test_changed_mission_destination_invalidates_consumed_authority(self):
        def change(plan_id):
            plan = self.execution.live_plan(plan_id)
            scope = plan.mission_scope
            policy = replace(scope.semantic_policy, model="substitution")
            self.execution._plans[plan_id] = replace(
                plan,
                mission_scope=replace(scope, semantic_policy=policy),
                steps=tuple(
                    (
                        replace(s, semantic_mission_policy=policy)
                        if s.semantic_mission_policy
                        else s
                    )
                    for s in plan.steps
                ),
            )

        with self.before_first_comparison(change):
            response = self.start()
        self.transport.assert_not_called()
        self.assertIn("advance_refused", response.message)

    def test_insufficient_initial_budget_cannot_create_run(self):
        self.budget = replace(self.budget, max_llm_operations=1)
        response = self.start()
        self.assertFalse(response.success)
        self.provider.discover.assert_not_called()
        self.transport.assert_not_called()

    def test_finished_optional_branch_cannot_spend_again(self):
        self.relation = "possible_agreement"
        response = self.start()
        plan_id = response.research_plan_execution.plan_id
        before = self.execution.allowance(plan_id)
        self.execution.process_advance(
            BrainRequest(
                message="advance",
                metadata={
                    "research_plan_id": plan_id,
                    "intent": "research_plan_execution_advance",
                },
            )
        )
        self.assertEqual(self.execution.allowance(plan_id), before)
        self.transport.assert_called_once()

    def test_missing_original_allowance_cannot_disclose(self):
        with self.before_first_comparison(
            lambda key: self.execution._allowances.pop(key)
        ):
            response = self.start()
        self.transport.assert_not_called()
        self.assertIn("advance_refused", response.message)

    def test_wrong_run_context_cannot_disclose_other_missions_evidence(self):
        def change(plan_id):
            runs = self.engine._research_goal_start_service._runs
            other = runs.create(self.question)
            self.execution._contexts[plan_id] = replace(
                self.execution._contexts[plan_id], research_run_id=other.run_id
            )

        with self.before_first_comparison(change):
            response = self.start()
        self.transport.assert_not_called()
        self.assertIn("step_failed", response.message)

    def test_runtime_disclosure_cannot_be_substituted(self):
        def change(plan_id):
            self.execution._contexts[plan_id] = replace(
                self.execution._contexts[plan_id], disclosure=ResearchDisclosure.NONE
            )

        with self.before_first_comparison(change):
            response = self.start()
        self.transport.assert_not_called()
        self.assertIn("step_failed", response.message)

    def test_lesson_failure_does_not_discard_research_report(self):
        with patch.object(
            self.engine._failure_memory_service,
            "process_store",
            side_effect=ResearchError("store unavailable"),
        ):
            response = self.start()
        self.assertIn("Lesson retention unavailable", response.message)
        self.assertIn(self.sources[0].url, response.message)
        self.assertEqual(self.transport.call_count, 2)

    def test_invented_model_quote_fails_without_retry(self):
        def invented(*args):
            output = self.answer(*args)
            body = json.loads(output["choices"][0]["message"]["content"])
            body["comparisons"][0]["left_quote"] = "unsupported invented quotation"
            output["choices"][0]["message"]["content"] = json.dumps(body)
            return output

        self.transport.side_effect = invented
        response = self.start()
        self.transport.assert_called_once()
        self.assertIn("step_failed", response.message)
        self.assertEqual(response.research_runs[0].comparison_notes, ())

    def test_cumulative_time_exhaustion_blocks_before_model(self):
        def exhaust(plan_id):
            self.execution._allowances[plan_id] = self.execution.allowance(
                plan_id
            ).with_elapsed(self.budget.max_seconds)

        with self.before_first_comparison(exhaust):
            response = self.start()
        self.transport.assert_not_called()
        self.assertIn("advance_refused", response.message)
