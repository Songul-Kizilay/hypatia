"""Composition-level proof that registered capabilities are actually reachable.

A capability can work when the application service is constructed directly in a
unit test while the production wiring silently fails to register it. That
happened once, so every connected capability must also be proven reachable
through the real CognitiveEngine composition path.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainRequest import BrainRequest
from cognition.CognitiveEngine import CognitiveEngine
from cognition.ResearchSourceAcceptanceService import (
    ResearchSourceAcceptanceService,
)
from core.Exceptions import ResearchError
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.MemoryManager import MemoryManager
from planner.Planner import Planner
from research.HttpResearchSourceFetcher import HttpResearchSourceFetcher
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchAssessmentAuthorization import (
    ResearchAssessmentAuthorization,
)
from research.ResearchClaimAuthorization import ResearchClaimAuthorization
from research.ResearchComparisonAuthorization import (
    ResearchComparisonAuthorization,
)
from research.ResearchCompletionAuthorization import (
    ResearchCompletionAuthorization,
)
from research.ResearchContradictionAuthorization import (
    ResearchContradictionAuthorization,
)
from research.ResearchEpistemicState import ResearchEpistemicState
from research.ResearchEvidenceIntegrityAuditor import (
    ResearchEvidenceIntegrityAuditor,
)
from research.ResearchPlanExecutionContext import ResearchPlanExecutionContext
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchPlanStepDraftInput import ResearchPlanStepDraftInput
from research.ResearchRunManager import ResearchRunManager
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSource import ResearchSource
from research.ResearchSourceCandidate import ResearchSourceCandidate
from response.ResponseComposer import ResponseComposer
from session.SessionManager import SessionManager
from session.SessionRenameTransactionService import SessionRenameTransactionService


class StubDiscoveryProvider:
    """Deterministic discovery provider standing in for a network provider."""

    def __init__(self) -> None:
        self.queries: list[str] = []

    @property
    def provider_name(self) -> str:
        return "stub_discovery"

    def discover(self, query: str, *, limit: int) -> list[ResearchSourceCandidate]:
        del limit
        self.queries.append(query)
        return [
            ResearchSourceCandidate(
                url="https://example.test/candidate",
                title="A candidate",
                snippet="A bounded snippet.",
            )
        ]


class StubSourceFetcher:
    """Deterministic fetcher standing in for the real HTTPS pipeline."""

    def __init__(self) -> None:
        self.urls: list[str] = []

    def fetch(self, url: str) -> ResearchSource:
        self.urls.append(url)
        return ResearchSource(
            url=url,
            title="Authorized source",
            content="Authorized source body text.",
            content_type="text/html",
            fetched_at=datetime(2026, 8, 1, tzinfo=UTC),
        )


EXPECTED_OPERATIONS = {
    ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH: "local_knowledge_search",
    ResearchPlanStepCapability.ACCEPTED_SOURCE_LISTING: "accepted_source_listing",
    ResearchPlanStepCapability.EVIDENCE_INTEGRITY_CHECK: "evidence_integrity_check",
    ResearchPlanStepCapability.SOURCE_DISCOVERY: "source_discovery",
    ResearchPlanStepCapability.SOURCE_FETCH: "source_fetch",
    ResearchPlanStepCapability.SOURCE_ACCEPT: "source_accept",
    ResearchPlanStepCapability.EVIDENCE_RECORDING: "evidence_recording",
    ResearchPlanStepCapability.SOURCE_ASSESSMENT: "source_assessment",
    ResearchPlanStepCapability.CLAIM_CREATION: "claim_creation",
    ResearchPlanStepCapability.CLAIM_CONTRADICTION: "claim_contradiction",
    ResearchPlanStepCapability.SOURCE_COMPARISON: "source_comparison",
    ResearchPlanStepCapability.RESEARCH_RUN_COMPLETION: ("research_run_completion"),
}


class PlanExecutionCompositionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        document = root / "knowledge.md"
        document.write_text("Saturn\n\nSaturn has rings.", encoding="utf-8")
        self.event_bus = EventBus()
        self.memory_manager = MemoryManager(self.event_bus)
        self.knowledge_engine = KnowledgeEngine()
        self.knowledge_engine.load(document)
        self.session_manager = SessionManager(self.event_bus)
        self.run_manager = ResearchRunManager(
            JsonFileResearchRunStore(root / "runs.json")
        )
        self.discovery_provider = StubDiscoveryProvider()
        self.source_fetcher = StubSourceFetcher()
        self.engine = CognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            Planner(),
            self.event_bus,
            ResponseComposer(),
            self.session_manager,
            SessionRenameTransactionService(
                session_manager=self.session_manager,
                memory_manager=self.memory_manager,
                event_bus=self.event_bus,
            ),
            research_run_manager=self.run_manager,
            research_evidence_integrity_auditor=ResearchEvidenceIntegrityAuditor(
                self.knowledge_engine
            ),
            research_source_discovery_provider=self.discovery_provider,
            research_source_fetcher=self.source_fetcher,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _registry(self):  # type: ignore[no-untyped-def]
        return self.engine._research_plan_execution_service._operation_registry

    def _start(
        self,
        capability: str,
        run_id: str | None = None,
        authorized_url: str | None = None,
        evidence: tuple[str, int, str] | None = None,
    ) -> str:
        draft: tuple[object, ...] = ("Authored instruction", (), capability)
        if authorized_url is not None or evidence is not None:
            draft = (*draft, authorized_url or "")
        if evidence is not None:
            draft = (*draft, evidence)
        metadata: dict[str, object] = {
            "intent": "research_plan_execution_start",
            "research_plan_question": "What evidence supports the claim?",
            "research_plan_steps": (draft,),
        }
        if run_id is not None:
            metadata["research_run_id"] = run_id
        response = self.engine.process(
            BrainRequest(message="Start research plan", metadata=metadata)
        )
        self.assertTrue(response.success, response.message)
        assert response.research_plan_execution is not None
        return response.research_plan_execution.plan_id

    def _advance(self, plan_id: str):  # type: ignore[no-untyped-def]
        return self.engine.process(
            BrainRequest(
                message="Advance research plan",
                metadata={
                    "intent": "research_plan_execution_advance",
                    "research_plan_id": plan_id,
                },
            )
        )

    def test_every_expected_capability_is_registered_in_production_wiring(
        self,
    ) -> None:
        registry = self._registry()

        for capability, operation_name in EXPECTED_OPERATIONS.items():
            with self.subTest(capability=capability):
                operation = registry.resolve(capability)
                self.assertIsNotNone(
                    operation,
                    f"{capability.value} is not registered in production wiring.",
                )
                assert operation is not None
                self.assertEqual(operation.operation_name, operation_name)

    def test_local_knowledge_search_runs_through_the_engine_route(self) -> None:
        plan_id = self._start("local_knowledge_search")

        response = self._advance(plan_id)

        state = response.research_plan_execution
        assert state is not None
        self.assertEqual(state.status.value, "completed")
        self.assertTrue(state.steps[0].work_performed)
        self.assertEqual(state.steps[0].operation, "local_knowledge_search")
        self.assertIn("Local knowledge search matched", state.steps[0].detail)

    def test_accepted_source_listing_runs_through_the_engine_route(self) -> None:
        run = self.run_manager.create("What evidence supports the claim?")
        self.run_manager.add_source(
            run.run_id,
            ResearchSource(
                url="https://example.test/a",
                title="A source",
                content="Accepted source content.",
                content_type="text/html",
                fetched_at=datetime(2026, 8, 23, tzinfo=UTC),
            ),
            "doc-1",
        )
        plan_id = self._start("accepted_source_listing", run_id=run.run_id)

        response = self._advance(plan_id)

        state = response.research_plan_execution
        assert state is not None
        self.assertEqual(state.status.value, "completed")
        self.assertTrue(state.steps[0].work_performed)
        self.assertEqual(state.steps[0].operation, "accepted_source_listing")
        self.assertIn("Listed 1 accepted source(s)", state.steps[0].detail)
        self.assertIn("no evidence was established", state.steps[0].detail)

    def test_accepted_source_listing_without_a_run_fails_the_step(self) -> None:
        plan_id = self._start("accepted_source_listing")

        response = self._advance(plan_id)

        state = response.research_plan_execution
        assert state is not None
        self.assertEqual(state.status.value, "failed")
        self.assertFalse(state.steps[0].work_performed)
        self.assertEqual(state.steps_with_research_work, 0)

    def test_unknown_run_fails_the_step_without_claiming_work(self) -> None:
        plan_id = self._start("accepted_source_listing", run_id="missing-run")

        response = self._advance(plan_id)

        state = response.research_plan_execution
        assert state is not None
        self.assertEqual(state.status.value, "failed")
        self.assertFalse(state.steps[0].work_performed)

    def test_capability_is_unregistered_without_a_run_manager(self) -> None:
        engine = CognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            Planner(),
            self.event_bus,
            ResponseComposer(),
            self.session_manager,
            SessionRenameTransactionService(
                session_manager=self.session_manager,
                memory_manager=self.memory_manager,
                event_bus=self.event_bus,
            ),
        )
        registry = engine._research_plan_execution_service._operation_registry

        self.assertIsNone(
            registry.resolve(ResearchPlanStepCapability.ACCEPTED_SOURCE_LISTING)
        )
        self.assertIsNotNone(
            registry.resolve(ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH)
        )

    def test_execution_routes_perform_no_memory_write(self) -> None:
        before = len(self.memory_manager.all())
        plan_id = self._start("local_knowledge_search")

        self._advance(plan_id)

        self.assertEqual(len(self.memory_manager.all()), before)

    def test_evidence_integrity_check_runs_through_the_engine_route(self) -> None:
        run = self.run_manager.create("What evidence supports the claim?")
        plan_id = self._start("evidence_integrity_check", run_id=run.run_id)

        response = self._advance(plan_id)

        state = response.research_plan_execution
        assert state is not None
        self.assertEqual(state.status.value, "completed")
        self.assertTrue(state.steps[0].work_performed)
        self.assertEqual(state.steps[0].operation, "evidence_integrity_check")
        self.assertIn("Evidence integrity audit ran", state.steps[0].detail)
        self.assertIn("does not establish truth", state.steps[0].detail)

    def test_evidence_integrity_check_without_a_run_fails_the_step(self) -> None:
        plan_id = self._start("evidence_integrity_check")

        response = self._advance(plan_id)

        state = response.research_plan_execution
        assert state is not None
        self.assertEqual(state.status.value, "failed")
        self.assertFalse(state.steps[0].work_performed)
        self.assertEqual(state.steps_with_research_work, 0)

    def test_integrity_capability_is_unregistered_without_an_auditor(self) -> None:
        engine = CognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            Planner(),
            self.event_bus,
            ResponseComposer(),
            self.session_manager,
            SessionRenameTransactionService(
                session_manager=self.session_manager,
                memory_manager=self.memory_manager,
                event_bus=self.event_bus,
            ),
            research_run_manager=self.run_manager,
        )
        registry = engine._research_plan_execution_service._operation_registry

        self.assertIsNone(
            registry.resolve(ResearchPlanStepCapability.EVIDENCE_INTEGRITY_CHECK)
        )
        self.assertIsNotNone(
            registry.resolve(ResearchPlanStepCapability.ACCEPTED_SOURCE_LISTING)
        )

    def test_source_discovery_runs_through_the_engine_route(self) -> None:
        run = self.run_manager.create("What evidence supports the claim?")
        plan_id = self._start("source_discovery", run_id=run.run_id)

        response = self._advance(plan_id)

        state = response.research_plan_execution
        assert state is not None
        self.assertEqual(state.status.value, "completed")
        self.assertTrue(state.steps[0].work_performed)
        self.assertEqual(state.steps[0].operation, "source_discovery")
        self.assertIn("returned 1 candidate(s)", state.steps[0].detail)
        self.assertIn("not accepted sources", state.steps[0].detail)
        self.assertEqual(self.discovery_provider.queries, [run.question])

    def test_discovery_accepts_nothing_and_creates_no_evidence(self) -> None:
        run = self.run_manager.create("What evidence supports the claim?")
        plan_id = self._start("source_discovery", run_id=run.run_id)

        self._advance(plan_id)

        stored = self.run_manager.get(run.run_id)
        self.assertEqual(len(stored.discoveries), 1)
        self.assertEqual(stored.sources, ())
        self.assertEqual(stored.evidence, ())
        self.assertEqual(stored.claims, ())
        self.assertEqual(stored.assessments, ())

    def test_discovery_capability_is_unregistered_without_a_provider(self) -> None:
        engine = CognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            Planner(),
            self.event_bus,
            ResponseComposer(),
            self.session_manager,
            SessionRenameTransactionService(
                session_manager=self.session_manager,
                memory_manager=self.memory_manager,
                event_bus=self.event_bus,
            ),
            research_run_manager=self.run_manager,
        )
        registry = engine._research_plan_execution_service._operation_registry

        self.assertIsNone(registry.resolve(ResearchPlanStepCapability.SOURCE_DISCOVERY))

    def test_source_fetch_runs_through_the_engine_route(self) -> None:
        run = self.run_manager.create("What evidence supports the claim?")
        plan_id = self._start(
            "source_fetch",
            run_id=run.run_id,
            authorized_url="https://example.test/authorized",
        )

        response = self._advance(plan_id)

        state = response.research_plan_execution
        assert state is not None
        self.assertEqual(state.status.value, "completed")
        self.assertTrue(state.steps[0].work_performed)
        self.assertEqual(state.steps[0].operation, "source_fetch")
        self.assertEqual(self.source_fetcher.urls, ["https://example.test/authorized"])
        self.assertIn("not accepted, not indexed, not evidence", state.steps[0].detail)

    def test_source_fetch_accepts_nothing_through_the_engine_route(self) -> None:
        run = self.run_manager.create("What evidence supports the claim?")
        plan_id = self._start(
            "source_fetch",
            run_id=run.run_id,
            authorized_url="https://example.test/authorized",
        )

        self._advance(plan_id)

        stored = self.run_manager.get(run.run_id)
        self.assertEqual(stored.sources, ())
        self.assertEqual(stored.evidence, ())
        self.assertEqual(stored.assessments, ())
        self.assertEqual(stored.claims, ())
        self.assertEqual(self.knowledge_engine.document_count(), 1)

    def test_source_fetch_without_authorization_fails_the_step(self) -> None:
        run = self.run_manager.create("What evidence supports the claim?")
        plan_id = self._start("source_fetch", run_id=run.run_id)

        response = self._advance(plan_id)

        state = response.research_plan_execution
        assert state is not None
        self.assertEqual(state.status.value, "failed")
        self.assertFalse(state.steps[0].work_performed)
        self.assertEqual(self.source_fetcher.urls, [])

    def test_real_pipeline_still_rejects_a_private_address(self) -> None:
        engine = CognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            Planner(),
            self.event_bus,
            ResponseComposer(),
            self.session_manager,
            SessionRenameTransactionService(
                session_manager=self.session_manager,
                memory_manager=self.memory_manager,
                event_bus=self.event_bus,
            ),
            research_run_manager=self.run_manager,
            research_source_fetcher=HttpResearchSourceFetcher(),
        )
        run = self.run_manager.create("What evidence supports the claim?")
        operation = engine._research_plan_execution_service._operation_registry.resolve(
            ResearchPlanStepCapability.SOURCE_FETCH
        )
        assert operation is not None

        for hostile_url in (
            "http://example.test/insecure",
            "https://127.0.0.1/private",
            "https://user:pass@example.test/credentials",
        ):
            with self.subTest(url=hostile_url):
                with self.assertRaises(ResearchError):
                    operation.run(
                        ResearchPlanStep(
                            step_id="step-1",
                            instruction="Fetch",
                            capability=ResearchPlanStepCapability.SOURCE_FETCH,
                            authorized_source_url=hostile_url,
                        ),
                        ResearchPlanExecutionContext(research_run_id=run.run_id),
                    )

        self.assertEqual(self.run_manager.get(run.run_id).sources, ())

    def test_source_accept_runs_through_the_engine_route(self) -> None:
        run = self.run_manager.create("What evidence supports the claim?")
        plan_id = self._start(
            "source_accept",
            run_id=run.run_id,
            authorized_url="https://example.test/accepted",
        )

        response = self._advance(plan_id)

        state = response.research_plan_execution
        assert state is not None
        self.assertEqual(state.status.value, "completed")
        self.assertTrue(state.steps[0].work_performed)
        self.assertEqual(state.steps[0].operation, "source_accept")
        stored = self.run_manager.get(run.run_id)
        self.assertEqual(len(stored.sources), 1)
        self.assertEqual(stored.evidence, ())
        self.assertEqual(stored.claims, ())
        self.assertEqual(stored.assessments, ())

    def test_source_accept_without_authorization_fails_the_step(self) -> None:
        run = self.run_manager.create("What evidence supports the claim?")
        plan_id = self._start("source_accept", run_id=run.run_id)

        response = self._advance(plan_id)

        state = response.research_plan_execution
        assert state is not None
        self.assertEqual(state.status.value, "failed")
        self.assertFalse(state.steps[0].work_performed)
        self.assertEqual(self.source_fetcher.urls, [])
        self.assertEqual(self.run_manager.get(run.run_id).sources, ())

    def test_existing_source_load_route_uses_the_extracted_service(self) -> None:
        service = self.engine._research_source_acceptance_service
        self.assertIsInstance(service, ResearchSourceAcceptanceService)

        accept_operation = self._registry().resolve(
            ResearchPlanStepCapability.SOURCE_ACCEPT
        )
        assert accept_operation is not None
        self.assertIs(accept_operation._acceptance_service, service)

    def test_existing_source_load_route_still_accepts_a_source(self) -> None:
        run = self.run_manager.create("What evidence supports the claim?")

        response = self.engine.process(
            BrainRequest(
                message="Load internet research source",
                metadata={
                    "intent": "research_source_load",
                    "research_url": "https://example.test/legacy",
                    "research_run_id": run.run_id,
                },
            )
        )

        self.assertTrue(response.success, response.message)
        stored = self.run_manager.get(run.run_id)
        self.assertEqual(len(stored.sources), 1)
        self.assertEqual(stored.evidence, ())

    def test_full_chain_accept_then_record_evidence(self) -> None:
        run = self.run_manager.create("What evidence supports the claim?")

        accept_plan = self._start(
            "source_accept",
            run_id=run.run_id,
            authorized_url="https://example.test/chain",
        )
        accept_response = self._advance(accept_plan)
        accept_state = accept_response.research_plan_execution
        assert accept_state is not None
        self.assertEqual(accept_state.status.value, "completed")

        accepted = self.run_manager.get(run.run_id)
        self.assertEqual(len(accepted.sources), 1)
        document_id = accepted.sources[0].document_id

        evidence_plan = self._start(
            "evidence_recording",
            run_id=run.run_id,
            evidence=(document_id, 0, "Supports the question under review."),
        )
        evidence_response = self._advance(evidence_plan)

        state = evidence_response.research_plan_execution
        assert state is not None
        self.assertEqual(state.status.value, "completed")
        self.assertTrue(state.steps[0].work_performed)
        self.assertEqual(state.steps[0].operation, "evidence_recording")

        final = self.run_manager.get(run.run_id)
        self.assertEqual(len(final.evidence), 1)
        self.assertEqual(final.evidence[0].source_document_id, document_id)
        self.assertEqual(final.claims, ())
        self.assertEqual(final.assessments, ())

    def test_repeated_identical_evidence_fails_honestly_without_duplicate(
        self,
    ) -> None:
        run = self.run_manager.create("What evidence supports the claim?")
        accept_plan = self._start(
            "source_accept",
            run_id=run.run_id,
            authorized_url="https://example.test/chain",
        )
        self._advance(accept_plan)
        document_id = self.run_manager.get(run.run_id).sources[0].document_id
        authorization = (document_id, 0, "Supports the question under review.")
        first = self._advance(
            self._start("evidence_recording", run_id=run.run_id, evidence=authorization)
        )
        assert first.research_plan_execution is not None
        self.assertEqual(first.research_plan_execution.status.value, "completed")
        recorded = self.run_manager.get(run.run_id)

        again = self._advance(
            self._start("evidence_recording", run_id=run.run_id, evidence=authorization)
        )

        state = again.research_plan_execution
        assert state is not None
        self.assertEqual(state.status.value, "failed")
        # Refused before any write: not reported as performed work or success.
        self.assertFalse(state.steps[0].work_performed)
        self.assertIn(recorded.evidence[0].evidence_id, state.steps[0].detail)
        self.assertEqual(self.run_manager.get(run.run_id).evidence, recorded.evidence)

    def test_fetched_but_unaccepted_source_cannot_record_evidence(self) -> None:
        run = self.run_manager.create("What evidence supports the claim?")

        fetch_plan = self._start(
            "source_fetch",
            run_id=run.run_id,
            authorized_url="https://example.test/fetched-only",
        )
        self._advance(fetch_plan)
        self.assertEqual(self.run_manager.get(run.run_id).sources, ())

        document_ids = [
            reference.document_id for reference in self.knowledge_engine.documents()
        ]
        evidence_plan = self._start(
            "evidence_recording",
            run_id=run.run_id,
            evidence=(document_ids[0], 0, "Should not be recordable."),
        )

        response = self._advance(evidence_plan)

        state = response.research_plan_execution
        assert state is not None
        self.assertEqual(state.status.value, "failed")
        self.assertFalse(state.steps[0].work_performed)
        self.assertEqual(self.run_manager.get(run.run_id).evidence, ())

    def test_evidence_recording_without_authorization_fails_the_step(self) -> None:
        run = self.run_manager.create("What evidence supports the claim?")
        plan_id = self._start("evidence_recording", run_id=run.run_id)

        response = self._advance(plan_id)

        state = response.research_plan_execution
        assert state is not None
        self.assertEqual(state.status.value, "failed")
        self.assertFalse(state.steps[0].work_performed)
        self.assertEqual(self.run_manager.get(run.run_id).evidence, ())

    def _start_named(self, draft: ResearchPlanStepDraftInput, run_id: str) -> str:
        response = self.engine.process(
            BrainRequest(
                message="Start research plan",
                metadata={
                    "intent": "research_plan_execution_start",
                    "research_plan_question": "What evidence supports the claim?",
                    "research_plan_steps": (draft,),
                    "research_run_id": run_id,
                },
            )
        )
        self.assertTrue(response.success, response.message)
        assert response.research_plan_execution is not None
        return response.research_plan_execution.plan_id

    def test_named_draft_input_is_accepted_alongside_legacy_tuples(self) -> None:
        run = self.run_manager.create("What evidence supports the claim?")
        plan_id = self._start_named(
            ResearchPlanStepDraftInput(
                instruction="Search local knowledge",
                capability="local_knowledge_search",
            ),
            run.run_id,
        )

        response = self._advance(plan_id)

        state = response.research_plan_execution
        assert state is not None
        self.assertEqual(state.status.value, "completed")
        self.assertEqual(state.steps[0].operation, "local_knowledge_search")

    def test_full_chain_through_assessment(self) -> None:
        run = self.run_manager.create("What evidence supports the claim?")

        accept_plan = self._start(
            "source_accept",
            run_id=run.run_id,
            authorized_url="https://example.test/assessed",
        )
        self._advance(accept_plan)
        document_id = self.run_manager.get(run.run_id).sources[0].document_id

        evidence_plan = self._start(
            "evidence_recording",
            run_id=run.run_id,
            evidence=(document_id, 0, "Directly relevant to the question."),
        )
        self._advance(evidence_plan)
        evidence_id = self.run_manager.get(run.run_id).evidence[0].evidence_id

        assessment_plan = self._start_named(
            ResearchPlanStepDraftInput(
                instruction="Assess the accepted source",
                capability="source_assessment",
                assessment_authorization=ResearchAssessmentAuthorization(
                    document_id=document_id,
                    evidence_ids=(evidence_id,),
                    text="The source states the point directly.",
                    information_trust="medium",  # type: ignore[arg-type]
                ),
            ),
            run.run_id,
        )
        response = self._advance(assessment_plan)

        state = response.research_plan_execution
        assert state is not None
        self.assertEqual(state.status.value, "completed")
        self.assertTrue(state.steps[0].work_performed)
        self.assertEqual(state.steps[0].operation, "source_assessment")

        final = self.run_manager.get(run.run_id)
        self.assertEqual(len(final.assessments), 1)
        self.assertEqual(final.assessments[0].evidence_ids, (evidence_id,))
        self.assertEqual(final.claims, ())
        self.assertEqual(final.claim_contradictions, ())

    def test_assessment_without_authorization_fails_the_step(self) -> None:
        run = self.run_manager.create("What evidence supports the claim?")
        plan_id = self._start("source_assessment", run_id=run.run_id)

        response = self._advance(plan_id)

        state = response.research_plan_execution
        assert state is not None
        self.assertEqual(state.status.value, "failed")
        self.assertFalse(state.steps[0].work_performed)
        self.assertEqual(self.run_manager.get(run.run_id).assessments, ())

    def test_full_chain_accept_evidence_assessment_claim(self) -> None:
        run = self.run_manager.create("What evidence supports the claim?")

        self._advance(
            self._start(
                "source_accept",
                run_id=run.run_id,
                authorized_url="https://example.test/claimed",
            )
        )
        document_id = self.run_manager.get(run.run_id).sources[0].document_id

        self._advance(
            self._start(
                "evidence_recording",
                run_id=run.run_id,
                evidence=(document_id, 0, "Directly relevant to the question."),
            )
        )
        evidence_id = self.run_manager.get(run.run_id).evidence[0].evidence_id

        self._advance(
            self._start_named(
                ResearchPlanStepDraftInput(
                    instruction="Assess the accepted source",
                    capability="source_assessment",
                    assessment_authorization=ResearchAssessmentAuthorization(
                        document_id=document_id,
                        evidence_ids=(evidence_id,),
                        text="The source states the point directly.",
                        information_trust="high",  # type: ignore[arg-type]
                    ),
                ),
                run.run_id,
            )
        )

        response = self._advance(
            self._start_named(
                ResearchPlanStepDraftInput(
                    instruction="Record the authored claim",
                    capability="claim_creation",
                    claim_authorization=ResearchClaimAuthorization(
                        evidence_ids=(evidence_id,),
                        text="The question is supported by the accepted source.",
                        epistemic_state=ResearchEpistemicState.STRONG_EVIDENCE,
                        confidence="medium",  # type: ignore[arg-type]
                    ),
                ),
                run.run_id,
            )
        )

        state = response.research_plan_execution
        assert state is not None
        self.assertEqual(state.status.value, "completed")
        self.assertTrue(state.steps[0].work_performed)
        self.assertEqual(state.steps[0].operation, "claim_creation")

        final = self.run_manager.get(run.run_id)
        self.assertEqual(len(final.sources), 1)
        self.assertEqual(len(final.evidence), 1)
        self.assertEqual(len(final.assessments), 1)
        self.assertEqual(len(final.claims), 1)
        self.assertEqual(final.claims[0].evidence_ids, (evidence_id,))
        self.assertEqual(final.claim_contradictions, ())

    def test_high_trust_assessment_does_not_promote_a_claim(self) -> None:
        run = self.run_manager.create("What evidence supports the claim?")
        self._advance(
            self._start(
                "source_accept",
                run_id=run.run_id,
                authorized_url="https://example.test/unpromoted",
            )
        )
        document_id = self.run_manager.get(run.run_id).sources[0].document_id
        self._advance(
            self._start(
                "evidence_recording",
                run_id=run.run_id,
                evidence=(document_id, 0, "Relevant."),
            )
        )
        evidence_id = self.run_manager.get(run.run_id).evidence[0].evidence_id
        self._advance(
            self._start_named(
                ResearchPlanStepDraftInput(
                    instruction="Assess",
                    capability="source_assessment",
                    assessment_authorization=ResearchAssessmentAuthorization(
                        document_id=document_id,
                        evidence_ids=(evidence_id,),
                        text="Highly trusted source.",
                        information_trust="high",  # type: ignore[arg-type]
                    ),
                ),
                run.run_id,
            )
        )

        self._advance(
            self._start_named(
                ResearchPlanStepDraftInput(
                    instruction="Record a hypothesis",
                    capability="claim_creation",
                    claim_authorization=ResearchClaimAuthorization(
                        evidence_ids=(evidence_id,),
                        text="A cautious hypothesis.",
                        epistemic_state=ResearchEpistemicState.HYPOTHESIS,
                    ),
                ),
                run.run_id,
            )
        )

        claim = self.run_manager.get(run.run_id).claims[0]
        self.assertIs(claim.epistemic_state, ResearchEpistemicState.HYPOTHESIS)
        self.assertEqual(claim.confidence.value, "unassessed")

    def test_claim_creation_without_authorization_fails_the_step(self) -> None:
        run = self.run_manager.create("What evidence supports the claim?")
        plan_id = self._start("claim_creation", run_id=run.run_id)

        response = self._advance(plan_id)

        state = response.research_plan_execution
        assert state is not None
        self.assertEqual(state.status.value, "failed")
        self.assertFalse(state.steps[0].work_performed)
        self.assertEqual(self.run_manager.get(run.run_id).claims, ())

    def _accept_with_evidence(self, run_id: str, slug: str) -> tuple[str, str]:
        self._advance(
            self._start(
                "source_accept",
                run_id=run_id,
                authorized_url=f"https://example.test/{slug}",
            )
        )
        document_id = self.run_manager.get(run_id).sources[-1].document_id
        self._advance(
            self._start(
                "evidence_recording",
                run_id=run_id,
                evidence=(document_id, 0, "Directly relevant."),
            )
        )
        return document_id, self.run_manager.get(run_id).evidence[-1].evidence_id

    def test_contradiction_runs_through_the_engine_route(self) -> None:
        run = self.run_manager.create("What evidence supports the claim?")
        _, first_evidence = self._accept_with_evidence(run.run_id, "c1")
        _, second_evidence = self._accept_with_evidence(run.run_id, "c2")

        for evidence_id, text in (
            (first_evidence, "Saturn has rings."),
            (second_evidence, "Saturn has no rings."),
        ):
            self._advance(
                self._start_named(
                    ResearchPlanStepDraftInput(
                        instruction="Record a claim",
                        capability="claim_creation",
                        claim_authorization=ResearchClaimAuthorization(
                            evidence_ids=(evidence_id,),
                            text=text,
                            epistemic_state=ResearchEpistemicState.LIKELY,
                        ),
                    ),
                    run.run_id,
                )
            )
        claims = self.run_manager.get(run.run_id).claims
        before = claims

        response = self._advance(
            self._start_named(
                ResearchPlanStepDraftInput(
                    instruction="Record the confirmed contradiction",
                    capability="claim_contradiction",
                    contradiction_authorization=ResearchContradictionAuthorization(
                        claim_ids=(claims[0].claim_id, claims[1].claim_id),
                        note="These claims cannot both hold.",
                    ),
                ),
                run.run_id,
            )
        )

        state = response.research_plan_execution
        assert state is not None
        self.assertEqual(state.status.value, "completed")
        self.assertEqual(state.steps[0].operation, "claim_contradiction")
        final = self.run_manager.get(run.run_id)
        self.assertEqual(len(final.claim_contradictions), 1)
        self.assertEqual(final.claims, before)

    def test_comparison_runs_through_the_engine_route(self) -> None:
        run = self.run_manager.create("What evidence supports the claim?")
        first_document, first_evidence = self._accept_with_evidence(run.run_id, "p1")
        second_document, second_evidence = self._accept_with_evidence(run.run_id, "p2")

        assessment_ids = []
        for document_id, evidence_id in (
            (first_document, first_evidence),
            (second_document, second_evidence),
        ):
            self._advance(
                self._start_named(
                    ResearchPlanStepDraftInput(
                        instruction="Assess the source",
                        capability="source_assessment",
                        assessment_authorization=ResearchAssessmentAuthorization(
                            document_id=document_id,
                            evidence_ids=(evidence_id,),
                            text="Authored assessment.",
                        ),
                    ),
                    run.run_id,
                )
            )
            assessment_ids.append(
                self.run_manager.get(run.run_id).assessments[-1].assessment_id
            )

        response = self._advance(
            self._start_named(
                ResearchPlanStepDraftInput(
                    instruction="Compare the accepted sources",
                    capability="source_comparison",
                    comparison_authorization=ResearchComparisonAuthorization(
                        document_ids=(first_document, second_document),
                        evidence_ids=(first_evidence, second_evidence),
                        assessment_ids=tuple(assessment_ids),
                        text="Both sources describe the subject consistently.",
                    ),
                ),
                run.run_id,
            )
        )

        state = response.research_plan_execution
        assert state is not None
        self.assertEqual(state.status.value, "completed")
        self.assertEqual(state.steps[0].operation, "source_comparison")
        final = self.run_manager.get(run.run_id)
        self.assertEqual(len(final.comparison_notes), 1)
        self.assertEqual(final.claims, ())
        self.assertEqual(final.claim_contradictions, ())

    def test_contradiction_and_comparison_without_authorization_fail(self) -> None:
        run = self.run_manager.create("What evidence supports the claim?")

        for capability in ("claim_contradiction", "source_comparison"):
            with self.subTest(capability=capability):
                response = self._advance(self._start(capability, run_id=run.run_id))
                state = response.research_plan_execution
                assert state is not None
                self.assertEqual(state.status.value, "failed")
                self.assertFalse(state.steps[0].work_performed)

        final = self.run_manager.get(run.run_id)
        self.assertEqual(final.claim_contradictions, ())
        self.assertEqual(final.comparison_notes, ())

    def test_finishing_execution_does_not_close_the_run(self) -> None:
        run = self.run_manager.create("What evidence supports the claim?")
        plan_id = self._start("local_knowledge_search")

        response = self._advance(plan_id)

        state = response.research_plan_execution
        assert state is not None
        self.assertEqual(state.status.value, "completed")
        self.assertIs(
            self.run_manager.get(run.run_id).status,
            ResearchRunStatus.COLLECTING,
        )

    def test_completion_capability_respects_domain_rules(self) -> None:
        run = self.run_manager.create("What evidence supports the claim?")

        response = self._advance(
            self._start_named(
                ResearchPlanStepDraftInput(
                    instruction="Close the run",
                    capability="research_run_completion",
                    completion_authorization=ResearchCompletionAuthorization(
                        target_status=ResearchRunStatus.COMPLETED
                    ),
                ),
                run.run_id,
            )
        )

        state = response.research_plan_execution
        assert state is not None
        self.assertEqual(state.status.value, "failed")
        self.assertTrue(state.steps[0].work_performed)
        self.assertEqual(state.steps[0].operation, "research_run_completion")
        self.assertIn("The run remains open", state.steps[0].detail)
        self.assertIs(
            self.run_manager.get(run.run_id).status,
            ResearchRunStatus.COLLECTING,
        )

    def test_complete_chain_closes_the_run_and_retains_uncertainty(self) -> None:
        run = self.run_manager.create("What evidence supports the claim?")
        document_id, evidence_id = self._accept_with_evidence(run.run_id, "final")

        self._advance(
            self._start_named(
                ResearchPlanStepDraftInput(
                    instruction="Record a hypothesis",
                    capability="claim_creation",
                    claim_authorization=ResearchClaimAuthorization(
                        evidence_ids=(evidence_id,),
                        text="A cautious hypothesis.",
                        epistemic_state=ResearchEpistemicState.HYPOTHESIS,
                    ),
                ),
                run.run_id,
            )
        )

        response = self._advance(
            self._start_named(
                ResearchPlanStepDraftInput(
                    instruction="Close the run",
                    capability="research_run_completion",
                    completion_authorization=ResearchCompletionAuthorization(
                        target_status=ResearchRunStatus.COMPLETED
                    ),
                ),
                run.run_id,
            )
        )

        state = response.research_plan_execution
        assert state is not None
        self.assertEqual(state.status.value, "completed")
        self.assertIn("1 unresolved claim(s)", state.steps[0].detail)
        self.assertIn("resolves nothing", state.steps[0].detail)

        closed = self.run_manager.get(run.run_id)
        self.assertIs(closed.status, ResearchRunStatus.COMPLETED)
        self.assertEqual(len(closed.sources), 1)
        self.assertEqual(len(closed.evidence), 1)
        self.assertIs(
            closed.claims[0].epistemic_state,
            ResearchEpistemicState.HYPOTHESIS,
        )
        self.assertEqual(document_id, closed.sources[0].document_id)


if __name__ == "__main__":
    unittest.main()
