"""Bounded autonomous continuation of an approved research execution.

Every budget is asserted to be enforced rather than advisory, and time is
injected so no test sleeps. Autonomy drives the real execution service through
the real engine, so anything it could invent would show up here.
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
from cognition.ResearchAutonomyApplicationService import (
    ResearchAutonomyApplicationService,
)
from cognition.ResearchAutonomyEvents import AUTONOMY_STARTED, AUTONOMY_STOPPED
from core.CancellationSignal import CancellationSignal
from core.Exceptions import ResearchError
from eventbus.Event import Event
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.MemoryManager import MemoryManager
from planner.Planner import Planner
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchAutonomyResult import AutonomyStopReason
from research.ResearchCapabilityCost import CAPABILITY_COSTS, cost_for
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchPlanStepDraftInput import ResearchPlanStepDraftInput
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSource import ResearchSource
from research.ResearchSourceCandidate import ResearchSourceCandidate
from response.ResponseComposer import ResponseComposer
from session.SessionManager import SessionManager
from session.SessionRenameTransactionService import SessionRenameTransactionService

QUESTION = "Does the ring system have a measured age?"


class StubClock:
    """Advance only when a test says so, so no run ever sleeps."""

    def __init__(self, step_seconds: float = 0.0) -> None:
        self.now = 0.0
        self.step_seconds = step_seconds

    def __call__(self) -> float:
        value = self.now
        self.now += self.step_seconds
        return value


class CountingDiscoveryProvider:
    def __init__(self) -> None:
        self.queries: list[str] = []

    @property
    def provider_name(self) -> str:
        return "counting_discovery"

    def discover(self, query: str, *, limit: int) -> list[ResearchSourceCandidate]:
        del limit
        self.queries.append(query)
        return [
            ResearchSourceCandidate(
                url="https://example.test/candidate",
                title="Candidate",
                snippet="A snippet.",
            )
        ]


class CountingSourceFetcher:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def fetch(self, url: str) -> ResearchSource:
        self.urls.append(url)
        return ResearchSource(
            url=url,
            title="A source",
            content="Saturn has a prominent ring system.",
            content_type="text/html",
            fetched_at=datetime(2026, 8, 1, tzinfo=UTC),
        )


class AutonomyFixture(unittest.TestCase):
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
        self.discovery_provider = CountingDiscoveryProvider()
        self.source_fetcher = CountingSourceFetcher()
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
            research_source_discovery_provider=self.discovery_provider,
            research_source_fetcher=self.source_fetcher,
        )
        self.events: list[Event] = []
        self.event_bus.subscribe("*", self.events.append)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def use_clock(self, clock: StubClock) -> None:
        """Replace the autonomy clock without touching execution behavior."""
        self.engine._research_autonomy_service = ResearchAutonomyApplicationService(
            self.engine._research_plan_execution_service,
            ResponseComposer(),
            event_bus=self.event_bus,
            clock=clock,
        )

    def start(self, *drafts: ResearchPlanStepDraftInput, run_id: str | None = None):  # type: ignore[no-untyped-def]
        metadata: dict[str, object] = {
            "intent": "research_plan_execution_start",
            "research_plan_question": QUESTION,
            "research_plan_steps": drafts,
        }
        if run_id is not None:
            metadata["research_run_id"] = run_id
        response = self.engine.process(
            BrainRequest(message="Start research plan", metadata=metadata)
        )
        assert response.research_plan_execution is not None
        return response.research_plan_execution.plan_id

    def run_autonomy(  # type: ignore[no-untyped-def]
        self,
        plan_id: str,
        budget: ResearchAutonomyBudget | None = None,
        cancellation_token: object = None,
    ):
        metadata: dict[str, object] = {
            "intent": "research_autonomy_run",
            "research_plan_id": plan_id,
        }
        if budget is not None:
            metadata["research_autonomy_budget"] = budget
        return self.engine.process(
            BrainRequest(
                message="Run research autonomy",
                metadata=metadata,
                cancellation_token=cancellation_token,  # type: ignore[arg-type]
            )
        )

    @staticmethod
    def search_step() -> ResearchPlanStepDraftInput:
        return ResearchPlanStepDraftInput(
            instruction="Search local knowledge",
            capability="local_knowledge_search",
        )

    @staticmethod
    def discovery_step() -> ResearchPlanStepDraftInput:
        return ResearchPlanStepDraftInput(
            instruction="Discover candidate sources",
            capability="source_discovery",
        )


class ResearchAutonomyTests(AutonomyFixture):
    def test_completes_a_small_plan_within_budget(self) -> None:
        plan_id = self.start(self.search_step(), self.search_step())

        response = self.run_autonomy(plan_id)

        result = response.research_autonomy
        assert result is not None
        self.assertTrue(response.success)
        self.assertIs(result.stop_reason, AutonomyStopReason.EXECUTION_TERMINAL)
        self.assertEqual(result.execution_status, "completed")
        self.assertEqual(result.steps_attempted, 2)
        self.assertEqual(result.operations_performed, 2)
        self.assertEqual(result.network_operations, 0)
        self.assertEqual(result.llm_operations, 0)

    def test_stops_exactly_at_the_step_budget(self) -> None:
        plan_id = self.start(*(self.search_step() for _ in range(4)))

        response = self.run_autonomy(
            plan_id,
            ResearchAutonomyBudget(max_step_advances=2),
        )

        result = response.research_autonomy
        assert result is not None
        self.assertIs(result.stop_reason, AutonomyStopReason.STEP_BUDGET_EXHAUSTED)
        self.assertEqual(result.steps_attempted, 2)
        self.assertEqual(result.execution_status, "running")

    def test_stops_before_exceeding_the_network_budget(self) -> None:
        run = self.run_manager.create(QUESTION)
        plan_id = self.start(
            self.discovery_step(),
            self.discovery_step(),
            run_id=run.run_id,
        )

        response = self.run_autonomy(
            plan_id,
            ResearchAutonomyBudget(max_network_operations=1),
        )

        result = response.research_autonomy
        assert result is not None
        self.assertIs(result.stop_reason, AutonomyStopReason.NETWORK_BUDGET_EXHAUSTED)
        self.assertEqual(result.network_operations, 1)
        self.assertEqual(len(self.discovery_provider.queries), 1)

    def test_zero_network_budget_prevents_any_network_operation(self) -> None:
        run = self.run_manager.create(QUESTION)
        plan_id = self.start(self.discovery_step(), run_id=run.run_id)

        response = self.run_autonomy(
            plan_id,
            ResearchAutonomyBudget(max_network_operations=0),
        )

        result = response.research_autonomy
        assert result is not None
        self.assertIs(result.stop_reason, AutonomyStopReason.NETWORK_BUDGET_EXHAUSTED)
        self.assertEqual(result.steps_attempted, 0)
        self.assertEqual(self.discovery_provider.queries, [])

    def test_llm_budget_is_enforced_from_declared_cost(self) -> None:
        self.assertEqual(
            cost_for(ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH).llm_operations,
            0,
        )
        plan_id = self.start(self.search_step())

        response = self.run_autonomy(
            plan_id,
            ResearchAutonomyBudget(max_llm_operations=0),
        )

        result = response.research_autonomy
        assert result is not None
        self.assertEqual(result.llm_operations, 0)
        self.assertIsNot(result.stop_reason, AutonomyStopReason.LLM_BUDGET_EXHAUSTED)

    def test_zero_step_budget_attempts_nothing(self) -> None:
        plan_id = self.start(self.search_step())

        response = self.run_autonomy(
            plan_id,
            ResearchAutonomyBudget(max_step_advances=0),
        )

        result = response.research_autonomy
        assert result is not None
        self.assertIs(result.stop_reason, AutonomyStopReason.STEP_BUDGET_EXHAUSTED)
        self.assertEqual(result.steps_attempted, 0)
        self.assertEqual(result.operations_performed, 0)

    def test_wall_clock_exhaustion_uses_the_injected_clock(self) -> None:
        self.use_clock(StubClock(step_seconds=5.0))
        plan_id = self.start(*(self.search_step() for _ in range(5)))

        response = self.run_autonomy(
            plan_id,
            ResearchAutonomyBudget(max_seconds=6.0),
        )

        result = response.research_autonomy
        assert result is not None
        self.assertIs(result.stop_reason, AutonomyStopReason.TIME_BUDGET_EXHAUSTED)
        self.assertGreater(result.elapsed_seconds, 0.0)
        self.assertLess(result.steps_attempted, 5)

    def test_cancellation_stops_the_loop(self) -> None:
        plan_id = self.start(*(self.search_step() for _ in range(3)))
        signal = CancellationSignal()
        signal.cancel()

        response = self.run_autonomy(plan_id, cancellation_token=signal)

        result = response.research_autonomy
        assert result is not None
        self.assertIs(result.stop_reason, AutonomyStopReason.CANCELLED)
        self.assertEqual(result.steps_attempted, 0)

    def test_blocked_step_stops_autonomy(self) -> None:
        plan_id = self.start(
            ResearchPlanStepDraftInput(instruction="No capability declared"),
            self.search_step(),
        )

        response = self.run_autonomy(plan_id)

        result = response.research_autonomy
        assert result is not None
        self.assertIs(result.stop_reason, AutonomyStopReason.STEP_BLOCKED)
        self.assertEqual(result.steps_attempted, 1)
        self.assertEqual(result.operations_performed, 0)

    def test_failed_operation_stops_autonomy(self) -> None:
        run = self.run_manager.create(QUESTION)
        plan_id = self.start(
            ResearchPlanStepDraftInput(
                instruction="Fetch without authorization",
                capability="source_fetch",
            ),
            self.search_step(),
            run_id=run.run_id,
        )

        response = self.run_autonomy(plan_id)

        result = response.research_autonomy
        assert result is not None
        self.assertIs(result.stop_reason, AutonomyStopReason.STEP_FAILED)
        self.assertEqual(result.steps_attempted, 1)
        self.assertEqual(result.operations_performed, 0)
        self.assertEqual(self.source_fetcher.urls, [])

    def test_autonomy_invents_no_capability(self) -> None:
        plan_id = self.start(
            ResearchPlanStepDraftInput(
                instruction="Please run a local knowledge search and fetch sources",
            )
        )

        response = self.run_autonomy(plan_id)

        result = response.research_autonomy
        assert result is not None
        self.assertIs(result.stop_reason, AutonomyStopReason.STEP_BLOCKED)
        self.assertEqual(self.source_fetcher.urls, [])
        self.assertEqual(self.discovery_provider.queries, [])

    def test_autonomy_accepts_no_source_and_promotes_no_claim(self) -> None:
        run = self.run_manager.create(QUESTION)
        plan_id = self.start(self.discovery_step(), run_id=run.run_id)

        self.run_autonomy(plan_id)

        stored = self.run_manager.get(run.run_id)
        self.assertEqual(len(stored.discoveries), 1)
        self.assertEqual(stored.sources, ())
        self.assertEqual(stored.evidence, ())
        self.assertEqual(stored.claims, ())
        self.assertEqual(stored.assessments, ())
        self.assertEqual(stored.claim_contradictions, ())

    def test_autonomy_causes_no_duplicate_side_effects(self) -> None:
        run = self.run_manager.create(QUESTION)
        plan_id = self.start(self.discovery_step(), run_id=run.run_id)

        self.run_autonomy(plan_id)
        second = self.run_autonomy(plan_id)

        result = second.research_autonomy
        assert result is not None
        self.assertIs(result.stop_reason, AutonomyStopReason.EXECUTION_TERMINAL)
        self.assertEqual(result.steps_attempted, 0)
        self.assertEqual(len(self.discovery_provider.queries), 1)
        self.assertEqual(len(self.run_manager.get(run.run_id).discoveries), 1)

    def test_manual_execution_behavior_is_unchanged(self) -> None:
        plan_id = self.start(self.search_step())

        manual = self.engine.process(
            BrainRequest(
                message="Advance research plan",
                metadata={
                    "intent": "research_plan_execution_advance",
                    "research_plan_id": plan_id,
                },
            )
        )

        state = manual.research_plan_execution
        assert state is not None
        self.assertEqual(state.status.value, "completed")
        self.assertEqual(state.steps[0].operation, "local_knowledge_search")

    def test_missing_live_execution_is_refused(self) -> None:
        response = self.run_autonomy("plan-that-never-existed")

        self.assertFalse(response.success)
        self.assertIsNone(response.research_autonomy)
        self.assertIn("never creates or authorizes a plan", response.message)

    def test_autonomy_events_are_bounded(self) -> None:
        plan_id = self.start(self.search_step())
        self.events.clear()

        self.run_autonomy(plan_id)

        autonomy_events = [
            event
            for event in self.events
            if event.name.startswith("research.autonomy.")
        ]
        self.assertEqual(
            [event.name for event in autonomy_events],
            [AUTONOMY_STARTED, AUTONOMY_STOPPED],
        )
        encoded = repr([event.payload for event in autonomy_events])
        self.assertNotIn("Search local knowledge", encoded)
        self.assertNotIn(QUESTION, encoded)


class ResearchAutonomyBudgetTests(unittest.TestCase):
    def test_rejects_invalid_budgets(self) -> None:
        for kwargs in (
            {"max_step_advances": -1},
            {"max_step_advances": True},
            {"max_step_advances": 51},
            {"max_network_operations": -1},
            {"max_network_operations": 26},
            {"max_llm_operations": -1},
            {"max_seconds": -1.0},
            {"max_seconds": 3_601.0},
            {"max_seconds": "60"},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ResearchError):
                    ResearchAutonomyBudget(**kwargs)  # type: ignore[arg-type]

    def test_defaults_are_conservative(self) -> None:
        budget = ResearchAutonomyBudget()

        self.assertEqual(budget.max_step_advances, 5)
        self.assertEqual(budget.max_network_operations, 3)
        self.assertEqual(budget.max_llm_operations, 0)
        self.assertEqual(budget.max_seconds, 60.0)


class ResearchCapabilityCostTests(unittest.TestCase):
    def test_every_capability_declares_a_cost(self) -> None:
        for capability in ResearchPlanStepCapability:
            with self.subTest(capability=capability):
                self.assertIn(capability, CAPABILITY_COSTS)
                cost_for(capability)

    def test_network_capabilities_are_declared_not_inferred(self) -> None:
        networked = {
            capability
            for capability, cost in CAPABILITY_COSTS.items()
            if cost.network_operations > 0
        }

        self.assertEqual(
            networked,
            {
                ResearchPlanStepCapability.SOURCE_DISCOVERY,
                ResearchPlanStepCapability.SOURCE_FETCH,
                ResearchPlanStepCapability.SOURCE_ACCEPT,
                ResearchPlanStepCapability.SOURCE_REVALIDATION,
                ResearchPlanStepCapability.SEMANTIC_EVIDENCE_PROPOSAL,
                ResearchPlanStepCapability.SEMANTIC_EVIDENCE_COMPARISON,
            },
        )

    def test_invalid_capability_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            cost_for("source_fetch")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
