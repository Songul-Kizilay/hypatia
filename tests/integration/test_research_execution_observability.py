"""Bounded observability for research-plan execution.

Every payload is checked against the authored content that produced it, so a
future change that starts leaking instructions, notes, URLs, questions, or
exception messages fails here rather than in a log somewhere.
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
from cognition.ResearchPlanExecutionEvents import (
    EXECUTION_CANCELLED,
    EXECUTION_STARTED,
    EXECUTION_STEP_BLOCKED,
    EXECUTION_STEP_COMPLETED,
    EXECUTION_STEP_FAILED,
    EXECUTION_STEP_STARTED,
    ExecutionBlockReason,
    ResearchPlanExecutionEvents,
)
from eventbus.Event import Event
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.MemoryManager import MemoryManager
from planner.Planner import Planner
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchPlanStepDraftInput import ResearchPlanStepDraftInput
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSource import ResearchSource
from response.ResponseComposer import ResponseComposer
from session.SessionManager import SessionManager
from session.SessionRenameTransactionService import SessionRenameTransactionService

QUESTION = "Does the ring system have a measured age?"
SECRET_INSTRUCTION = "SECRET-INSTRUCTION-TEXT-THAT-MUST-NOT-LEAK"
AUTHORIZED_URL = "https://example.test/secret-path-that-must-not-leak"


class ScenarioSourceFetcher:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def fetch(self, url: str) -> ResearchSource:
        self.urls.append(url)
        return ResearchSource(
            url=url,
            title="A source",
            content="SOURCE-BODY-THAT-MUST-NOT-LEAK",
            content_type="text/html",
            fetched_at=datetime(2026, 8, 1, tzinfo=UTC),
        )


class ResearchExecutionObservabilityTests(unittest.TestCase):
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
        self.source_fetcher = ScenarioSourceFetcher()
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
            research_source_fetcher=self.source_fetcher,
        )
        self.events: list[Event] = []
        self.event_bus.subscribe("*", self.events.append)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _execution_events(self) -> list[Event]:
        return [
            event
            for event in self.events
            if event.name.startswith("research.plan.execution.")
        ]

    def _start(self, draft: ResearchPlanStepDraftInput, run_id: str | None) -> str:
        metadata: dict[str, object] = {
            "intent": "research_plan_execution_start",
            "research_plan_question": QUESTION,
            "research_plan_steps": (draft,),
        }
        if run_id is not None:
            metadata["research_run_id"] = run_id
        response = self.engine.process(
            BrainRequest(message="Start research plan", metadata=metadata)
        )
        assert response.research_plan_execution is not None
        return response.research_plan_execution.plan_id

    def _advance(self, plan_id: str) -> None:
        self.engine.process(
            BrainRequest(
                message="Advance research plan",
                metadata={
                    "intent": "research_plan_execution_advance",
                    "research_plan_id": plan_id,
                },
            )
        )

    def test_successful_step_emits_started_then_completed(self) -> None:
        plan_id = self._start(
            ResearchPlanStepDraftInput(
                instruction=SECRET_INSTRUCTION,
                capability="local_knowledge_search",
            ),
            None,
        )

        self._advance(plan_id)

        names = [event.name for event in self._execution_events()]
        self.assertEqual(
            names,
            [EXECUTION_STARTED, EXECUTION_STEP_STARTED, EXECUTION_STEP_COMPLETED],
        )
        started, step_started, completed = self._execution_events()
        self.assertEqual(
            started.payload,
            {"plan_id": plan_id, "steps": 1, "bound_research_run": False},
        )
        self.assertEqual(
            step_started.payload,
            {
                "plan_id": plan_id,
                "step_id": "step-1",
                "capability": "local_knowledge_search",
                "operation": "local_knowledge_search",
            },
        )
        self.assertEqual(
            completed.payload,
            {
                "plan_id": plan_id,
                "step_id": "step-1",
                "operation": "local_knowledge_search",
                "work_performed": True,
            },
        )
        self.assertTrue(
            all(event.source == "research.execution" for event in [started, completed])
        )

    def test_payloads_never_contain_authored_content(self) -> None:
        run = self.run_manager.create(QUESTION)
        plan_id = self._start(
            ResearchPlanStepDraftInput(
                instruction=SECRET_INSTRUCTION,
                capability="source_fetch",
                authorized_source_url=AUTHORIZED_URL,
            ),
            run.run_id,
        )

        self._advance(plan_id)

        encoded = repr([event.payload for event in self._execution_events()])
        for forbidden in (
            SECRET_INSTRUCTION,
            AUTHORIZED_URL,
            QUESTION,
            "SOURCE-BODY-THAT-MUST-NOT-LEAK",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, encoded)

    def test_bound_run_is_reported_as_a_boolean_not_an_identifier(self) -> None:
        run = self.run_manager.create(QUESTION)

        plan_id = self._start(
            ResearchPlanStepDraftInput(
                instruction="Search",
                capability="local_knowledge_search",
            ),
            run.run_id,
        )

        started = self._execution_events()[0]
        self.assertEqual(
            started.payload,
            {"plan_id": plan_id, "steps": 1, "bound_research_run": True},
        )
        self.assertNotIn(run.run_id, repr(started.payload))

    def test_undeclared_capability_emits_a_bounded_block_reason(self) -> None:
        plan_id = self._start(
            ResearchPlanStepDraftInput(instruction=SECRET_INSTRUCTION),
            None,
        )

        self._advance(plan_id)

        blocked = self._execution_events()[-1]
        self.assertEqual(blocked.name, EXECUTION_STEP_BLOCKED)
        self.assertEqual(
            blocked.payload,
            {
                "plan_id": plan_id,
                "step_id": "step-1",
                "reason": ExecutionBlockReason.NO_DECLARED_CAPABILITY.value,
            },
        )

    def test_unregistered_capability_emits_its_own_reason(self) -> None:
        plan_id = self._start(
            ResearchPlanStepDraftInput(
                instruction="Discover",
                capability="source_discovery",
            ),
            None,
        )

        self._advance(plan_id)

        blocked = self._execution_events()[-1]
        self.assertEqual(blocked.name, EXECUTION_STEP_BLOCKED)
        self.assertEqual(
            blocked.payload["reason"],
            ExecutionBlockReason.UNREGISTERED_CAPABILITY.value,
        )

    def test_failed_operation_reports_cause_class_without_message(self) -> None:
        run = self.run_manager.create(QUESTION)
        plan_id = self._start(
            ResearchPlanStepDraftInput(
                instruction="Fetch without authorization",
                capability="source_fetch",
            ),
            run.run_id,
        )

        self._advance(plan_id)

        failed = self._execution_events()[-1]
        self.assertEqual(failed.name, EXECUTION_STEP_FAILED)
        self.assertEqual(
            failed.payload,
            {
                "plan_id": plan_id,
                "step_id": "step-1",
                "operation": "source_fetch",
                "cause": "ResearchError",
                "work_performed": False,
            },
        )
        self.assertNotIn("authorized", repr(failed.payload))

    def test_cancellation_reports_surviving_progress(self) -> None:
        plan_id = self._start(
            ResearchPlanStepDraftInput(
                instruction="Search",
                capability="local_knowledge_search",
            ),
            None,
        )

        self.engine.process(
            BrainRequest(
                message="Cancel research plan",
                metadata={
                    "intent": "research_plan_execution_cancel",
                    "research_plan_id": plan_id,
                },
            )
        )

        cancelled = self._execution_events()[-1]
        self.assertEqual(cancelled.name, EXECUTION_CANCELLED)
        self.assertEqual(
            cancelled.payload,
            {
                "plan_id": plan_id,
                "completed_steps": 0,
                "steps_with_research_work": 0,
            },
        )

    def test_observability_never_changes_behavior(self) -> None:
        quiet_engine = CognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            Planner(),
            EventBus(),
            ResponseComposer(),
            self.session_manager,
            SessionRenameTransactionService(
                session_manager=self.session_manager,
                memory_manager=self.memory_manager,
                event_bus=self.event_bus,
            ),
            research_run_manager=self.run_manager,
        )
        draft = ResearchPlanStepDraftInput(
            instruction="Search",
            capability="local_knowledge_search",
        )

        loud_plan = self._start(draft, None)
        self._advance(loud_plan)
        loud_state = self.engine.process(
            BrainRequest(
                message="Status",
                metadata={
                    "intent": "research_plan_execution_status",
                    "research_plan_id": loud_plan,
                },
            )
        ).research_plan_execution

        quiet_start = quiet_engine.process(
            BrainRequest(
                message="Start research plan",
                metadata={
                    "intent": "research_plan_execution_start",
                    "research_plan_question": QUESTION,
                    "research_plan_steps": (draft,),
                },
            )
        )
        assert quiet_start.research_plan_execution is not None
        quiet_plan = quiet_start.research_plan_execution.plan_id
        quiet_engine.process(
            BrainRequest(
                message="Advance",
                metadata={
                    "intent": "research_plan_execution_advance",
                    "research_plan_id": quiet_plan,
                },
            )
        )
        quiet_state = quiet_engine.process(
            BrainRequest(
                message="Status",
                metadata={
                    "intent": "research_plan_execution_status",
                    "research_plan_id": quiet_plan,
                },
            )
        ).research_plan_execution

        assert loud_state is not None and quiet_state is not None
        self.assertEqual(loud_state.snapshot(), quiet_state.snapshot())
        self.assertEqual(loud_state.status, quiet_state.status)


class ResearchPlanExecutionEventsTests(unittest.TestCase):
    def test_absent_event_bus_is_a_no_op(self) -> None:
        events = ResearchPlanExecutionEvents(None)

        events.step_started("plan-1", "step-1", "capability", "operation")
        events.step_completed("plan-1", "step-1", "operation")
        events.step_blocked(
            "plan-1",
            "step-1",
            ExecutionBlockReason.NO_DECLARED_CAPABILITY,
        )
        events.step_failed("plan-1", "step-1", "operation", "Cause", False)

    def test_block_reasons_are_bounded(self) -> None:
        self.assertEqual(
            {reason.value for reason in ExecutionBlockReason},
            {
                "no_declared_capability",
                "unregistered_capability",
                "operation_performed_nothing",
            },
        )


if __name__ == "__main__":
    unittest.main()
