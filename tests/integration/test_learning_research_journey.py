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
from brain.BrainResponse import BrainResponse
from cognition.CognitiveEngine import CognitiveEngine
from cognition.ResearchAutonomyApplicationService import (
    ResearchAutonomyApplicationService,
)
from core.Bootstrap import Bootstrap
from core.CancellationSignal import CancellationSignal
from core.Exceptions import ResearchError
from core.ExclusiveStoreOwnership import release_all
from desktop.DesktopController import DesktopController
from desktop.MissionComparisonReview import mission_comparison_review_preview
from desktop.MissionSourceIndependenceReview import (
    independence_assessment_arguments,
    independence_review_rows,
)
from knowledge.KnowledgeEngine import KnowledgeEngine
from llm.LLMRuntimeConfig import LLMRuntimeConfig
from research.JsonFileFailureLessonStore import JsonFileFailureLessonStore
from research.JsonFileResearchExecutionStore import JsonFileResearchExecutionStore
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchAutonomyResult import AutonomyStopReason
from research.ResearchCapabilityCost import cost_for
from research.ResearchDisclosure import ResearchDisclosure
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchEvidenceCompletionEvaluation import (
    ResearchEvidenceCompletionCaveat as Caveat,
)
from research.ResearchEvidenceCompletionEvaluation import (
    source_independence_caveats,
)
from research.ResearchExecutionAllowance import ResearchExecutionAllowance
from research.ResearchExecutionSpend import ResearchExecutionSpend
from research.ResearchFailureLessonDeriver import ResearchFailureLessonDeriver
from research.ResearchMissionAudit import build_mission_audit, mission_audit_json
from research.ResearchMissionFollowupDecision import (
    ResearchMissionFollowupDecisionStatus,
)
from research.ResearchMissionGoalSatisfaction import (
    ResearchMissionGoalSatisfactionStatus as GoalStatus,
)
from research.ResearchMissionOutcome import mission_outcome_for
from research.ResearchPlanDigest import plan_digest
from research.ResearchPlanExecutionCodec import (
    decode_execution_snapshot,
    encode_execution_snapshot,
)
from research.ResearchPlanStepCapability import ResearchPlanStepCapability as Cap
from research.ResearchPlanStepStatus import ResearchPlanStepStatus
from research.ResearchRunManager import ResearchRunManager
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSource import ResearchSource
from research.ResearchSourceCandidate import ResearchSourceCandidate
from research.ResearchTeachingReport import teaching_report
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
        # The calling mission is the one with a running step; with several
        # stored missions the newest snapshot need not be it.
        running = [
            snapshot
            for snapshot in snapshots
            if any(s.status.value == "running" for s in snapshot.steps)
        ]
        self.assertEqual(len(running), 1)
        # Every model call, across every mission in this test, was charged to
        # the allowance of the mission that made it before it was made.
        self.assertEqual(
            sum(
                snapshot.allowance.spend.llm_operations
                for snapshot in snapshots
                if snapshot.allowance is not None
            ),
            self.transport.call_count,
        )
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
        self.restarted = restarted
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
        self.assertIn("mission goal satisfaction: unresolved", response.message.lower())

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
        self.assertIn("Mission goal satisfaction: Unresolved", response.message)
        self.assertIn(
            "Mission completion readiness: Not ready: a canonical conflict remains "
            "unresolved",
            response.message,
        )
        self.assertIn("clarifies the conflict structure", response.message)
        self.assertIn(
            "does not establish a verified resolution of the original disputed "
            "comparison or claim",
            response.message,
        )
        self.assertNotIn(
            "Satisfied within the current bounded evidence", response.message
        )
        self.assertNotIn("Ready for bounded user conclusion", response.message)

    def clarified_conflict(self):
        self.relations = ["possible_conflict", "possible_agreement"]
        response = self.start()
        snapshot = self.execution._execution_store.load()[0]
        return response, snapshot

    def test_clarified_conflict_spends_nothing_extra_and_stays_tentative(self):
        response, snapshot = self.clarified_conflict()
        plan_id = response.research_plan_execution.plan_id
        checkpoint = snapshot.mission_checkpoint
        run = response.research_runs[0]

        # The follow-up pairs the first source (side A) with one new source;
        # the second source (side B) is never a follow-up target by design.
        note = next(
            value
            for value in run.comparison_notes
            if value.note_id == checkpoint.contradiction_followup_note_id
        )
        self.assertEqual(
            note.evidence_ids[0], checkpoint.contradiction_initial_evidence_ids[0]
        )
        self.assertNotIn(
            checkpoint.contradiction_initial_evidence_ids[1], note.evidence_ids
        )
        self.assertIn("Tentative relation: possible_agreement.", note.text)
        self.assertEqual(
            checkpoint.contradiction_followup_relation, "possible_agreement"
        )
        self.assertEqual((run.claims, run.claim_contradictions), ((), ()))
        self.assertEqual(
            {assessment.information_trust.value for assessment in run.assessments},
            {"unassessed"},
        )
        plan = self.execution.live_plan(plan_id)
        self.assertIs(
            self.execution._mission_resolver.followup_decision(
                plan, plan.steps[12].step_id, self.execution.allowance(plan_id)
            ).status,
            ResearchMissionFollowupDecisionStatus.COMPLETED,
        )
        self.assertEqual(plan_digest(plan), snapshot.mission_plan_digest)
        self.assertEqual(len(checkpoint.acquired_urls), 3)
        self.assertEqual(self.spend(self.execution, plan_id), (18, 9, 2))
        self.assertEqual(
            (self.fetcher.fetch.call_count, self.transport.call_count), (3, 2)
        )

    def test_restart_recomputes_the_same_unresolved_clarified_conflict(self):
        response, snapshot = self.clarified_conflict()
        plan_id = response.research_plan_execution.plan_id
        stop = response.research_autonomy.stop_reason.value
        calls = self.external_calls()

        engine = self.restart()

        restored = engine._research_plan_execution_service.restored_execution(plan_id)
        self.assertEqual(restored.mission_checkpoint, snapshot.mission_checkpoint)
        self.assertEqual(restored.mission_plan_digest, snapshot.mission_plan_digest)
        self.assertEqual(restored.allowance, snapshot.allowance)
        run = JsonFileResearchRunStore(self.root / "runs.json").load()[0]
        outcome = mission_outcome_for(run, stop, restored.mission_checkpoint)
        self.assertIs(outcome.goal_satisfaction.status, GoalStatus.UNRESOLVED)
        self.assertFalse(outcome.completion_readiness.ready)
        self.assertEqual(self.external_calls(), calls)

    def test_legacy_clarified_checkpoint_never_becomes_satisfied(self):
        response, _ = self.clarified_conflict()
        plan_id = response.research_plan_execution.plan_id
        stop = response.research_autonomy.stop_reason.value
        path = self.root / "research_executions.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        checkpoint = document["executions"][0]["mission_checkpoint"]
        for key in tuple(checkpoint):
            if key.startswith(("contradiction_", "evidence_gap_")):
                checkpoint.pop(key)
        path.write_text(json.dumps(document), encoding="utf-8")
        calls = self.external_calls()

        engine = self.restart()

        legacy = engine._research_plan_execution_service.restored_execution(
            plan_id
        ).mission_checkpoint
        self.assertEqual(legacy.semantic_relation, "possible_conflict")
        self.assertEqual(legacy.contradiction_outcome, "")
        run = JsonFileResearchRunStore(self.root / "runs.json").load()[0]
        outcome = mission_outcome_for(run, stop, legacy)
        self.assertIs(outcome.goal_satisfaction.status, GoalStatus.UNRESOLVED)
        self.assertFalse(outcome.completion_readiness.ready)
        self.assertEqual(self.external_calls(), calls)

    def test_initial_tentative_agreement_is_unresolved_without_extra_work(self):
        self.relation = "possible_agreement"

        response = self.start()

        plan_id = response.research_plan_execution.plan_id
        snapshot = self.execution._execution_store.load()[0]
        checkpoint = snapshot.mission_checkpoint
        run = response.research_runs[0]
        self.assertEqual(checkpoint.semantic_relation, "possible_agreement")
        self.assertIn("Mission goal satisfaction: Unresolved", response.message)
        self.assertIn(
            "Mission completion readiness: Not ready: canonical evidence remains "
            "incomplete",
            response.message,
        )
        self.assertIn("The selected sources tentatively agree", response.message)
        self.assertIn(
            "does not establish a sufficiently supported comparison", response.message
        )
        self.assertNotIn(
            "Satisfied within the current bounded evidence", response.message
        )
        self.assertNotIn("Ready for bounded user conclusion", response.message)
        self.assertNotIn("clarifies the conflict structure", response.message)
        self.assertIn(
            "Tentative relation: possible_agreement.", run.comparison_notes[0].text
        )
        self.assertEqual(run.claims, ())
        self.assertEqual(
            {assessment.information_trust.value for assessment in run.assessments},
            {"unassessed"},
        )
        self.assertEqual(
            {assessment.independence.value for assessment in run.assessments},
            {"unknown"},
        )
        plan = self.execution.live_plan(plan_id)
        self.assertIs(
            self.execution._mission_resolver.followup_decision(
                plan, plan.steps[12].step_id, self.execution.allowance(plan_id)
            ).status,
            ResearchMissionFollowupDecisionStatus.NOT_NEEDED,
        )
        self.assertEqual(plan_digest(plan), snapshot.mission_plan_digest)
        self.assertEqual(len(checkpoint.acquired_urls), 2)
        self.assertEqual(self.spend(self.execution, plan_id), (12, 6, 1))
        self.assertEqual(
            (self.fetcher.fetch.call_count, self.transport.call_count), (2, 1)
        )

    def test_restart_recovers_the_same_unresolved_tentative_agreement(self):
        self.relation = "possible_agreement"
        response = self.start()
        plan_id = response.research_plan_execution.plan_id
        before = self.execution._execution_store.load()[0]
        calls = self.external_calls()

        engine = self.restart()

        execution = engine._research_plan_execution_service
        self.assertEqual(
            execution.mission_checkpoint(plan_id), before.mission_checkpoint
        )
        self.assertEqual(
            plan_digest(execution.live_plan(plan_id)), before.mission_plan_digest
        )
        status = self.execution_status(engine, plan_id).message
        self.assertIn("Recovered mission teaching report", status)
        self.assertIn("Mission goal satisfaction: Unresolved", status)
        self.assertIn("The selected sources tentatively agree", status)
        self.assertEqual(self.external_calls(), calls)
        self.assertEqual(self.spend(execution, plan_id), (12, 6, 1))

    def test_legacy_agreement_checkpoints_never_become_satisfied(self):
        self.relation = "possible_agreement"
        response = self.start()
        plan_id = response.research_plan_execution.plan_id
        stop = response.research_autonomy.stop_reason.value
        path = self.root / "research_executions.json"
        cases = (
            ("before contradiction fields", ("contradiction_", "evidence_gap_")),
            (
                "before semantic relation",
                ("contradiction_", "evidence_gap_", "semantic_"),
            ),
        )
        for label, prefixes in cases:
            with self.subTest(checkpoint=label):
                document = json.loads(path.read_text(encoding="utf-8"))
                checkpoint = document["executions"][0]["mission_checkpoint"]
                for key in tuple(checkpoint):
                    if key.startswith(prefixes):
                        checkpoint.pop(key)
                path.write_text(json.dumps(document), encoding="utf-8")
                calls = self.external_calls()

                engine = self.restart()

                execution = engine._research_plan_execution_service
                restored = execution.restored_execution(plan_id)
                legacy = (
                    restored.mission_checkpoint
                    if restored is not None
                    else execution.mission_checkpoint(plan_id)
                )
                run = JsonFileResearchRunStore(self.root / "runs.json").load()[0]
                outcome = mission_outcome_for(run, stop, legacy)
                self.assertIs(outcome.goal_satisfaction.status, GoalStatus.UNRESOLVED)
                self.assertFalse(outcome.completion_readiness.ready)
                self.assertEqual(self.external_calls(), calls)

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
            # An older checkpoint predates both outcome groups.
            if key.startswith(("contradiction_", "evidence_gap_")):
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
            "evidence_gap_followup_note_id",
            "evidence_gap_followup_input_fingerprint",
            "evidence_gap_followup_relation",
            "evidence_gap_outcome",
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

    def test_restart_resumes_accepted_source_without_refetching_it(self):
        """Acceptance persists the exact text; evidence is rebuilt, never refetched.

        Before v0.3.384 this boundary was refused. The evidence selection is a
        deterministic function of the accepted content version, which the run,
        checkpoint and knowledge index record exactly.
        """
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

        self.assertIsNotNone(execution.live_execution(snapshot.plan_id))
        self.assertIsNone(execution.restored_execution(snapshot.plan_id))
        accepted_url = snapshot.mission_checkpoint.requested_urls[0]
        fetched = [call.args[0] for call in self.fetcher.fetch.call_args_list]
        self.assertEqual(fetched.count(accepted_url), 1, fetched)
        run = JsonFileResearchRunStore(self.root / "runs.json").load()[0]
        self.assertEqual(len({source.url for source in run.sources}), len(run.sources))

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

    def review_first_note(self, run, decision="supported", supersedes=""):
        return self.controller.record_research_comparison_review(
            run.run_id,
            run.comparison_notes[0].note_id,
            decision,
            "Operator compared both quoted excerpts against the question.",
            supersedes,
        )

    def test_operator_review_supports_agreement_and_survives_restart(self):
        self.relation = "possible_agreement"
        response = self.start()
        plan_id = response.research_plan_execution.plan_id
        stop = response.research_autonomy.stop_reason.value
        snapshot = self.execution._execution_store.load()[0]
        checkpoint = snapshot.mission_checkpoint
        calls = self.external_calls()
        tentative = teaching_report(
            response.research_runs[0], stop, "Spend.", checkpoint=checkpoint
        )
        self.assertIn("Comparison review: none recorded", tentative)
        self.assertIn("Mission goal satisfaction: Unresolved", tentative)

        recorded = self.review_first_note(response.research_runs[0])

        self.assertTrue(recorded.success, recorded.message)
        run = recorded.research_runs[0]
        review = run.comparison_reviews[-1]
        self.assertEqual(review.note_id, checkpoint.semantic_note_id)
        report = teaching_report(run, stop, "Spend.", checkpoint=checkpoint)
        self.assertIn(
            "Mission goal satisfaction: Satisfied within the current bounded evidence",
            report,
        )
        self.assertIn("Ready for bounded user conclusion", report)
        self.assertIn("explicit operator comparison review marked supported", report)
        self.assertIn(f"Comparison review: operator review {review.review_id}", report)
        self.assertEqual(self.external_calls(), calls)
        self.assertEqual(self.spend(self.execution, plan_id), (12, 6, 1))
        self.assertEqual(
            plan_digest(self.execution.live_plan(plan_id)), snapshot.mission_plan_digest
        )

        engine = self.restart()

        execution = engine._research_plan_execution_service
        status = self.execution_status(engine, plan_id).message
        self.assertIn("Mission goal satisfaction: Satisfied", status)
        self.assertIn(review.review_id, status)
        stored = JsonFileResearchRunStore(self.root / "runs.json").load()[0]
        self.assertEqual(stored.comparison_reviews, run.comparison_reviews)
        self.assertEqual(self.external_calls(), calls)
        self.assertEqual(self.spend(execution, plan_id), (12, 6, 1))
        self.assertEqual(execution.mission_checkpoint(plan_id), checkpoint)

    def test_withdrawn_review_recomputes_unresolved_and_stale_review_is_refused(self):
        self.relation = "possible_agreement"
        response = self.start()
        stop = response.research_autonomy.stop_reason.value
        checkpoint = self.execution._execution_store.load()[0].mission_checkpoint
        first = self.review_first_note(response.research_runs[0])
        self.assertTrue(first.success, first.message)
        supported = first.research_runs[0]

        stale = self.review_first_note(supported, "not_supported")
        withdrawn = self.review_first_note(
            supported, "not_supported", supported.comparison_reviews[-1].review_id
        )

        self.assertFalse(stale.success)
        self.assertTrue(withdrawn.success, withdrawn.message)
        outcome = mission_outcome_for(withdrawn.research_runs[0], stop, checkpoint)
        self.assertIs(outcome.goal_satisfaction.status, GoalStatus.UNRESOLVED)
        self.assertFalse(outcome.completion_readiness.ready)

    def test_review_of_a_conflict_note_cannot_satisfy_the_goal(self):
        response = self.start()
        stop = response.research_autonomy.stop_reason.value
        checkpoint = self.execution._execution_store.load()[0].mission_checkpoint

        recorded = self.review_first_note(response.research_runs[0])

        self.assertTrue(recorded.success, recorded.message)
        outcome = mission_outcome_for(recorded.research_runs[0], stop, checkpoint)
        self.assertIs(outcome.goal_satisfaction.status, GoalStatus.UNRESOLVED)
        self.assertEqual(outcome.goal_satisfaction.supported_by_review_id, "")

    def mission_review(self, plan_id, decision, reason="Operator compared quotes."):
        """Load the mission target, preview, record exactly its args, reload."""
        target = self.controller.mission_comparison_review(plan_id)
        self.assertTrue(target.success, target.message)
        preview = mission_comparison_review_preview(
            target.research_runs[0],
            plan_id,
            target.research_mission_comparison_note_id,
            decision,
            reason,
        )
        recorded = self.controller.record_research_comparison_review(*preview.arguments)
        return (
            target,
            preview,
            recorded,
            self.controller.mission_comparison_review(plan_id),
        )

    def durable_state(self, plan_id):
        return (
            self.external_calls(),
            self.spend(self.execution, plan_id),
            self.execution.mission_checkpoint(plan_id),
            plan_digest(self.execution.live_plan(plan_id)),
            self.execution.live_plan(plan_id).mission_scope,
            self.execution.live_execution(plan_id),
        )

    def test_mission_review_target_binds_checkpoint_note_and_writes_nothing(self):
        self.relation = "possible_agreement"
        response = self.start()
        plan_id = response.research_plan_execution.plan_id
        checkpoint = self.execution.mission_checkpoint(plan_id)
        state = self.durable_state(plan_id)
        runs = (self.root / "runs.json").read_bytes()

        target = self.controller.mission_comparison_review(plan_id)
        preview = mission_comparison_review_preview(
            target.research_runs[0],
            plan_id,
            target.research_mission_comparison_note_id,
            "supported",
            "Both excerpts answer the question.",
        )

        note = next(
            value
            for value in target.research_runs[0].comparison_notes
            if value.note_id == checkpoint.semantic_note_id
        )
        self.assertEqual(
            target.research_mission_comparison_note_id, checkpoint.semantic_note_id
        )
        self.assertEqual(
            target.research_runs[0].run_id, response.research_runs[0].run_id
        )
        self.assertIn("Mission goal satisfaction: Unresolved", target.message)
        self.assertIn(f"Evidence IDs: {', '.join(note.evidence_ids)}", preview.text)
        self.assertIn(f"Research run: {response.research_runs[0].run_id}", preview.text)
        self.assertIn("Current review: none recorded", preview.text)
        self.assertIn("Proposed decision: supported", preview.text)
        self.assertEqual(
            preview.arguments,
            (
                response.research_runs[0].run_id,
                checkpoint.semantic_note_id,
                "supported",
                "Both excerpts answer the question.",
                "",
            ),
        )
        # Loading and previewing write nothing and spend nothing.
        self.assertEqual((self.root / "runs.json").read_bytes(), runs)
        self.assertEqual(self.durable_state(plan_id), state)

    def test_mission_review_supports_then_revokes_through_canonical_refresh(self):
        self.relation = "possible_agreement"
        response = self.start()
        plan_id = response.research_plan_execution.plan_id
        state = self.durable_state(plan_id)
        run = response.research_runs[0]

        _, _, recorded, refreshed = self.mission_review(plan_id, "supported")

        self.assertTrue(recorded.success, recorded.message)
        review = refreshed.research_runs[0].comparison_reviews[-1]
        self.assertIn(
            "Mission goal satisfaction: Satisfied within the current bounded evidence",
            refreshed.message,
        )
        self.assertIn("Ready for bounded user conclusion", refreshed.message)
        self.assertIn(f"operator review {review.review_id}", refreshed.message)

        _, preview, revoked, after = self.mission_review(plan_id, "not_supported")

        self.assertTrue(revoked.success, revoked.message)
        self.assertEqual(preview.arguments[4], review.review_id)
        self.assertIn(f"Current review: {review.review_id}", preview.text)
        final = after.research_runs[0]
        self.assertEqual(
            final.comparison_reviews[-1].supersedes_review_id, review.review_id
        )
        self.assertIn("Mission goal satisfaction: Unresolved", after.message)
        self.assertIn("Mission completion readiness: Not ready", after.message)
        self.assertEqual(self.durable_state(plan_id), state)
        self.assertEqual(
            (final.status, final.claims, final.evidence, final.assessments),
            (run.status, run.claims, run.evidence, run.assessments),
        )

    def test_stale_mission_review_is_refused_and_reload_shows_current(self):
        self.relation = "possible_agreement"
        response = self.start()
        plan_id = response.research_plan_execution.plan_id
        target = self.controller.mission_comparison_review(plan_id)
        stale = mission_comparison_review_preview(
            target.research_runs[0],
            plan_id,
            target.research_mission_comparison_note_id,
            "supported",
            "Stale view.",
        )
        _, _, first, _ = self.mission_review(plan_id, "not_supported")
        self.assertTrue(first.success, first.message)

        refused = self.controller.record_research_comparison_review(*stale.arguments)
        reloaded = self.controller.mission_comparison_review(plan_id)

        self.assertFalse(refused.success)
        reviews = reloaded.research_runs[0].comparison_reviews
        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0].decision.value, "not_supported")
        self.assertIn("Mission goal satisfaction: Unresolved", reloaded.message)

    def test_review_of_non_mission_note_never_satisfies_the_mission(self):
        response = self.start()
        plan_id = response.research_plan_execution.plan_id
        checkpoint = self.execution.mission_checkpoint(plan_id)
        run = response.research_runs[0]
        others = [
            n for n in run.comparison_notes if n.note_id != checkpoint.semantic_note_id
        ]
        self.assertTrue(others)
        target = self.controller.mission_comparison_review(plan_id)
        self.assertEqual(
            target.research_mission_comparison_note_id, checkpoint.semantic_note_id
        )
        for note in others:
            recorded = self.controller.record_research_comparison_review(
                run.run_id, note.note_id, "supported", "Other note.", ""
            )
            self.assertTrue(recorded.success, recorded.message)
        _, _, recorded, refreshed = self.mission_review(plan_id, "supported")

        # The mission's own conflict note is not lifted by any review either.
        self.assertTrue(recorded.success, recorded.message)
        self.assertIn("Mission goal satisfaction: Unresolved", refreshed.message)
        self.assertNotIn("Ready for bounded user conclusion", refreshed.message)

    def test_not_comparable_mission_review_is_not_lifted(self):
        self.relation = "not_comparable"
        response = self.start()
        plan_id = response.research_plan_execution.plan_id

        target, _, recorded, refreshed = self.mission_review(plan_id, "supported")

        if target.research_mission_comparison_note_id:
            self.assertTrue(recorded.success, recorded.message)
        self.assertIn("Mission goal satisfaction: Unresolved", refreshed.message)
        self.assertNotIn("Ready for bounded user conclusion", refreshed.message)

    def test_empty_proposal_gap_review_target_is_not_lifted(self):
        self.empty_proposals()
        response = self.start()
        plan_id = response.research_plan_execution.plan_id

        target = self.controller.mission_comparison_review(plan_id)

        self.assertTrue(target.success, target.message)
        self.assertIn("Mission goal satisfaction: Unresolved", target.message)
        if not target.research_mission_comparison_note_id:
            with self.assertRaisesRegex(ValueError, "no recorded comparison note"):
                mission_comparison_review_preview(
                    target.research_runs[0], plan_id, "", "supported", "Reason."
                )

    def test_closed_run_refuses_mission_review_without_goal_change(self):
        self.relation = "possible_agreement"
        response = self.start()
        plan_id = response.research_plan_execution.plan_id
        target = self.controller.mission_comparison_review(plan_id)
        preview = mission_comparison_review_preview(
            target.research_runs[0],
            plan_id,
            target.research_mission_comparison_note_id,
            "supported",
            "Reason.",
        )
        manager = self.bootstrap.container.resolve(ResearchRunManager)
        manager.transition_status(
            target.research_runs[0].run_id, ResearchRunStatus.COMPLETED
        )

        refused = self.controller.record_research_comparison_review(*preview.arguments)
        reloaded = self.controller.mission_comparison_review(plan_id)

        self.assertFalse(refused.success)
        self.assertEqual(reloaded.research_runs[0].comparison_reviews, ())
        with self.assertRaisesRegex(ValueError, "closed"):
            mission_comparison_review_preview(
                reloaded.research_runs[0],
                plan_id,
                reloaded.research_mission_comparison_note_id,
                "supported",
                "Reason.",
            )

    def test_unknown_or_restored_unresumed_plan_loads_no_review_target(self):
        missing = self.controller.mission_comparison_review("plan-missing")

        self.assertFalse(missing.success)
        self.assertEqual(missing.research_runs, [])
        self.assertEqual(missing.research_mission_comparison_note_id, "")

    def test_recovered_mission_review_binds_same_run_and_note_after_restart(self):
        self.relation = "possible_agreement"
        snapshot = self.interrupted_start(6)
        engine = self.restart()
        controller = DesktopController(self.restarted.container.resolve(Brain))
        calls = self.external_calls()
        execution = engine._research_plan_execution_service
        checkpoint = execution.mission_checkpoint(snapshot.plan_id)
        spend = self.spend(execution, snapshot.plan_id)

        target = controller.mission_comparison_review(snapshot.plan_id)

        self.assertTrue(target.success, target.message)
        self.assertEqual(target.research_runs[0].run_id, snapshot.research_run_id)
        self.assertEqual(
            target.research_mission_comparison_note_id, checkpoint.semantic_note_id
        )
        preview = mission_comparison_review_preview(
            target.research_runs[0],
            snapshot.plan_id,
            target.research_mission_comparison_note_id,
            "supported",
            "Recovered review.",
        )
        recorded = controller.record_research_comparison_review(*preview.arguments)
        refreshed = controller.mission_comparison_review(snapshot.plan_id)

        self.assertTrue(recorded.success, recorded.message)
        self.assertIn("Ready for bounded user conclusion", refreshed.message)
        self.assertEqual(self.external_calls(), calls)
        self.assertEqual(self.spend(execution, snapshot.plan_id), spend)
        self.assertEqual(execution.mission_checkpoint(snapshot.plan_id), checkpoint)

        again = self.restart()
        status = self.execution_status(again, snapshot.plan_id)
        stored = JsonFileResearchRunStore(self.root / "runs.json").load()[0]
        self.assertEqual(
            stored.comparison_reviews, refreshed.research_runs[0].comparison_reviews
        )
        self.assertEqual(self.external_calls(), calls)
        self.assertIsNotNone(status)

    def execution_store_path(self):
        return self.execution._execution_store._path

    def stored_snapshot(self, plan_id):
        return next(
            snapshot
            for snapshot in self.execution._execution_store.load()
            if snapshot.plan_id == plan_id
        )

    def durable_files(self):
        return {
            path.name: path.read_bytes()
            for path in self.root.rglob("*.json")
            if path.is_file()
        }

    def restored_controller(self, **kwargs):
        engine = self.restart(**kwargs) if kwargs else self.deferred_restart()
        return engine, DesktopController(self.restarted.container.resolve(Brain))

    def test_completed_mission_durably_records_its_typed_stop_reason(self):
        self.relation = "possible_agreement"
        response = self.start()
        plan_id = response.research_plan_execution.plan_id

        snapshot = self.stored_snapshot(plan_id)

        self.assertIs(
            snapshot.mission_stop_reason,
            AutonomyStopReason(response.research_autonomy.stop_reason.value),
        )
        document = json.loads(self.execution_store_path().read_text("utf-8"))
        self.assertEqual(
            document["executions"][0]["mission_stop_reason"],
            response.research_autonomy.stop_reason.value,
        )
        # Typed execution metadata only: no rendered report prose is persisted.
        self.assertNotIn("Mission goal satisfaction", json.dumps(document))

    def test_fresh_restart_without_resume_reconstructs_the_same_report(self):
        self.relation = "possible_agreement"
        response = self.start()
        plan_id = response.research_plan_execution.plan_id
        before = self.controller.mission_comparison_review(plan_id)
        snapshot = self.stored_snapshot(plan_id)
        calls = self.external_calls()
        files = self.durable_files()

        engine, controller = self.restored_controller()
        first = controller.mission_comparison_review(plan_id)
        second = controller.mission_comparison_review(plan_id)

        execution = engine._research_plan_execution_service
        self.assertTrue(first.success, first.message)
        self.assertEqual(first.message, before.message)
        self.assertEqual(second.message, first.message)
        self.assertEqual(
            first.research_mission_comparison_note_id,
            before.research_mission_comparison_note_id,
        )
        # Nothing was resumed, executed, spent, called, reviewed or retained.
        self.assertIsNone(execution.live_execution(plan_id))
        self.assertEqual(execution.restored_execution(plan_id), snapshot)
        self.assertEqual(self.external_calls(), calls)
        self.assertEqual(self.durable_files(), files)
        self.assertEqual(first.research_runs[0].comparison_reviews, ())

    def test_fresh_restart_enables_mission_review_without_resuming(self):
        self.relation = "possible_agreement"
        response = self.start()
        plan_id = response.research_plan_execution.plan_id
        snapshot = self.stored_snapshot(plan_id)
        calls = self.external_calls()

        engine, controller = self.restored_controller()
        target = controller.mission_comparison_review(plan_id)
        preview = mission_comparison_review_preview(
            target.research_runs[0],
            plan_id,
            target.research_mission_comparison_note_id,
            "supported",
            "Reviewed after restart.",
        )
        recorded = controller.record_research_comparison_review(*preview.arguments)
        refreshed = controller.mission_comparison_review(plan_id)
        revoked_preview = mission_comparison_review_preview(
            refreshed.research_runs[0],
            plan_id,
            refreshed.research_mission_comparison_note_id,
            "not_supported",
            "Withdrawn after restart.",
        )
        revoked = controller.record_research_comparison_review(
            *revoked_preview.arguments
        )
        revoked_report = controller.mission_comparison_review(plan_id)

        execution = engine._research_plan_execution_service
        self.assertTrue(recorded.success, recorded.message)
        self.assertEqual(
            target.research_mission_comparison_note_id,
            snapshot.mission_checkpoint.semantic_note_id,
        )
        self.assertIn(
            "Mission goal satisfaction: Satisfied within the current bounded evidence",
            refreshed.message,
        )
        self.assertIn("Ready for bounded user conclusion", refreshed.message)
        self.assertTrue(revoked.success, revoked.message)
        self.assertIn("Mission goal satisfaction: Unresolved", revoked_report.message)
        self.assertIn("Mission completion readiness: Not ready", revoked_report.message)
        self.assertEqual(self.external_calls(), calls)
        self.assertIsNone(execution.live_execution(plan_id))
        self.assertEqual(execution.restored_execution(plan_id), snapshot)
        self.assertEqual(self.stored_snapshot(plan_id), snapshot)

    def test_refused_recovery_keeps_durable_stop_and_same_report(self):
        response = self.start()
        plan_id = response.research_plan_execution.plan_id
        before = self.controller.mission_comparison_review(plan_id)
        calls = self.external_calls()

        engine, controller = self.restored_controller(endpoint="http://127.0.0.1:9/v1")
        target = controller.mission_comparison_review(plan_id)

        self.assertIsNotNone(
            engine._research_plan_execution_service.restored_execution(plan_id)
        )
        self.assertTrue(target.success, target.message)
        self.assertEqual(target.message, before.message)
        self.assertIn("Mission goal satisfaction: Unresolved", target.message)
        self.assertEqual(self.external_calls(), calls)

    def test_legacy_snapshot_without_stop_reason_refuses_mission_report(self):
        self.relation = "possible_agreement"
        response = self.start()
        plan_id = response.research_plan_execution.plan_id
        path = self.execution_store_path()
        document = json.loads(path.read_text("utf-8"))
        for execution in document["executions"]:
            execution.pop("mission_stop_reason", None)
        path.write_text(json.dumps(document), encoding="utf-8")
        files = self.durable_files()

        engine, controller = self.restored_controller()
        target = controller.mission_comparison_review(plan_id)

        restored = engine._research_plan_execution_service.restored_execution(plan_id)
        self.assertIsNone(restored.mission_stop_reason)
        self.assertFalse(target.success)
        self.assertEqual(target.research_runs, [])
        self.assertEqual(self.durable_files(), files)

    def test_unknown_stop_reason_fails_closed_on_load(self):
        self.relation = "possible_agreement"
        self.start()
        path = self.execution_store_path()
        document = json.loads(path.read_text("utf-8"))
        document["executions"][0]["mission_stop_reason"] = "goal_satisfied"
        path.write_text(json.dumps(document), encoding="utf-8")

        with self.assertRaises(ResearchError):
            JsonFileResearchExecutionStore(path).load()

    def assert_stop_survives_fresh_restart(self, response, stop):
        plan_id = response.research_plan_execution.plan_id
        before = self.controller.mission_comparison_review(plan_id)
        calls = self.external_calls()

        self.assertEqual(response.research_autonomy.stop_reason.value, stop)
        self.assertEqual(self.stored_snapshot(plan_id).mission_stop_reason.value, stop)
        _, controller = self.restored_controller()
        after = controller.mission_comparison_review(plan_id)

        self.assertTrue(after.success, after.message)
        self.assertEqual(after.message, before.message)
        self.assertIn(f"Stop reason: {stop}", after.message)
        self.assertNotIn("Ready for bounded user conclusion", after.message)
        self.assertEqual(self.external_calls(), calls)

    def test_cancelled_mission_keeps_its_actual_stop_reason(self):
        signal = CancellationSignal()

        def cancelled(*args):
            result = self.answer(*args)
            signal.cancel()
            return result

        self.transport.side_effect = cancelled
        response = self.start(cancellation_token=signal)

        self.assert_stop_survives_fresh_restart(response, "cancelled")

    def test_failed_mission_keeps_its_actual_stop_reason(self):
        self.fetcher.fetch.side_effect = ResearchError("fixture unavailable")
        response = self.start()

        self.assert_stop_survives_fresh_restart(response, "step_failed")

    def test_stop_reason_codec_is_typed_and_bound_to_mission_state(self):
        self.relation = "possible_agreement"
        response = self.start()
        snapshot = self.stored_snapshot(response.research_plan_execution.plan_id)
        document = encode_execution_snapshot(snapshot)

        self.assertEqual(decode_execution_snapshot(document), snapshot)
        legacy = dict(document)
        legacy.pop("mission_stop_reason")
        self.assertIsNone(decode_execution_snapshot(legacy).mission_stop_reason)
        for value in ("", "satisfied", None, 3):
            with self.subTest(value=value), self.assertRaises(ResearchError):
                decode_execution_snapshot({**document, "mission_stop_reason": value})
        non_mission = {
            key: value
            for key, value in document.items()
            if key
            not in {
                "mission_scope",
                "mission_disclosure",
                "mission_checkpoint",
                "mission_plan_digest",
                "mission_request_id",
            }
        }
        with self.assertRaises(ResearchError):
            decode_execution_snapshot(non_mission)
        with self.assertRaises(ResearchError):
            replace(
                snapshot,
                mission_scope=None,
                mission_disclosure=ResearchDisclosure.NONE,
                mission_checkpoint=None,
                mission_request_id=None,
            )
        with self.assertRaises(ResearchError):
            replace(snapshot, mission_stop_reason="research_deliverable_ready")
        running = replace(
            snapshot,
            steps=(
                replace(snapshot.steps[0], status=ResearchPlanStepStatus.RUNNING),
                *snapshot.steps[1:],
            ),
        )
        self.assertIsNone(running.restored().mission_stop_reason)

    def audit_preview(self, controller, plan_id):
        response = controller.preview_mission_audit_export(plan_id)
        self.assertTrue(response.success, response.message)
        return response.research_mission_audit_export_preview

    def audit_documents(self, controller, plan_id):
        """Save one previewed audit to a fresh directory and load both files."""
        preview = self.audit_preview(controller, plan_id)
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        saved = controller.save_mission_audit_export(preview, str(directory))
        self.assertTrue(saved.success, saved.message)
        result = saved.research_mission_audit_export_result
        markdown = Path(result.markdown_path).read_text("utf-8")
        document = json.loads(Path(result.json_path).read_text("utf-8"))
        return preview, markdown, document

    def test_mission_audit_bundle_carries_canonical_mission_state(self):
        self.relation = "possible_agreement"
        response = self.start()
        plan_id = response.research_plan_execution.plan_id
        run = response.research_runs[0]
        first = self.review_first_note(run)
        withdrawn = self.review_first_note(
            first.research_runs[0],
            "not_supported",
            first.research_runs[0].comparison_reviews[-1].review_id,
        )
        self.assertTrue(withdrawn.success, withdrawn.message)
        supported = self.review_first_note(
            withdrawn.research_runs[0],
            "supported",
            withdrawn.research_runs[0].comparison_reviews[-1].review_id,
        )
        self.assertTrue(supported.success, supported.message)
        reviews = supported.research_runs[0].comparison_reviews
        checkpoint = self.execution.mission_checkpoint(plan_id)
        allowance = self.execution.allowance(plan_id)
        authorization = self.approvals.authorization_for_execution(plan_id)
        calls = self.external_calls()
        state_files = self.durable_files()
        mission = self.mission_state(response)

        preview, markdown, document = self.audit_documents(self.controller, plan_id)

        # Identity, plan and authority come from the canonical records.
        self.assertEqual(document["schema"], "hypatia.mission_audit")
        self.assertEqual(document["schema_version"], 3)
        self.assertEqual(document["identity"]["plan_id"], plan_id)
        self.assertEqual(document["identity"]["research_run_id"], run.run_id)
        self.assertEqual(
            document["plan"]["mission_plan_digest"],
            self.stored_snapshot(plan_id).mission_plan_digest,
        )
        self.assertEqual(
            [step["capability"] for step in document["plan"]["capability_order"]],
            [step.capability.value for step in self.execution.live_plan(plan_id).steps],
        )
        self.assertEqual(
            document["authority"]["authorization_id"], authorization.authorization_id
        )
        self.assertEqual(document["authority"]["consumption"]["execution_id"], plan_id)
        self.assertEqual(
            document["budget"]["spent"],
            {
                "step_advances": allowance.spend.step_advances,
                "network_operations": allowance.spend.network_operations,
                "llm_operations": allowance.spend.llm_operations,
                "active_seconds": allowance.spend.active_seconds,
            },
        )
        self.assertEqual(
            document["budget"]["remaining"]["llm_operations"],
            allowance.remaining_llm_operations,
        )
        stop = response.research_autonomy.stop_reason.value
        self.assertEqual(document["execution"]["stop_reason"], stop)
        self.assertEqual(
            document["execution"]["snapshot"]["mission_checkpoint"]["semantic_note_id"],
            checkpoint.semantic_note_id,
        )
        # Evaluation is recomputed by the existing functions, not re-derived.
        outcome = mission_outcome_for(supported.research_runs[0], stop, checkpoint)
        evaluation = document["evaluation"]
        self.assertEqual(
            evaluation["goal_satisfaction"]["status"],
            outcome.goal_satisfaction.status.value,
        )
        self.assertEqual(evaluation["goal_satisfaction"]["status"], "satisfied")
        self.assertEqual(
            evaluation["goal_satisfaction"]["supported_by_review_id"],
            reviews[-1].review_id,
        )
        self.assertEqual(evaluation["completion_readiness"]["status"], "ready")
        self.assertEqual(
            document["teaching_report"],
            teaching_report(
                supported.research_runs[0],
                stop,
                self.controller.mission_comparison_review(plan_id)
                .message.split("Stop reason: ", 1)[1]
                .split(". ", 1)[1]
                .split("\n", 1)[0],
                checkpoint=checkpoint,
            ),
        )
        # Review history is traceable to exact note, evidence and sources.
        trace = document["traceability"]
        self.assertEqual(
            trace["mission_comparison_note_id"], checkpoint.semantic_note_id
        )
        self.assertEqual(trace["mission_comparison_review_id"], reviews[-1].review_id)
        note = next(
            n
            for n in supported.research_runs[0].comparison_notes
            if n.note_id == checkpoint.semantic_note_id
        )
        self.assertEqual(
            [
                (
                    entry["decision"],
                    entry["current"],
                    entry["supersedes_review_id"],
                    entry["note_id"],
                    entry["evidence_ids"],
                    entry["source_document_ids"],
                )
                for entry in trace["comparison_reviews"]
            ],
            [
                (
                    "supported",
                    False,
                    None,
                    note.note_id,
                    list(note.evidence_ids),
                    list(note.source_document_ids),
                ),
                (
                    "not_supported",
                    False,
                    reviews[0].review_id,
                    note.note_id,
                    list(note.evidence_ids),
                    list(note.source_document_ids),
                ),
                (
                    "supported",
                    True,
                    reviews[1].review_id,
                    note.note_id,
                    list(note.evidence_ids),
                    list(note.source_document_ids),
                ),
            ],
        )
        # The trace resolves every hop through recorded IDs to this run's own
        # source observations and names the recorded basis of the goal.
        final_run = supported.research_runs[0]
        observations = {
            source.document_id: (
                source.requested_url,
                source.url,
                source.content_sha256,
            )
            for source in final_run.sources
        }
        self.assertEqual(
            {
                o["document_id"]: (o["requested_url"], o["url"], o["content_sha256"])
                for o in trace["source_observations"]
            },
            observations,
        )
        evidence_sources = {
            e.evidence_id: e.source_document_id for e in final_run.evidence
        }
        for entry in trace["comparison_reviews"]:
            self.assertEqual(
                [
                    (t["evidence_id"], t["source"]["document_id"])
                    for t in entry["evidence"]
                ],
                [(e, evidence_sources[e]) for e in entry["evidence_ids"]],
            )
            self.assertTrue(all(t["resolved"] for t in entry["evidence"]))
        basis = trace["goal_basis"]
        self.assertEqual(
            [
                (n["role"], n["note_id"], n["recorded_relation"], n["resolved"])
                for n in basis["comparison_notes"]
            ],
            [
                (
                    "mission_comparison_note",
                    checkpoint.semantic_note_id,
                    "possible_agreement",
                    True,
                )
            ],
        )
        self.assertEqual(basis["supporting_review_id"], reviews[-1].review_id)
        self.assertEqual(
            evaluation["goal_satisfaction"]["supported_by_review_id"],
            basis["supporting_review_id"],
        )
        self.assertIn("### Recorded Basis of the Goal Evaluation", markdown)
        self.assertIn("### Source Observations of This Run", markdown)
        assessment = document["research_run"]["assessments"][0]
        for key in (
            "information_trust",
            "usefulness",
            "applicability",
            "independence",
            "publication_status",
        ):
            self.assertIn(key, assessment)
        # Markdown carries the same state for a human reader.
        for text in (
            "# Mission Audit",
            f"- **Plan ID:** {plan_id}",
            f"`{document['plan']['mission_plan_digest']}`",
            f"- **Recorded approval:** {authorization.authorization_id}",
            "| Model operations |",
            f"- **Recorded stop reason:** {stop}",
            "- **Goal satisfaction:** satisfied",
            "- **Completion readiness:** ready",
            "## Teaching Report",
            "## Operator Comparison Reviews",
            "not model output and not universal truth",
            "- **Decision:** not_supported",
            f"- **Supersedes:** {reviews[0].review_id}",
        ):
            self.assertIn(text, markdown)
        self.assertEqual(preview.plan_id, plan_id)
        # Export is read-only: no calls, spend, mission, approval or store change.
        self.assertEqual(self.external_calls(), calls)
        self.assertEqual(self.durable_files(), state_files)
        self.assertEqual(self.mission_state(response), mission)
        self.assertEqual(self.execution.allowance(plan_id), allowance)
        self.assertEqual(
            self.approvals.authorization_for_execution(plan_id), authorization
        )

    def test_audit_trace_reports_unresolved_references_without_guessing(self):
        self.relation = "possible_agreement"
        response = self.start()
        plan_id = response.research_plan_execution.plan_id
        snapshot = self.execution.mission_snapshot(plan_id)
        run = response.research_runs[0]
        tampered = replace(
            snapshot,
            mission_checkpoint=replace(
                snapshot.mission_checkpoint,
                semantic_note_id="note-that-does-not-exist",
                semantic_input_fingerprint="f" * 64,
            ),
        )

        audit = build_mission_audit(tampered, run, None, hypatia_version="test")

        (note,) = audit["traceability"]["goal_basis"]["comparison_notes"]
        self.assertEqual(
            (note["note_id"], note["resolved"], note["evidence"]),
            ("note-that-does-not-exist", False, []),
        )
        self.assertIsNone(audit["traceability"]["goal_basis"]["supporting_review_id"])
        legacy = replace(
            run,
            sources=tuple(
                replace(
                    source,
                    requested_url=None,
                    content_sha256=None,
                    discovery_candidate_id=None,
                )
                for source in run.sources
            ),
        )
        observations = build_mission_audit(
            snapshot, legacy, None, hypatia_version="test"
        )["traceability"]["source_observations"]
        self.assertTrue(
            all(
                o["requested_url"] is None and o["content_sha256"] is None
                for o in observations
            )
        )
        self.assertEqual(
            mission_audit_json(
                build_mission_audit(snapshot, run, None, hypatia_version="test")
            ),
            mission_audit_json(
                build_mission_audit(snapshot, run, None, hypatia_version="test")
            ),
        )

    def test_mission_audit_preview_writes_nothing_and_is_deterministic(self):
        self.relation = "possible_agreement"
        response = self.start()
        plan_id = response.research_plan_execution.plan_id
        files = self.durable_files()

        first = self.audit_preview(self.controller, plan_id)
        second = self.audit_preview(self.controller, plan_id)

        self.assertEqual(first, second)
        self.assertEqual(self.durable_files(), files)
        self.assertEqual(
            {path.name for path in self.root.rglob("mission-audit-*")}, set()
        )
        self.assertEqual(
            (first.markdown_filename, first.json_filename),
            (f"mission-audit-{plan_id}.md", f"mission-audit-{plan_id}.json"),
        )

    def test_live_and_fresh_restart_audits_are_identical_without_resuming(self):
        self.relation = "possible_agreement"
        response = self.start()
        plan_id = response.research_plan_execution.plan_id
        live = self.audit_preview(self.controller, plan_id)
        calls = self.external_calls()

        engine, controller = self.restored_controller()
        restored = self.audit_preview(controller, plan_id)

        self.assertEqual(restored.json_sha256, live.json_sha256)
        self.assertEqual(restored.markdown_sha256, live.markdown_sha256)
        self.assertIsNone(
            engine._research_plan_execution_service.live_execution(plan_id)
        )
        self.assertEqual(self.external_calls(), calls)

    def test_mission_audit_save_refuses_stale_preview_and_existing_files(self):
        self.relation = "possible_agreement"
        response = self.start()
        plan_id = response.research_plan_execution.plan_id
        run = response.research_runs[0]
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        stale = self.audit_preview(self.controller, plan_id)
        self.assertTrue(self.review_first_note(run).success)

        refused = self.controller.save_mission_audit_export(stale, str(directory))

        self.assertFalse(refused.success)
        self.assertIn("changed since its preview", refused.message)
        self.assertEqual(list(directory.iterdir()), [])
        current = self.audit_preview(self.controller, plan_id)
        saved = self.controller.save_mission_audit_export(current, str(directory))
        self.assertTrue(saved.success, saved.message)
        self.assertEqual(
            sorted(path.name for path in directory.iterdir()),
            sorted((current.markdown_filename, current.json_filename)),
        )
        again = self.controller.save_mission_audit_export(current, str(directory))
        self.assertFalse(again.success)
        self.assertIn("already exists", again.message)

    def test_conflict_audit_keeps_outcome_unresolved_without_truth_promotion(self):
        response = self.start()
        plan_id = response.research_plan_execution.plan_id
        reviewed = self.review_first_note(response.research_runs[0])
        self.assertTrue(reviewed.success, reviewed.message)

        _, markdown, document = self.audit_documents(self.controller, plan_id)

        goal = document["evaluation"]["goal_satisfaction"]
        self.assertEqual(goal["status"], "unresolved")
        self.assertIsNone(goal["supported_by_review_id"])
        self.assertEqual(
            document["execution"]["snapshot"]["mission_checkpoint"][
                "contradiction_initial_relation"
            ],
            "possible_conflict",
        )
        self.assertNotEqual(
            document["evaluation"]["completion_readiness"]["status"], "ready"
        )
        self.assertIn("none is a verified fact", markdown)
        self.assertNotIn("Ready for bounded user conclusion:** yes", markdown)

    def test_legacy_mission_audit_marks_missing_stop_without_inference(self):
        self.relation = "possible_agreement"
        response = self.start()
        plan_id = response.research_plan_execution.plan_id
        path = self.execution_store_path()
        document = json.loads(path.read_text("utf-8"))
        for execution in document["executions"]:
            execution.pop("mission_stop_reason", None)
        path.write_text(json.dumps(document), encoding="utf-8")

        _, controller = self.restored_controller()
        _, markdown, audit = self.audit_documents(controller, plan_id)

        self.assertIsNone(audit["execution"]["stop_reason"])
        self.assertIsNone(audit["evaluation"])
        self.assertIsNone(audit["teaching_report"])
        self.assertIn("stop_reason_unrecorded", audit["limitations"])
        self.assertIn("mission_evaluation_unavailable", audit["limitations"])
        self.assertIsNotNone(audit["research_run"])
        self.assertIn("no goal status was inferred", markdown)

    def test_mission_audit_never_mixes_another_missions_run_or_reviews(self):
        self.relation = "possible_agreement"
        first = self.start()
        other_review = self.review_first_note(first.research_runs[0])
        self.assertTrue(other_review.success, other_review.message)
        second = self.start()
        self.assertNotEqual(
            second.research_runs[0].run_id, first.research_runs[0].run_id
        )

        _, markdown, document = self.audit_documents(
            self.controller, second.research_plan_execution.plan_id
        )

        self.assertEqual(
            document["research_run"]["run_id"], second.research_runs[0].run_id
        )
        self.assertEqual(document["traceability"]["comparison_reviews"], [])
        other = other_review.research_runs[0]
        self.assertNotIn(other.run_id, json.dumps(document))
        self.assertNotIn(other.comparison_reviews[0].review_id, markdown)

    def test_mission_audit_builder_refuses_foreign_records_and_credentialed_urls(self):
        self.relation = "possible_agreement"
        first = self.start()
        second = self.start()
        plan_id = first.research_plan_execution.plan_id
        snapshot = self.execution.mission_snapshot(plan_id)
        run = first.research_runs[0]
        other_authorization = self.approvals.authorization_for_execution(
            second.research_plan_execution.plan_id
        )

        audit = build_mission_audit(
            snapshot,
            run,
            self.approvals.authorization_for_execution(plan_id),
            hypatia_version="test",
        )
        self.assertEqual(mission_audit_json(audit), mission_audit_json(audit))
        self.assertEqual(json.loads(mission_audit_json(audit)), audit)
        for wrong_run, authorization in (
            (second.research_runs[0], None),
            (run, other_authorization),
        ):
            with self.subTest(), self.assertRaises(ResearchError):
                build_mission_audit(
                    snapshot, wrong_run, authorization, hypatia_version="test"
                )
        leaked = replace(
            run.sources[0], url="https://user:secret@reference0.example/study"
        )
        credentialed = replace(run, sources=(leaked, *run.sources[1:]))
        with self.assertRaisesRegex(ResearchError, "credentials"):
            build_mission_audit(snapshot, credentialed, None, hypatia_version="test")
        rendered = mission_audit_json(audit)
        for secret_marker in ("api_key", "Authorization", "headers", "password"):
            self.assertNotIn(secret_marker, rendered)

    def test_unknown_mission_audit_is_refused_without_files(self):
        response = self.controller.preview_mission_audit_export("plan-missing")

        self.assertFalse(response.success)
        self.assertIsNone(response.research_mission_audit_export_preview)

    def redirect_first_source(self):
        """The first candidate's fetch ends at a different, validated final URL."""
        requested = self.sources[0]
        final = replace(requested, url="https://mirror0.example/study")
        self.fetcher.fetch.side_effect = lambda url: (
            final
            if url == requested.url
            else next(s for s in self.sources if s.url == url)
        )
        return requested.url, final.url

    def fetched_urls(self):
        return [call.args[0] for call in self.fetcher.fetch.call_args_list]

    def test_mission_sources_record_their_selected_discovery_candidate(self):
        self.relation = "possible_agreement"
        response = self.start()
        run = response.research_runs[0]
        (discovery,) = run.discoveries

        candidate_ids = dict(
            zip(discovery.candidate_ids, discovery.candidates, strict=True)
        )

        self.assertEqual(len(set(discovery.candidate_ids)), len(discovery.candidates))
        for source in run.sources:
            selected = candidate_ids[source.discovery_candidate_id]
            self.assertEqual(selected.url, source.requested_url)

        calls = self.external_calls()
        plan_id = response.research_plan_execution.plan_id
        _, controller = self.restored_controller()
        restored = JsonFileResearchRunStore(self.root / "runs.json").load()[0]
        _, _, audit = self.audit_documents(controller, plan_id)

        # Restart neither rediscovers nor reselects: the exact links survive.
        self.assertEqual(self.external_calls(), calls)
        self.assertEqual(
            [s.discovery_candidate_id for s in restored.sources],
            [s.discovery_candidate_id for s in run.sources],
        )
        self.assertEqual(
            {
                (
                    o["document_id"],
                    o["discovery_candidate"]["candidate_id"],
                    o["discovery_candidate"]["discovery_id"],
                    o["discovery_candidate"]["url"],
                    o["requested_url"],
                )
                for o in audit["traceability"]["source_observations"]
            },
            {
                (
                    s.document_id,
                    s.discovery_candidate_id,
                    discovery.discovery_id,
                    candidate_ids[s.discovery_candidate_id].url,
                    s.requested_url,
                )
                for s in run.sources
            },
        )
        self.assertTrue(
            all(
                o["discovery_candidate"]["resolved"]
                for o in audit["traceability"]["source_observations"]
            )
        )

    def test_mission_source_records_the_requested_url_of_a_redirect(self):
        self.relation = "possible_agreement"
        requested, final = self.redirect_first_source()
        response = self.start()
        plan_id = response.research_plan_execution.plan_id
        checkpoint = self.execution.mission_checkpoint(plan_id)

        engine, controller = self.restored_controller()
        run = JsonFileResearchRunStore(self.root / "runs.json").load()[0]
        _, _, audit = self.audit_documents(controller, plan_id)

        redirected = next(s for s in run.sources if s.url == final)
        self.assertEqual(redirected.requested_url, requested)
        # Every mission source matches its checkpoint slot exactly: requested
        # URL, final URL and observed content hash.
        slots = set(
            zip(
                checkpoint.requested_urls,
                checkpoint.acquired_urls,
                checkpoint.body_hashes,
                strict=True,
            )
        )
        self.assertEqual(
            {(s.requested_url, s.url, s.content_sha256) for s in run.sources}, slots
        )
        self.assertIn(
            (requested, final),
            {(s["requested_url"], s["url"]) for s in audit["research_run"]["sources"]},
        )

    def test_redirected_source_is_not_refetched_after_restart(self):
        self.relation = "possible_agreement"
        requested, final = self.redirect_first_source()
        live = self.start()
        live_fetches = self.fetched_urls()
        self.assertEqual(live_fetches.count(requested), 1, live_fetches)
        live_sources = [s.url for s in live.research_runs[0].sources]

        self.setUp()
        self.relation = "possible_agreement"
        requested, final = self.redirect_first_source()
        snapshot = self.interrupted_start(6)
        self.assertEqual(snapshot.mission_checkpoint.acquired_urls, (final,))
        before = self.fetched_urls()
        engine = self.restart()

        after = self.fetched_urls()
        run = JsonFileResearchRunStore(self.root / "runs.json").load()[-1]
        status = self.execution_status(engine, snapshot.plan_id).message
        self.assertEqual(after.count(requested), 1, after)
        self.assertEqual(before, after[: len(before)])
        self.assertEqual(after, live_fetches, status)
        self.assertEqual([s.url for s in run.sources], live_sources, status)

    def source_fetch_state(self, execution, plan_id):
        restored = execution.restored_execution(plan_id)
        allowance = execution.allowance(plan_id) or (
            restored.allowance if restored is not None else None
        )
        run = JsonFileResearchRunStore(self.root / "runs.json").load()[-1]
        return (
            list(self.fetched_urls()),
            allowance.spend.network_operations if allowance else None,
            [source.url for source in run.sources],
            [record.evidence_id for record in run.evidence],
        )

    def test_completed_fetch_is_never_repeated_in_process_or_after_restart(self):
        self.relation = "possible_agreement"
        response = self.start()
        plan_id = response.research_plan_execution.plan_id
        state = self.source_fetch_state(self.execution, plan_id)
        self.assertEqual(len(state[0]), len(set(state[0])))
        audit = self.audit_preview(self.controller, plan_id)

        again = self.engine.process(
            BrainRequest(
                message="advance",
                metadata={
                    "intent": "research_plan_execution_advance",
                    "research_plan_id": plan_id,
                },
            )
        )
        self.assertFalse(again.success)
        self.assertEqual(self.source_fetch_state(self.execution, plan_id), state)

        engine = self.restart()
        controller = DesktopController(self.restarted.container.resolve(Brain))
        execution = engine._research_plan_execution_service
        self.assertEqual(self.source_fetch_state(execution, plan_id), state)
        restored_audit = self.audit_preview(controller, plan_id)
        self.assertEqual(restored_audit.json_sha256, audit.json_sha256)

    def test_failed_fetch_is_not_retried_after_restart(self):
        self.fetcher.fetch.side_effect = ResearchError("fixture unavailable")
        response = self.start()
        plan_id = response.research_plan_execution.plan_id
        state = self.source_fetch_state(self.execution, plan_id)
        self.assertEqual(len(state[0]), 1)
        failures = JsonFileResearchRunStore(self.root / "runs.json").load()[-1].failures

        engine = self.restart()

        execution = engine._research_plan_execution_service
        self.assertEqual(self.source_fetch_state(execution, plan_id), state)
        self.assertEqual(execution.restored_execution(plan_id).status.value, "failed")
        self.assertEqual(
            JsonFileResearchRunStore(self.root / "runs.json").load()[-1].failures,
            failures,
        )
        self.transport.assert_not_called()

    def interrupted_fetch_start(self):
        """Die inside the first network fetch, after the attempt was recorded."""

        def crash(url):
            raise RuntimeError("simulated process death during fetch")

        self.fetcher.fetch.side_effect = crash
        with self.assertRaisesRegex(RuntimeError, "simulated process death"):
            self.start()
        snapshot = self.execution._execution_store.load()[-1]
        running = [s for s in snapshot.steps if s.status.value == "running"]
        self.assertEqual([s.capability.value for s in running], ["source_fetch"])
        return snapshot

    def advance(self, engine, plan_id):
        return engine.process(
            BrainRequest(
                message="advance",
                metadata={
                    "intent": "research_plan_execution_advance",
                    "research_plan_id": plan_id,
                },
            )
        )

    def test_interrupted_fetch_is_never_replayed_after_restart(self):
        self.relation = "possible_agreement"
        snapshot = self.interrupted_fetch_start()
        self.fetcher.fetch.side_effect = lambda url: next(
            s for s in self.sources if s.url == url
        )
        fetches = self.fetched_urls()

        engine = self.restart()
        execution = engine._research_plan_execution_service

        # The attempt may have reached the network; nothing proves otherwise, so
        # recovery keeps it charged and interrupted and never fetches again.
        self.assertEqual(self.fetched_urls(), fetches)
        live = execution.live_execution(snapshot.plan_id)
        self.assertIsNotNone(live)
        interrupted = next(s for s in live.steps if s.status.value == "interrupted")
        self.assertEqual(
            execution.allowance(snapshot.plan_id).spend, snapshot.allowance.spend
        )
        self.assertEqual(
            execution.mission_stop_reason(snapshot.plan_id).value, "step_interrupted"
        )
        refused = self.advance(engine, snapshot.plan_id)
        self.assertFalse(refused.success)
        self.assertIn("outcome is unknown", refused.message)
        self.assertEqual(self.fetched_urls(), fetches)

        # Recovery now reaches the existing explicit authority: an operator rules
        # the attempt never happened, and the next advance is an ordinary,
        # newly charged attempt.
        ruled = engine.process(
            BrainRequest(
                message="resolve",
                metadata={
                    "intent": "research_plan_execution_resolve",
                    "research_plan_id": snapshot.plan_id,
                    "step_id": interrupted.step_id,
                    "resolution": "not_performed",
                },
            )
        )
        self.assertTrue(ruled.success, ruled.message)
        self.assertEqual(self.fetched_urls(), fetches)
        retried = self.advance(engine, snapshot.plan_id)
        self.assertTrue(retried.success, retried.message)
        self.assertEqual(len(self.fetched_urls()), len(fetches) + 1)
        self.assertEqual(
            execution.allowance(snapshot.plan_id).spend.network_operations,
            snapshot.allowance.spend.network_operations + 1,
        )

    def test_mission_stopped_after_discovery_resumes_like_a_live_mission(self):
        self.relation = "possible_agreement"
        live = self.start()
        live_fetches = self.fetched_urls()
        live_spend = self.spend(self.execution, live.research_plan_execution.plan_id)

        self.setUp()
        self.relation = "possible_agreement"
        snapshot = self.interrupted_start(2)
        self.assertEqual(snapshot.mission_checkpoint.evidence_ids, ())
        self.assertEqual(self.fetched_urls(), [])
        engine = self.restart()

        execution = engine._research_plan_execution_service
        self.assertIsNone(execution.restored_execution(snapshot.plan_id))
        self.assertEqual(self.fetched_urls(), live_fetches)
        self.assertEqual(self.spend(execution, snapshot.plan_id), live_spend)
        self.assertEqual(
            execution.mission_stop_reason(snapshot.plan_id).value,
            live.research_autonomy.stop_reason.value,
        )

    def live_totals(self, relation):
        self.relation = relation
        live = self.start()
        plan_id = live.research_plan_execution.plan_id
        totals = (
            self.fetcher.fetch.call_count,
            self.transport.call_count,
            self.provider.discover.call_count,
            self.spend(self.execution, plan_id),
            live.research_autonomy.stop_reason.value,
        )
        self.setUp()
        self.relation = relation
        return totals

    def test_mission_stopped_before_discovery_resumes_like_a_live_mission(self):
        for relation in ("possible_agreement", "possible_conflict"):
            with self.subTest(relation=relation):
                live = self.live_totals(relation)
                snapshot = self.interrupted_start(1)
                self.assertEqual(snapshot.mission_checkpoint.discovery_id, "")
                self.assertEqual(self.provider.discover.call_count, 0)

                engine = self.restart()

                execution = engine._research_plan_execution_service
                resumed = (
                    self.fetcher.fetch.call_count,
                    self.transport.call_count,
                    self.provider.discover.call_count,
                    self.spend(execution, snapshot.plan_id),
                    execution.mission_stop_reason(snapshot.plan_id).value,
                )
                # Same work, spend and outcome as live; the conflict branch runs
                # its pre-authorized third-source follow-up exactly once.
                self.assertEqual(resumed, live)
                _, _, audit = self.audit_documents(
                    DesktopController(self.restarted.container.resolve(Brain)),
                    snapshot.plan_id,
                )
                self.assertEqual(
                    audit["budget"]["spent"]["network_operations"], live[3][1]
                )

                calls = self.external_calls()
                again = self.restart()
                self.assertEqual(self.external_calls(), calls)
                self.assertEqual(
                    again._research_plan_execution_service.mission_stop_reason(
                        snapshot.plan_id
                    ).value,
                    live[4],
                )
                release_all()
                self.setUp()

    def test_mission_stopped_after_acceptance_resumes_from_accepted_content(self):
        # Step 4, 8 and 14 each end with a source accepted but its evidence not
        # yet recorded: the first slot, the second slot and the follow-up slot.
        for relation, boundary in (
            ("possible_agreement", 4),
            ("possible_agreement", 8),
            ("possible_conflict", 14),
        ):
            with self.subTest(relation=relation, boundary=boundary):
                live = self.live_totals(relation)
                snapshot = self.interrupted_start(boundary)
                fetched_before = self.fetcher.fetch.call_count

                engine = self.restart()

                execution = engine._research_plan_execution_service
                resumed = (
                    self.fetcher.fetch.call_count,
                    self.transport.call_count,
                    self.provider.discover.call_count,
                    self.spend(execution, snapshot.plan_id),
                    execution.mission_stop_reason(snapshot.plan_id).value,
                )
                # The accepted source is never fetched again; everything after it
                # matches the live mission, with no extra slot, call or spend.
                self.assertEqual(resumed, live)
                self.assertGreaterEqual(self.fetcher.fetch.call_count, fetched_before)
                run = JsonFileResearchRunStore(self.root / "runs.json").load()[-1]
                self.assertEqual(len(run.sources), live[0])
                self.assertEqual(
                    len({e.source_document_id for e in run.evidence}), len(run.sources)
                )
                calls = self.external_calls()
                self.restart()
                self.assertEqual(self.external_calls(), calls)
                release_all()
                self.setUp()

    def test_accepted_source_boundary_without_recorded_identities_is_refused(self):
        self.relation = "possible_conflict"
        snapshot = self.interrupted_start(14)
        path = self.execution_store_path()
        document = json.loads(path.read_text("utf-8"))
        for execution in document["executions"]:
            execution["mission_checkpoint"].pop("requested_urls")
        path.write_text(json.dumps(document), encoding="utf-8")
        calls = self.external_calls()

        engine = self.restart()

        self.assertEqual(self.external_calls(), calls)
        self.assertIsNotNone(
            engine._research_plan_execution_service.restored_execution(snapshot.plan_id)
        )
        self.assertIn(
            "accepted source lacks its durable evidence checkpoint",
            self.recovered_listing(engine).message,
        )

    def test_accepted_source_boundary_with_tampered_body_hash_is_refused(self):
        self.relation = "possible_agreement"
        snapshot = self.interrupted_start(8)
        path = self.execution_store_path()
        document = json.loads(path.read_text("utf-8"))
        for execution in document["executions"]:
            execution["mission_checkpoint"]["body_hashes"][-1] = "0" * 64
        path.write_text(json.dumps(document), encoding="utf-8")
        calls = self.external_calls()

        engine = self.restart()

        self.assertEqual(self.external_calls(), calls)
        self.assertIsNone(
            engine._research_plan_execution_service.live_execution(snapshot.plan_id)
        )
        self.assertIn(
            "accepted source lacks its durable evidence checkpoint",
            self.recovered_listing(engine).message,
        )

    def test_checkpoint_without_discovery_but_later_state_is_still_refused(self):
        self.relation = "possible_agreement"
        snapshot = self.interrupted_start(2)
        path = self.execution_store_path()
        document = json.loads(path.read_text("utf-8"))
        for execution in document["executions"]:
            execution["mission_checkpoint"]["discovery_id"] = ""
        path.write_text(json.dumps(document), encoding="utf-8")
        calls = self.external_calls()

        engine = self.restart()

        self.assertEqual(self.external_calls(), calls)
        self.assertIsNotNone(
            engine._research_plan_execution_service.restored_execution(snapshot.plan_id)
        )
        self.assertIn(
            "Mission discovery checkpoint is unavailable",
            self.recovered_listing(engine).message,
        )

    def test_exhausted_budget_before_discovery_refuses_without_provider_call(self):
        self.relation = "possible_agreement"
        snapshot = self.interrupted_start(1)
        path = self.execution_store_path()
        document = json.loads(path.read_text("utf-8"))
        for execution in document["executions"]:
            spend = execution["allowance"]["spend"]
            spend["network_operations"] = execution["allowance"]["budget"][
                "max_network_operations"
            ]
        path.write_text(json.dumps(document), encoding="utf-8")

        engine = self.restart()

        execution = engine._research_plan_execution_service
        self.assertEqual(self.provider.discover.call_count, 0)
        self.assertEqual(self.fetcher.fetch.call_count, 0)
        self.assertEqual(
            execution.mission_stop_reason(snapshot.plan_id).value,
            "network_budget_exhausted",
        )

    def test_checkpoint_without_evidence_but_later_state_is_refused(self):
        self.relation = "possible_agreement"
        snapshot = self.interrupted_start(6)
        path = self.execution_store_path()
        document = json.loads(path.read_text("utf-8"))
        for execution in document["executions"]:
            execution["mission_checkpoint"]["evidence_ids"] = []
            execution["mission_checkpoint"]["assessment_ids"] = []
        path.write_text(json.dumps(document), encoding="utf-8")
        fetches = self.fetched_urls()

        engine = self.restart()

        self.assertEqual(self.fetched_urls(), fetches)
        self.assertIsNotNone(
            engine._research_plan_execution_service.restored_execution(snapshot.plan_id)
        )
        self.assertIn(
            "Mission evidence changed or is missing",
            self.recovered_listing(engine).message,
        )

    def runs_by_id(self):
        return {
            run.run_id: run
            for run in JsonFileResearchRunStore(self.root / "runs.json").load()
        }

    def test_second_mission_accepts_its_own_changed_fetch_of_an_indexed_url(self):
        self.relation = "possible_agreement"
        first = self.start()
        first_run = first.research_runs[0]
        self.assertTrue(first_run.evidence)
        self.sources = [
            replace(
                source,
                content=source.content.replace("in study", "in revised study"),
            )
            for source in self.sources
        ]

        second = self.start()

        second_run = second.research_runs[0]
        self.assertTrue(second_run.sources, second.message)
        self.assertTrue(second_run.evidence, second.message)
        shared_urls = {s.url for s in first_run.sources} & {
            s.url for s in second_run.sources
        }
        self.assertTrue(shared_urls)
        for url in shared_urls:
            old = next(s for s in first_run.sources if s.url == url)
            new = next(s for s in second_run.sources if s.url == url)
            self.assertNotEqual(old.document_id, new.document_id)
            self.assertNotEqual(old.content_sha256, new.content_sha256)
        self.assertTrue(all("revised study" in e.excerpt for e in second_run.evidence))
        stored = self.runs_by_id()
        # The first mission's observations and evidence are untouched.
        self.assertEqual(stored[first_run.run_id].sources, first_run.sources)
        self.assertEqual(stored[first_run.run_id].evidence, first_run.evidence)
        self.assertTrue(
            all("revised" not in e.excerpt for e in stored[first_run.run_id].evidence)
        )

        calls = self.external_calls()
        engine, controller = self.restored_controller()
        _, _, audit = self.audit_documents(
            controller, second.research_plan_execution.plan_id
        )
        self.assertEqual(self.external_calls(), calls)
        self.assertEqual(
            {
                (source["url"], source["content_sha256"])
                for source in audit["research_run"]["sources"]
            },
            {(source.url, source.content_sha256) for source in second_run.sources},
        )
        knowledge = self.restarted.container.resolve(KnowledgeEngine)
        for evidence in second_run.evidence:
            self.assertIn(
                "revised study", knowledge.get_chunk(evidence.chunk_id).content
            )
        for evidence in first_run.evidence:
            self.assertNotIn("revised", knowledge.get_chunk(evidence.chunk_id).content)

    def test_same_url_in_a_different_mission_is_a_distinct_authorized_fetch(self):
        self.relation = "possible_agreement"
        self.start()
        first = self.fetched_urls()
        self.start()

        # Another mission's authorized slot is its own operation: the earlier
        # fetch of the same URL does not suppress it.
        second = self.fetched_urls()[len(first) :]
        self.assertEqual(second[:1], first[:1])
        runs = sorted(self.runs_by_id().values(), key=lambda run: run.created_at)
        first_run, second_run = runs[-2], runs[-1]
        shared = {s.url for s in first_run.sources} & {
            s.url for s in second_run.sources
        }
        self.assertTrue(shared)
        for url in shared:
            old = next(s for s in first_run.sources if s.url == url)
            new = next(s for s in second_run.sources if s.url == url)
            # Identical content shares one immutable stored version, but each
            # mission keeps its own record of accepting its own fetch.
            self.assertEqual(
                (old.document_id, old.content_sha256),
                (new.document_id, new.content_sha256),
            )
            self.assertLess(old.added_at, new.added_at)

    def test_legacy_checkpoint_without_requested_urls_refuses_further_fetch(self):
        self.relation = "possible_agreement"
        snapshot = self.interrupted_start(6)
        path = self.execution_store_path()
        document = json.loads(path.read_text("utf-8"))
        for execution in document["executions"]:
            execution["mission_checkpoint"].pop("requested_urls")
        path.write_text(json.dumps(document), encoding="utf-8")
        fetches = self.fetched_urls()

        engine = self.restart()

        self.assertEqual(self.fetched_urls(), fetches)
        listing = self.recovered_listing(engine)
        self.assertIn("lacks requested source identities", listing.message)
        self.assertIsNotNone(
            engine._research_plan_execution_service.restored_execution(snapshot.plan_id)
        )

    def test_malformed_requested_urls_fail_closed_on_load(self):
        self.relation = "possible_agreement"
        self.interrupted_start(6)
        path = self.execution_store_path()
        original = json.loads(path.read_text("utf-8"))
        for value in ("https://reference0.example/study", ["a", "b"], [""], [1]):
            with self.subTest(value=value):
                document = json.loads(json.dumps(original))
                document["executions"][0]["mission_checkpoint"][
                    "requested_urls"
                ] = value
                path.write_text(json.dumps(document), encoding="utf-8")
                with self.assertRaises(ResearchError):
                    JsonFileResearchExecutionStore(path).load()

    @staticmethod
    def routed_status(engine, plan_id):
        return engine.process(
            BrainRequest(
                message="status",
                metadata={
                    "intent": "research_plan_execution_status",
                    "research_plan_id": plan_id,
                },
            )
        )

    def test_restored_mission_status_shows_recomputed_report_without_work(self):
        self.relation = "possible_agreement"
        response = self.start()
        plan_id = response.research_plan_execution.plan_id
        report = self.controller.mission_comparison_review(plan_id).message.split(
            "\n\n", 1
        )[1]
        calls = self.external_calls()
        files = self.durable_files()

        engine, controller = self.restored_controller()
        first = self.routed_status(engine, plan_id)
        second = self.routed_status(engine, plan_id)

        self.assertIn("Research plan execution (restored):", first.message)
        self.assertIn("Restored mission teaching report (recomputed", first.message)
        self.assertTrue(first.message.endswith(report), first.message)
        self.assertEqual(second.message, first.message)
        self.assertIn("Mission goal satisfaction: Unresolved", first.message)
        self.assertEqual(self.external_calls(), calls)
        self.assertEqual(self.durable_files(), files)
        self.assertIsNone(
            engine._research_plan_execution_service.live_execution(plan_id)
        )

        target = controller.mission_comparison_review(plan_id)
        recorded = controller.record_research_comparison_review(
            *mission_comparison_review_preview(
                target.research_runs[0],
                plan_id,
                target.research_mission_comparison_note_id,
                "supported",
                "Reviewed from restored status.",
            ).arguments
        )
        self.assertTrue(recorded.success, recorded.message)
        after = self.routed_status(engine, plan_id)
        self.assertIn(
            "Mission goal satisfaction: Satisfied within the current bounded evidence",
            after.message,
        )
        self.assertIn("Ready for bounded user conclusion", after.message)

    def test_legacy_restored_mission_status_names_missing_stop_without_guessing(self):
        self.relation = "possible_agreement"
        response = self.start()
        plan_id = response.research_plan_execution.plan_id
        path = self.execution_store_path()
        document = json.loads(path.read_text("utf-8"))
        for execution in document["executions"]:
            execution.pop("mission_stop_reason", None)
        path.write_text(json.dumps(document), encoding="utf-8")

        engine, _ = self.restored_controller()
        status = self.routed_status(engine, plan_id)

        self.assertIn("Restored mission teaching report unavailable:", status.message)
        self.assertIn("no outcome was inferred", status.message)
        self.assertNotIn("Mission goal satisfaction", status.message)

    def test_live_mission_status_does_not_add_restored_report(self):
        self.relation = "possible_agreement"
        response = self.start()

        status = self.routed_status(
            self.engine, response.research_plan_execution.plan_id
        )

        self.assertNotIn("Restored mission teaching report", status.message)

    def test_interrupted_mission_records_no_stop_reason(self):
        snapshot = self.interrupted_start(6)

        self.assertIsNone(snapshot.mission_stop_reason)
        self.assertIsNone(snapshot.restored().mission_stop_reason)

    def test_resumed_mission_records_the_new_stop_not_the_old_one(self):
        self.relation = "possible_agreement"
        snapshot = self.interrupted_start(6)
        engine = self.restart()
        execution = engine._research_plan_execution_service

        stop = execution.mission_stop_reason(snapshot.plan_id)

        self.assertIsNotNone(stop)
        stored = JsonFileResearchExecutionStore(self.execution_store_path()).load()
        self.assertEqual(
            next(
                s for s in stored if s.plan_id == snapshot.plan_id
            ).mission_stop_reason,
            stop,
        )

    def spend(self, execution, plan_id):
        allowance = execution.allowance(plan_id)
        return (
            allowance.spend.step_advances,
            allowance.spend.network_operations,
            allowance.spend.llm_operations,
        )

    def test_not_comparable_mission_is_unresolved_without_extra_followup(self):
        self.relation = "not_comparable"

        response = self.start()

        plan_id = response.research_plan_execution.plan_id
        snapshot = self.execution._execution_store.load()[0]
        checkpoint = snapshot.mission_checkpoint
        self.assertEqual(checkpoint.semantic_relation, "not_comparable")
        self.assertEqual(
            (checkpoint.contradiction_outcome, checkpoint.evidence_gap_outcome),
            ("", ""),
        )
        self.assertIn("Mission goal satisfaction: Unresolved", response.message)
        self.assertIn(
            "Mission completion readiness: Not ready: canonical evidence remains "
            "incomplete",
            response.message,
        )
        self.assertIn(
            "The selected sources were judged not comparable", response.message
        )
        self.assertIn("no supported comparison was established", response.message)
        self.assertNotIn("Ready for bounded user conclusion", response.message)
        plan = self.execution.live_plan(plan_id)
        self.assertIs(
            self.execution._mission_resolver.followup_decision(
                plan, plan.steps[12].step_id, self.execution.allowance(plan_id)
            ).status,
            ResearchMissionFollowupDecisionStatus.NOT_NEEDED,
        )
        self.assertEqual(plan_digest(plan), snapshot.mission_plan_digest)
        self.assertEqual(len(checkpoint.acquired_urls), 2)
        self.assertEqual(self.spend(self.execution, plan_id), (12, 6, 1))
        self.assertEqual(
            (self.transport.call_count, self.fetcher.fetch.call_count), (1, 2)
        )
        self.assertEqual(response.research_runs[0].claims, ())

    def test_restart_not_comparable_recovers_the_same_unresolved_report(self):
        self.relation = "not_comparable"
        response = self.start()
        plan_id = response.research_plan_execution.plan_id
        before = self.execution._execution_store.load()[0].mission_checkpoint
        calls = self.external_calls()

        engine = self.restart()

        execution = engine._research_plan_execution_service
        self.assertEqual(execution.mission_checkpoint(plan_id), before)
        status = self.execution_status(engine, plan_id).message
        self.assertIn("Recovered mission teaching report", status)
        self.assertIn("Mission goal satisfaction: Unresolved", status)
        self.assertIn("The selected sources were judged not comparable", status)
        self.assertEqual(self.external_calls(), calls)
        self.assertEqual(self.spend(execution, plan_id), (12, 6, 1))

    def test_pre_gap_not_comparable_checkpoint_recovers_as_unresolved(self):
        self.relation = "not_comparable"
        response = self.start()
        plan_id = response.research_plan_execution.plan_id
        path = self.root / "research_executions.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        checkpoint = document["executions"][0]["mission_checkpoint"]
        for key in tuple(checkpoint):
            if key.startswith(("contradiction_", "evidence_gap_")):
                checkpoint.pop(key)
        path.write_text(json.dumps(document), encoding="utf-8")
        calls = self.external_calls()

        engine = self.restart()

        execution = engine._research_plan_execution_service
        restored = execution.mission_checkpoint(plan_id)
        self.assertEqual(restored.semantic_relation, "not_comparable")
        status = self.execution_status(engine, plan_id).message
        self.assertIn("Mission goal satisfaction: Unresolved", status)
        self.assertNotIn("Satisfied within the current bounded evidence", status)
        self.assertEqual(self.external_calls(), calls)
        self.assertEqual(self.spend(execution, plan_id), (12, 6, 1))

    def test_conflict_followup_not_comparable_is_named_in_explanation(self):
        self.relations = ["possible_conflict", "not_comparable"]

        response = self.start()

        checkpoint = self.execution._execution_store.load()[0].mission_checkpoint
        self.assertEqual(checkpoint.contradiction_followup_relation, "not_comparable")
        self.assertEqual(checkpoint.contradiction_outcome, "unresolved")
        self.assertIn(
            "The bounded tentative contradiction remains unresolved", response.message
        )
        self.assertIn(
            "follow-up comparison with a new source was judged not comparable, so it "
            "neither supports nor resolves the tentative contradiction",
            response.message,
        )
        self.assertIn("Mission goal satisfaction: Unresolved", response.message)
        self.assertEqual(
            self.spend(self.execution, response.research_plan_execution.plan_id),
            (18, 9, 2),
        )

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

    def test_learning_preview_shows_prior_advisory_lessons_without_writing(self):
        self.provider.discover.return_value = []
        first = self.start()
        run = first.research_runs[0]
        self.assertTrue(self.engine._failure_memory_service.lessons())
        before = {
            path: path.read_text(encoding="utf-8") for path in self.root.rglob("*.json")
        }
        discovered = self.provider.discover.call_count

        preview = self.controller.preview_learning_research(
            self.question, "crossref", self.budget
        )

        self.assertTrue(preview.success, preview.message)
        self.assertIn(
            "Prior advisory lessons for this question (advice only; not "
            "instructions, authority or evidence):",
            preview.message,
        )
        self.assertIn(f"[run {run.run_id}]", preview.message)
        self.assertEqual(
            {
                path: path.read_text(encoding="utf-8")
                for path in self.root.rglob("*.json")
            },
            before,
        )
        self.assertEqual(self.provider.discover.call_count, discovered)
        self.transport.assert_not_called()

    def test_learning_preview_without_matching_lessons_adds_no_advice(self):
        preview = self.controller.preview_learning_research(
            self.question, "crossref", self.budget
        )

        self.assertTrue(preview.success, preview.message)
        self.assertNotIn("Prior advisory lessons", preview.message)

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

    def empty_proposals(self):
        self.transport.side_effect = None
        self.transport.return_value = {
            "choices": [{"message": {"content": '{"comparisons": []}'}}]
        }

    def test_empty_model_proposal_follows_up_once_only(self):
        self.empty_proposals()
        response = self.start()
        self.assertEqual(self.transport.call_count, 2)
        self.assertEqual(self.fetcher.fetch.call_count, 3)
        self.assertIn("evidence gap remains", response.message)
        self.assertEqual(response.research_runs[0].claims, ())

    def test_empty_proposal_followup_completes_as_unresolved_comparison_gap(self):
        self.empty_proposals()

        response = self.start()

        state = response.research_plan_execution
        self.assertEqual(state.status.value, "completed")
        self.assertEqual(state.completed_steps, 18)
        self.assertNotIn("not authorized", response.message)
        snapshot = self.execution._execution_store.load()[0]
        checkpoint = snapshot.mission_checkpoint
        self.assertEqual(checkpoint.semantic_relation, "no_supported_comparison")
        self.assertEqual(checkpoint.contradiction_outcome, "")
        self.assertEqual(checkpoint.evidence_gap_outcome, "no_supported_comparison")
        self.assertEqual(
            checkpoint.evidence_gap_followup_note_id,
            response.research_runs[0].comparison_notes[-1].note_id,
        )
        self.assertIn("Mission goal satisfaction: Unresolved", response.message)
        self.assertIn(
            "Mission completion readiness: Not ready: canonical evidence remains "
            "incomplete",
            response.message,
        )
        self.assertIn(
            "the initial comparison and the one authorized follow-up both returned "
            "none",
            response.message,
        )
        self.assertNotIn("Execution failed", response.message)
        run = response.research_runs[0]
        self.assertEqual((run.claims, run.claim_contradictions), ((), ()))
        self.assertFalse(run.status.terminal)
        allowance = self.execution.allowance(state.plan_id)
        self.assertEqual(
            (
                allowance.spend.step_advances,
                allowance.spend.network_operations,
                allowance.spend.llm_operations,
            ),
            (18, 9, 2),
        )
        self.assertEqual(
            plan_digest(self.execution.live_plan(state.plan_id)),
            snapshot.mission_plan_digest,
        )
        self.assertEqual(len(checkpoint.acquired_urls), 3)
        self.assertEqual(
            (self.transport.call_count, self.fetcher.fetch.call_count), (2, 3)
        )

    def test_restart_derives_the_same_comparison_gap_without_replay(self):
        self.empty_proposals()
        response = self.start()
        stop = response.research_autonomy.stop_reason.value
        before = self.execution._execution_store.load()[0].mission_checkpoint
        calls = self.external_calls()

        engine = self.restart()

        snapshot = engine._research_plan_execution_service.restored_execution(
            response.research_plan_execution.plan_id
        )
        self.assertIsNotNone(snapshot)
        restored = snapshot.mission_checkpoint
        self.assertEqual(restored, before)
        run = JsonFileResearchRunStore(self.root / "runs.json").load()[0]
        self.assertIs(
            mission_outcome_for(run, stop, restored).goal_satisfaction.status,
            GoalStatus.UNRESOLVED,
        )
        self.assertEqual(self.external_calls(), calls)

    def test_restart_before_gap_followup_resumes_to_the_same_unresolved_gap(self):
        self.empty_proposals()
        snapshot = self.interrupted_start(12)
        self.assertEqual(
            snapshot.mission_checkpoint.semantic_relation, "no_supported_comparison"
        )
        self.assertEqual(
            (self.transport.call_count, self.fetcher.fetch.call_count), (1, 2)
        )

        engine = self.restart()

        execution = engine._research_plan_execution_service
        state = execution.live_execution(snapshot.plan_id)
        self.assertEqual((state.status.value, state.completed_steps), ("completed", 18))
        checkpoint = execution.mission_checkpoint(snapshot.plan_id)
        self.assertEqual(checkpoint.evidence_gap_outcome, "no_supported_comparison")
        status = self.execution_status(engine, snapshot.plan_id).message
        self.assertIn("Mission goal satisfaction: Unresolved", status)
        self.assertIn("both returned none", status)
        self.assertEqual(
            (self.transport.call_count, self.fetcher.fetch.call_count), (2, 3)
        )
        allowance = execution.allowance(snapshot.plan_id)
        self.assertEqual(
            (
                allowance.spend.step_advances,
                allowance.spend.network_operations,
                allowance.spend.llm_operations,
            ),
            (18, 9, 2),
        )

    def test_legacy_gap_checkpoint_without_outcome_never_becomes_satisfied(self):
        self.empty_proposals()
        response = self.start()
        plan_id = response.research_plan_execution.plan_id
        stop = response.research_autonomy.stop_reason.value
        store_path = next(
            path
            for path in self.root.rglob("*.json")
            if "evidence_gap_outcome" in path.read_text(encoding="utf-8")
        )
        document = json.loads(store_path.read_text(encoding="utf-8"))

        def strip_gap(value):
            if isinstance(value, dict):
                return {
                    key: strip_gap(item)
                    for key, item in value.items()
                    if not key.startswith("evidence_gap_")
                }
            if isinstance(value, list):
                return [strip_gap(item) for item in value]
            return value

        store_path.write_text(json.dumps(strip_gap(document)), encoding="utf-8")
        calls = self.external_calls()

        engine = self.restart()

        execution = engine._research_plan_execution_service
        self.assertIsNone(execution.live_execution(plan_id))
        legacy = execution.restored_execution(plan_id).mission_checkpoint
        self.assertEqual(legacy.evidence_gap_outcome, "")
        self.assertEqual(legacy.semantic_relation, "no_supported_comparison")
        run = JsonFileResearchRunStore(self.root / "runs.json").load()[0]
        self.assertIs(
            mission_outcome_for(run, stop, legacy).goal_satisfaction.status,
            GoalStatus.UNRESOLVED,
        )
        self.assertIn(
            "Automatic mission recovery stopped safely",
            self.execution_status(engine, plan_id).message,
        )
        self.assertEqual(self.external_calls(), calls)

    def interrupted_start(self, completed_steps):
        real_advance = self.execution.process_advance

        def interrupt(request):
            state = self.execution.live_execution(request.metadata["research_plan_id"])
            if state is not None and state.completed_steps == completed_steps:
                raise RuntimeError("simulated process interruption")
            return real_advance(request)

        with patch.object(self.execution, "process_advance", side_effect=interrupt):
            with self.assertRaisesRegex(RuntimeError, "simulated process interruption"):
                self.start()
        return self.execution._execution_store.load()[-1]

    @staticmethod
    def execution_status(engine, plan_id):
        return engine._research_plan_execution_service.process_status(
            BrainRequest(
                message="status",
                metadata={
                    "intent": "research_plan_execution_status",
                    "research_plan_id": plan_id,
                },
            )
        )

    @staticmethod
    def recovered_mission_state(engine, plan_id):
        execution = engine._research_plan_execution_service
        plan = execution.live_plan(plan_id)
        return (
            execution.allowance(plan_id),
            execution.mission_checkpoint(plan_id),
            plan_digest(plan),
            plan.mission_scope,
            execution.live_execution(plan_id),
        )

    def test_restart_completed_mission_exposes_recovered_teaching_report(self):
        snapshot = self.interrupted_start(6)
        engine = self.restart()
        calls = self.external_calls()
        state = self.recovered_mission_state(engine, snapshot.plan_id)
        self.assertEqual(state[4].completed_steps, 18)

        first = self.execution_status(engine, snapshot.plan_id)
        second = self.execution_status(engine, snapshot.plan_id)

        self.assertEqual(first.message, second.message)
        run = JsonFileResearchRunStore(self.root / "runs.json").load()[0]
        stop = first.message.split("Stop reason: ", 1)[1].split(".", 1)[0]
        self.assertIn(stop, {value.value for value in AutonomyStopReason})
        spend = "Cumulative spending: 18 advances, 9 network and 2 model operations."
        self.assertIn(f"Stop reason: {stop}. {spend}", first.message)
        expected = teaching_report(run, stop, spend, checkpoint=state[1])
        self.assertIn("Recovered mission teaching report", first.message)
        self.assertIn(
            expected + "\n\nPrior advisory lessons (not instructions or authority):",
            first.message,
        )
        for section in (
            "Mission goal satisfaction: Unresolved",
            "Goal-satisfaction explanation:",
            "Mission completion readiness: Not ready",
            "Uncertainty caveats: source independence unverified",
        ):
            self.assertIn(section, first.message)
        self.assertEqual(self.external_calls(), calls)
        self.assertEqual(self.recovered_mission_state(engine, snapshot.plan_id), state)
        self.assertFalse(run.status.terminal)
        for path in self.root.rglob("*.json"):
            self.assertNotIn(
                "Goal-satisfaction explanation", path.read_text(encoding="utf-8")
            )

    def test_refused_recovery_keeps_refusal_without_report(self):
        snapshot = self.interrupted_start(3)
        engine = self.restart()

        status = self.execution_status(engine, snapshot.plan_id)

        self.assertIn("preview was not durably accepted", status.message)
        self.assertNotIn("Recovered mission teaching report", status.message)
        self.assertNotIn("Bounded research report", status.message)
        self.transport.assert_not_called()

    def test_resume_without_autonomy_result_exposes_no_report(self):
        snapshot = self.interrupted_start(6)
        refused = BrainResponse(
            message="Research autonomy refused.",
            request_id="restart",
            intent="research_autonomy_run",
            memory_count=0,
            success=False,
        )
        with patch.object(
            ResearchAutonomyApplicationService, "process_run", return_value=refused
        ):
            engine = self.restart()

        status = self.execution_status(engine, snapshot.plan_id)

        self.assertIsNotNone(
            engine._research_plan_execution_service.live_execution(snapshot.plan_id)
        )
        self.assertNotIn("Recovered mission teaching report", status.message)
        self.assertNotIn("Bounded research report", status.message)
        self.transport.assert_not_called()

    def test_recovered_reports_and_refusals_stay_with_their_missions(self):
        # The fixture model checks the newest snapshot, so the mission that
        # makes model calls on resume is started last.
        refused = self.interrupted_start(3)
        recovered = self.interrupted_start(6)
        engine = self.restart()
        runs = {
            run.run_id: run
            for run in JsonFileResearchRunStore(self.root / "runs.json").load()
        }

        recovered_message = self.execution_status(engine, recovered.plan_id).message
        refused_message = self.execution_status(engine, refused.plan_id).message

        self.assertIn("preview was not durably accepted", refused_message)
        self.assertNotIn("Recovered mission teaching report", refused_message)
        self.assertIn("Recovered mission teaching report", recovered_message)
        self.assertNotIn("preview was not durably accepted", recovered_message)
        recovered_evidence = runs[recovered.research_run_id].evidence
        self.assertTrue(recovered_evidence)
        for record in recovered_evidence:
            self.assertIn(record.evidence_id, recovered_message)
            self.assertNotIn(record.evidence_id, refused_message)
        for record in runs[refused.research_run_id].evidence:
            self.assertNotIn(record.evidence_id, recovered_message)

    def deferred_restart(self):
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
            defer_mission_recovery=True,
        )
        restarted.initialize()
        self.restarted = restarted
        return restarted.container.resolve(CognitiveEngine)

    @staticmethod
    def start_mission_recovery(engine, cancellation_token=None):
        return engine.process(
            BrainRequest(
                message="Resume restored research missions",
                cancellation_token=cancellation_token,
                metadata={"intent": "research_mission_recovery_start"},
            )
        )

    def test_cancelled_deferred_recovery_replays_nothing_and_stays_visible(self):
        snapshot = self.interrupted_start(6)
        calls = self.external_calls()
        engine = self.deferred_restart()
        signal = CancellationSignal()
        signal.cancel()

        response = self.start_mission_recovery(engine, signal)

        self.assertIn("finished: 0 mission(s) resumed", response.message)
        self.assertIn("Recovery was cancelled", response.message)
        execution = engine._research_plan_execution_service
        self.assertIsNone(execution.live_execution(snapshot.plan_id))
        self.assertIn(
            "cancelled before this mission",
            self.execution_status(engine, snapshot.plan_id).message,
        )
        self.assertIn(snapshot.plan_id, self.recovered_listing(engine).message)
        self.assertEqual(self.external_calls(), calls)
        self.assertIn("already ran", self.start_mission_recovery(engine).message)
        self.assertEqual(self.external_calls(), calls)

    def test_cancellation_during_deferred_recovery_keeps_charge_not_lessons(self):
        snapshot = self.interrupted_start(6)
        engine = self.deferred_restart()
        signal = CancellationSignal()
        answer = self.transport.side_effect

        def cancel_after_model(*args):
            result = answer(*args)
            signal.cancel()
            return result

        self.transport.side_effect = cancel_after_model

        response = self.start_mission_recovery(engine, signal)

        self.assertIn("Recovery was cancelled", response.message)
        self.assertEqual(self.transport.call_count, 1)
        allowance = engine._research_plan_execution_service.allowance(snapshot.plan_id)
        self.assertEqual(allowance.spend.llm_operations, 1)
        status = self.execution_status(engine, snapshot.plan_id).message
        self.assertIn("Stop reason: cancelled", status)
        self.assertIn("Cancelled: no new lesson retention attempted.", status)
        self.assertEqual(self.run_lessons(engine, snapshot.research_run_id), ())

    def test_deferred_startup_recovery_runs_only_when_requested_and_once(self):
        snapshot = self.interrupted_start(6)
        calls = self.external_calls()

        engine = self.deferred_restart()

        execution = engine._research_plan_execution_service
        self.assertIsNone(execution.live_execution(snapshot.plan_id))
        self.assertIsNotNone(execution.restored_execution(snapshot.plan_id))
        self.assertEqual(self.external_calls(), calls)

        first = self.start_mission_recovery(engine)

        self.assertIn("finished: 1 mission(s) resumed", first.message)
        self.assertEqual(execution.live_execution(snapshot.plan_id).completed_steps, 18)
        self.assertIn(
            "Recovered mission teaching report",
            self.execution_status(engine, snapshot.plan_id).message,
        )
        resumed_calls = self.external_calls()
        allowance = execution.allowance(snapshot.plan_id)

        second = self.start_mission_recovery(engine)

        self.assertIn("already ran", second.message)
        self.assertEqual(self.external_calls(), resumed_calls)
        self.assertEqual(execution.allowance(snapshot.plan_id), allowance)

    def test_non_deferred_startup_recovery_is_not_repeated_on_request(self):
        snapshot = self.interrupted_start(6)
        engine = self.restart()
        calls = self.external_calls()
        allowance = engine._research_plan_execution_service.allowance(snapshot.plan_id)

        response = self.start_mission_recovery(engine)

        self.assertIn("already ran", response.message)
        self.assertEqual(self.external_calls(), calls)
        self.assertEqual(
            engine._research_plan_execution_service.allowance(snapshot.plan_id),
            allowance,
        )

    def test_deferred_recovery_refusal_stays_visible_without_work(self):
        snapshot = self.interrupted_start(3)
        engine = self.deferred_restart()

        response = self.start_mission_recovery(engine)

        self.assertIn("finished: 0 mission(s) resumed", response.message)
        self.assertIn(
            "preview was not durably accepted",
            self.execution_status(engine, snapshot.plan_id).message,
        )
        self.transport.assert_not_called()

    def fail_followup_fetch(self):
        followup_url = self.sources[2].url

        def fetch(url):
            if url == followup_url:
                raise ResearchError("fixture follow-up source unavailable")
            return next(s for s in self.sources if s.url == url)

        self.fetcher.fetch.side_effect = fetch

    @staticmethod
    def run_lessons(engine, run_id):
        return tuple(
            lesson
            for lesson in engine._failure_memory_service.lessons()
            if lesson.run_id == run_id
        )

    def test_recovered_mission_retains_lessons_through_live_failure_memory(self):
        snapshot = self.interrupted_start(6)
        self.assertEqual(self.run_lessons(self.engine, snapshot.research_run_id), ())
        self.fail_followup_fetch()

        engine = self.restart()

        run = JsonFileResearchRunStore(self.root / "runs.json").load()[0]
        lessons = self.run_lessons(engine, run.run_id)
        self.assertTrue(run.failures)
        self.assertTrue(
            any(lesson.kind.value == "operation_failure" for lesson in lessons)
        )
        self.assertEqual(
            {lesson.lesson_id for lesson in lessons},
            {
                lesson.lesson_id
                for lesson in ResearchFailureLessonDeriver().derive(
                    run, datetime.now(UTC)
                )
            },
        )
        report = self.execution_status(engine, snapshot.plan_id).message
        self.assertIn("Prior advisory lessons (not instructions or authority)", report)
        self.assertEqual(self.transport.call_count, 1)
        allowance = engine._research_plan_execution_service.allowance(snapshot.plan_id)
        self.assertLessEqual(
            allowance.spend.llm_operations, self.budget.max_llm_operations
        )
        self.assertEqual(
            plan_digest(
                engine._research_plan_execution_service.live_plan(snapshot.plan_id)
            ),
            snapshot.mission_plan_digest,
        )
        self.assertFalse(run.status.terminal)
        self.assertEqual(run.claims, ())

        calls = self.external_calls()
        persisted = (self.root / "research_failure_lessons.json").read_text(
            encoding="utf-8"
        )
        again = self.restart()

        self.assertEqual(
            {lesson.lesson_id for lesson in self.run_lessons(again, run.run_id)},
            {lesson.lesson_id for lesson in lessons},
        )
        self.assertEqual(self.external_calls(), calls)
        self.assertEqual(
            (self.root / "research_failure_lessons.json").read_text(encoding="utf-8"),
            persisted,
        )

    def test_refused_recovery_retains_no_lesson(self):
        snapshot = self.interrupted_start(3)

        engine = self.restart()

        self.assertEqual(self.run_lessons(engine, snapshot.research_run_id), ())

    def test_resume_without_autonomy_result_retains_no_lesson(self):
        snapshot = self.interrupted_start(6)
        refused = BrainResponse(
            message="Research autonomy refused.",
            request_id="restart",
            intent="research_autonomy_run",
            memory_count=0,
            success=False,
        )
        with patch.object(
            ResearchAutonomyApplicationService, "process_run", return_value=refused
        ):
            engine = self.restart()

        self.assertEqual(self.run_lessons(engine, snapshot.research_run_id), ())

    @staticmethod
    def recovered_listing(engine):
        return engine.process(
            BrainRequest(
                message="List missions recovered at startup",
                metadata={"intent": "research_plan_execution_recovered"},
            )
        )

    def test_recovered_missions_listing_names_resumed_and_refused_plans(self):
        refused = self.interrupted_start(3)
        recovered = self.interrupted_start(6)
        engine = self.restart()
        calls = self.external_calls()
        state = self.recovered_mission_state(engine, recovered.plan_id)

        listing = self.recovered_listing(engine)

        self.assertTrue(listing.success)
        self.assertEqual(
            set(listing.research_recovered_mission_ids),
            {refused.plan_id, recovered.plan_id},
        )
        self.assertEqual(
            dict(
                zip(
                    listing.research_recovered_mission_ids,
                    listing.research_recovered_mission_run_ids,
                    strict=True,
                )
            ),
            {
                refused.plan_id: refused.research_run_id,
                recovered.plan_id: recovered.research_run_id,
            },
        )
        self.assertIn(f"Run ID: {recovered.research_run_id}", listing.message)
        self.assertIn(
            f"Plan ID: {recovered.plan_id} | Question: {self.question} | resumed",
            listing.message,
        )
        self.assertIn(f"Plan ID: {refused.plan_id}", listing.message)
        self.assertIn("not resumed: ", listing.message)
        self.assertIn("preview was not durably accepted", listing.message)
        self.assertIn(
            "No stop was recorded, so no report is available.", listing.message
        )
        self.assertEqual(self.recovered_listing(engine).message, listing.message)
        self.assertEqual(self.external_calls(), calls)
        self.assertEqual(self.recovered_mission_state(engine, recovered.plan_id), state)

    def test_listing_points_a_terminal_restored_mission_to_its_report(self):
        self.fetcher.fetch.side_effect = ResearchError("fixture unavailable")
        response = self.start()
        plan_id = response.research_plan_execution.plan_id
        calls = self.external_calls()

        engine = self.restart()
        listing = self.recovered_listing(engine)
        status = self.routed_status(engine, plan_id)

        entry = next(line for line in listing.message.splitlines() if plan_id in line)
        self.assertIn("not resumed: ", entry)
        self.assertIn(
            "Its report, recomputed from the recorded stop, is in this "
            "execution's status.",
            entry,
        )
        self.assertIn("Restored mission teaching report (recomputed", status.message)
        self.assertIn("Stop reason: step_failed", status.message)
        self.assertEqual(self.external_calls(), calls)

    def test_recovered_missions_listing_is_empty_without_startup_recovery(self):
        self.relation = "possible_agreement"
        self.start()

        listing = self.recovered_listing(self.engine)

        self.assertEqual(listing.research_recovered_mission_ids, ())
        self.assertIn("No learning mission was resumed or refused", listing.message)

    def mission_state(self, response):
        plan_id = response.research_plan_execution.plan_id
        return (
            self.execution.mission_checkpoint(plan_id),
            self.execution.allowance(plan_id),
            plan_digest(self.execution.live_plan(plan_id)),
            self.execution.live_execution(plan_id),
        )

    def external_calls(self):
        return (
            self.transport.call_count,
            self.fetcher.fetch.call_count,
            self.provider.discover.call_count,
        )

    def judge(self, run, document_id, independence):
        return self.controller.record_research_source_assessment(
            *independence_assessment_arguments(run, document_id, independence)
        )

    def test_independence_judgement_updates_caveat_not_mission_or_goal(self):
        self.relation = "possible_agreement"
        response = self.start()
        stop = response.research_autonomy.stop_reason.value
        run = response.research_runs[0]
        state = self.mission_state(response)
        calls = self.external_calls()
        before = mission_outcome_for(run, stop, state[0])
        self.assertIn("source independence unverified", response.message)
        rows = independence_review_rows(run)
        self.assertEqual(
            {row.document_id for row in rows},
            {record.source_document_id for record in run.evidence},
        )

        current = run
        for row in rows:
            recorded = self.judge(current, row.document_id, "independent")
            self.assertTrue(recorded.success, recorded.message)
            current = recorded.research_runs[0]

        self.assertEqual(source_independence_caveats(current), ())
        self.assertEqual(
            tuple(
                record.supersedes_assessment_id
                for record in current.assessments[len(run.assessments) :]
            ),
            tuple(row.current_assessment.assessment_id for row in rows),
        )
        after = mission_outcome_for(current, stop, self.mission_state(response)[0])
        # Tentative agreement is unresolved; operator judgements never upgrade it.
        self.assertIs(before.goal_satisfaction.status, GoalStatus.UNRESOLVED)
        self.assertEqual(after.goal_satisfaction, before.goal_satisfaction)
        self.assertEqual(after.completion_readiness, before.completion_readiness)
        self.assertEqual(self.mission_state(response), state)
        self.assertEqual(self.external_calls(), calls)
        self.assertEqual((current.status, current.claims), (run.status, run.claims))
        report = teaching_report(current, stop, "Spend.", checkpoint=state[0])
        self.assertIn("Uncertainty caveats: none recorded.", report)
        self.assertNotIn("source independence unverified", report)

    def test_derivative_judgement_keeps_stronger_caveat_and_goal(self):
        self.relation = "possible_agreement"
        response = self.start()
        stop = response.research_autonomy.stop_reason.value
        run = response.research_runs[0]
        checkpoint = self.mission_state(response)[0]
        first = independence_review_rows(run)[0]

        recorded = self.judge(run, first.document_id, "derivative")

        self.assertTrue(recorded.success, recorded.message)
        current = recorded.research_runs[0]
        self.assertEqual(
            source_independence_caveats(current),
            (Caveat.SOURCE_NOT_INDEPENDENT, Caveat.SOURCE_INDEPENDENCE_UNVERIFIED),
        )
        self.assertEqual(
            mission_outcome_for(current, stop, checkpoint).goal_satisfaction,
            mission_outcome_for(run, stop, checkpoint).goal_satisfaction,
        )
        self.assertIn(
            "source not independent",
            teaching_report(current, stop, "Spend.", checkpoint=checkpoint),
        )

    def test_stale_independence_review_cannot_overwrite_newer_assessment(self):
        self.relation = "possible_agreement"
        run = self.start().research_runs[0]
        row = independence_review_rows(run)[0]

        first = self.judge(run, row.document_id, "independent")
        stale = self.judge(run, row.document_id, "likely_duplicate")

        self.assertTrue(first.success, first.message)
        self.assertFalse(stale.success)
        saved = JsonFileResearchRunStore(self.root / "runs.json").load()[0]
        self.assertEqual(len(saved.assessments), len(run.assessments) + 1)
        self.assertEqual(
            independence_review_rows(saved)[0].independence.value, "independent"
        )

    def test_unresolved_goal_is_not_upgraded_by_independence_judgements(self):
        response = self.start()
        stop = response.research_autonomy.stop_reason.value
        run = response.research_runs[0]
        checkpoint = self.mission_state(response)[0]
        current = run
        for row in independence_review_rows(run):
            current = self.judge(current, row.document_id, "independent").research_runs[
                0
            ]

        self.assertEqual(source_independence_caveats(current), ())
        before = mission_outcome_for(run, stop, checkpoint)
        after = mission_outcome_for(current, stop, checkpoint)
        self.assertIs(after.goal_satisfaction.status, GoalStatus.UNRESOLVED)
        self.assertEqual(after.completion_readiness, before.completion_readiness)

    def test_restart_shows_same_current_independence_without_replay(self):
        self.relation = "possible_agreement"
        run = self.start().research_runs[0]
        current = run
        for row in independence_review_rows(run):
            current = self.judge(current, row.document_id, "independent").research_runs[
                0
            ]
        calls = self.external_calls()

        self.restart()
        restored = JsonFileResearchRunStore(self.root / "runs.json").load()[0]

        self.assertEqual(restored, current)
        self.assertEqual(source_independence_caveats(restored), ())
        self.assertEqual(
            independence_review_rows(restored), independence_review_rows(current)
        )
        self.assertEqual(self.external_calls(), calls)

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
