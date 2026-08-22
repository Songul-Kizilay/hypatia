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
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.MemoryManager import MemoryManager
from planner.Planner import Planner
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchEvidenceIntegrityAuditor import (
    ResearchEvidenceIntegrityAuditor,
)
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchRunManager import ResearchRunManager
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


EXPECTED_OPERATIONS = {
    ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH: "local_knowledge_search",
    ResearchPlanStepCapability.ACCEPTED_SOURCE_LISTING: "accepted_source_listing",
    ResearchPlanStepCapability.EVIDENCE_INTEGRITY_CHECK: "evidence_integrity_check",
    ResearchPlanStepCapability.SOURCE_DISCOVERY: "source_discovery",
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
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _registry(self):  # type: ignore[no-untyped-def]
        return self.engine._research_plan_execution_service._operation_registry

    def _start(self, capability: str, run_id: str | None = None) -> str:
        metadata: dict[str, object] = {
            "intent": "research_plan_execution_start",
            "research_plan_question": "What evidence supports the claim?",
            "research_plan_steps": (("Authored instruction", (), capability),),
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


if __name__ == "__main__":
    unittest.main()
