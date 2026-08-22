from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from itertools import count
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainRequest import BrainRequest
from cognition.ResearchPlanExecutionApplicationService import (
    RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT,
    RESEARCH_PLAN_EXECUTION_CANCEL_INTENT,
    RESEARCH_PLAN_EXECUTION_START_INTENT,
    RESEARCH_PLAN_EXECUTION_STATUS_INTENT,
    ResearchPlanExecutionApplicationService,
)
from core.Exceptions import ResearchError
from research.ResearchPlanDraftService import ResearchPlanDraftService
from research.ResearchPlanExecutionStatus import ResearchPlanExecutionStatus
from research.ResearchPlanStepOperationResult import (
    ResearchPlanStepOperationResult,
)
from research.ResearchPlanStepStatus import ResearchPlanStepStatus
from response.ResponseComposer import ResponseComposer

STEPS = (
    ("Collect candidate sources", ()),
    ("Compare accepted sources", ()),
)


def start_request(plan_steps: tuple = STEPS) -> BrainRequest:
    return BrainRequest(
        message="Start research plan",
        metadata={
            "intent": RESEARCH_PLAN_EXECUTION_START_INTENT,
            "research_plan_question": "What evidence supports the claim?",
            "research_plan_steps": plan_steps,
        },
    )


def plan_request(intent: str, plan_id: str) -> BrainRequest:
    return BrainRequest(
        message="Research plan execution",
        metadata={"intent": intent, "research_plan_id": plan_id},
    )


class ResearchPlanExecutionApplicationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.identifiers = count(1)
        self.service = ResearchPlanExecutionApplicationService(
            ResponseComposer(),
            ResearchPlanDraftService(
                clock=lambda: datetime(2026, 8, 23, tzinfo=UTC),
                id_factory=lambda: f"plan-{next(self.identifiers)}",
            ),
        )

    def test_recognizes_only_the_exact_structured_intents(self) -> None:
        self.assertTrue(self.service.is_start_request(start_request()))
        self.assertTrue(
            self.service.is_status_request(
                plan_request(RESEARCH_PLAN_EXECUTION_STATUS_INTENT, "plan-1")
            )
        )
        self.assertTrue(
            self.service.is_cancel_request(
                plan_request(RESEARCH_PLAN_EXECUTION_CANCEL_INTENT, "plan-1")
            )
        )
        self.assertFalse(
            self.service.is_start_request(BrainRequest(message="start research plan"))
        )

    def test_start_creates_running_state_without_advancing_a_step(self) -> None:
        response = self.service.process_start(start_request())

        self.assertTrue(response.success)
        state = response.research_plan_execution
        assert state is not None
        self.assertIs(state.status, ResearchPlanExecutionStatus.RUNNING)
        self.assertEqual(state.completed_steps, 0)
        self.assertEqual(state.pending_steps, 2)
        self.assertIsNone(state.running_step_id)
        self.assertTrue(
            all(step.status is ResearchPlanStepStatus.PENDING for step in state.steps)
        )

    def test_start_never_reports_performed_research_work(self) -> None:
        response = self.service.process_start(start_request())

        state = response.research_plan_execution
        assert state is not None
        self.assertFalse(state.performed_research_work)
        self.assertEqual(state.steps_with_research_work, 0)
        self.assertIn("Research operations performed: 0", response.message)
        self.assertIn("No research work has run", response.message)
        self.assertIn(
            "Source discovery, fetching, evidence, and claims: not performed",
            response.message,
        )
        self.assertIn("Persistent writes: not used", response.message)

    def test_status_message_states_the_ephemeral_boundary(self) -> None:
        started = self.service.process_start(start_request())
        assert started.research_plan_execution is not None
        plan_id = started.research_plan_execution.plan_id

        response = self.service.process_status(
            plan_request(RESEARCH_PLAN_EXECUTION_STATUS_INTENT, plan_id)
        )

        self.assertTrue(response.success)
        self.assertIn(
            "Execution state: in-memory only, lost when Hypatia exits",
            response.message,
        )

    def test_duplicate_start_is_rejected_deterministically(self) -> None:
        fixed = ResearchPlanExecutionApplicationService(
            ResponseComposer(),
            ResearchPlanDraftService(
                clock=lambda: datetime(2026, 8, 23, tzinfo=UTC),
                id_factory=lambda: "plan-fixed",
            ),
        )
        first = fixed.process_start(start_request())
        second = fixed.process_start(start_request())

        self.assertTrue(first.success)
        self.assertFalse(second.success)
        self.assertIn(
            "already has execution state in this process",
            second.message,
        )
        self.assertIn("Execution: not started", second.message)
        status = fixed.process_status(
            plan_request(RESEARCH_PLAN_EXECUTION_STATUS_INTENT, "plan-fixed")
        )
        assert status.research_plan_execution is not None
        self.assertIs(
            status.research_plan_execution.status,
            ResearchPlanExecutionStatus.RUNNING,
        )

    def test_unknown_plan_reports_lost_ephemeral_state(self) -> None:
        response = self.service.process_status(
            plan_request(RESEARCH_PLAN_EXECUTION_STATUS_INTENT, "plan-missing")
        )

        self.assertFalse(response.success)
        self.assertIsNone(response.research_plan_execution)
        self.assertIn("holds no execution state", response.message)
        self.assertIn("It is not resumed after a restart.", response.message)

    def test_cancel_marks_unfinished_steps_cancelled(self) -> None:
        started = self.service.process_start(start_request())
        assert started.research_plan_execution is not None
        plan_id = started.research_plan_execution.plan_id

        response = self.service.process_cancel(
            plan_request(RESEARCH_PLAN_EXECUTION_CANCEL_INTENT, plan_id)
        )

        state = response.research_plan_execution
        assert state is not None
        self.assertIs(state.status, ResearchPlanExecutionStatus.CANCELLED)
        self.assertTrue(
            all(step.status is ResearchPlanStepStatus.CANCELLED for step in state.steps)
        )
        self.assertFalse(state.performed_research_work)

    def test_cancel_preserves_completed_step_history(self) -> None:
        started = self.service.process_start(start_request())
        assert started.research_plan_execution is not None
        plan_id = started.research_plan_execution.plan_id
        advanced = (
            self.service._executions[plan_id]
            .start_step("step-1")
            .complete_step("step-1", "verified source", work_performed=True)
        )
        self.service._executions[plan_id] = advanced

        response = self.service.process_cancel(
            plan_request(RESEARCH_PLAN_EXECUTION_CANCEL_INTENT, plan_id)
        )

        state = response.research_plan_execution
        assert state is not None
        self.assertIs(state.status, ResearchPlanExecutionStatus.CANCELLED)
        self.assertIs(state.steps[0].status, ResearchPlanStepStatus.COMPLETED)
        self.assertTrue(state.steps[0].work_performed)
        self.assertIs(state.steps[1].status, ResearchPlanStepStatus.CANCELLED)
        self.assertEqual(state.completed_steps, 1)
        self.assertEqual(state.steps_with_research_work, 1)
        self.assertIn("Research operations performed: 1", response.message)
        self.assertNotIn("No research work has run", response.message)

    def test_manual_advance_without_work_is_reported_as_no_research(self) -> None:
        started = self.service.process_start(start_request())
        assert started.research_plan_execution is not None
        plan_id = started.research_plan_execution.plan_id
        advanced = (
            self.service._executions[plan_id]
            .start_step("step-1")
            .complete_step("step-1", "state advanced only")
        )
        self.service._executions[plan_id] = advanced

        response = self.service.process_status(
            plan_request(RESEARCH_PLAN_EXECUTION_STATUS_INTENT, plan_id)
        )

        state = response.research_plan_execution
        assert state is not None
        self.assertEqual(state.completed_steps, 1)
        self.assertEqual(state.steps_with_research_work, 0)
        self.assertFalse(state.performed_research_work)
        self.assertIn("Research operations performed: 0", response.message)
        self.assertIn("No research work has run", response.message)

    def test_terminal_execution_rejects_a_second_cancel(self) -> None:
        started = self.service.process_start(start_request())
        assert started.research_plan_execution is not None
        plan_id = started.research_plan_execution.plan_id
        cancel = plan_request(RESEARCH_PLAN_EXECUTION_CANCEL_INTENT, plan_id)
        self.service.process_cancel(cancel)

        response = self.service.process_cancel(cancel)

        self.assertFalse(response.success)
        self.assertIn("terminal status", response.message)

    def test_invalid_plan_draft_is_rejected_without_execution_state(self) -> None:
        response = self.service.process_start(start_request(plan_steps=()))

        self.assertFalse(response.success)
        self.assertIn("Research plan execution rejected", response.message)
        self.assertEqual(self.service._executions, {})

    def test_missing_plan_id_is_rejected(self) -> None:
        for intent in (
            RESEARCH_PLAN_EXECUTION_STATUS_INTENT,
            RESEARCH_PLAN_EXECUTION_CANCEL_INTENT,
        ):
            with self.subTest(intent=intent):
                with self.assertRaises(ResearchError):
                    self.service.process_status(
                        BrainRequest(message="", metadata={"intent": intent})
                    )

    def test_execution_capacity_is_bounded(self) -> None:
        service = ResearchPlanExecutionApplicationService(
            ResponseComposer(),
            ResearchPlanDraftService(
                clock=lambda: datetime(2026, 8, 23, tzinfo=UTC),
                id_factory=lambda: f"plan-{next(self.identifiers)}",
            ),
            max_active_executions=2,
        )

        self.assertTrue(service.process_start(start_request()).success)
        self.assertTrue(service.process_start(start_request()).success)
        overflow = service.process_start(start_request())

        self.assertFalse(overflow.success)
        self.assertIn("capacity is full", overflow.message)
        self.assertEqual(len(service._executions), 2)

    def test_rejects_invalid_capacity(self) -> None:
        for invalid in (0, -1, True):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    ResearchPlanExecutionApplicationService(
                        ResponseComposer(),
                        max_active_executions=invalid,
                    )

    def test_fresh_service_holds_no_state_from_a_previous_process(self) -> None:
        started = self.service.process_start(start_request())
        assert started.research_plan_execution is not None
        plan_id = started.research_plan_execution.plan_id

        restarted = ResearchPlanExecutionApplicationService(ResponseComposer())
        response = restarted.process_status(
            plan_request(RESEARCH_PLAN_EXECUTION_STATUS_INTENT, plan_id)
        )

        self.assertFalse(response.success)
        self.assertIn("It is not resumed after a restart.", response.message)


class RecordingStepOperation:
    """Record every step handed to a connected research operation."""

    def __init__(self, performed: bool = True, detail: str = "operation ran") -> None:
        self.performed = performed
        self.detail = detail
        self.steps: list[str] = []

    @property
    def operation_name(self) -> str:
        return "recording"

    def run(self, step) -> ResearchPlanStepOperationResult:  # type: ignore[no-untyped-def]
        self.steps.append(step.step_id)
        return ResearchPlanStepOperationResult(
            performed=self.performed,
            detail=self.detail,
        )


class FailingStepOperation(RecordingStepOperation):
    def run(self, step) -> ResearchPlanStepOperationResult:  # type: ignore[no-untyped-def]
        self.steps.append(step.step_id)
        raise ResearchError("Research operation failed.")


class ResearchPlanExecutionAdvanceTests(unittest.TestCase):
    def _service(self, operation=None):  # type: ignore[no-untyped-def]
        return ResearchPlanExecutionApplicationService(
            ResponseComposer(),
            ResearchPlanDraftService(
                clock=lambda: datetime(2026, 8, 23, tzinfo=UTC),
                id_factory=lambda: "plan-advance",
            ),
            step_operation=operation,
        )

    def _started(self, service):  # type: ignore[no-untyped-def]
        response = service.process_start(start_request())
        assert response.research_plan_execution is not None
        return response.research_plan_execution.plan_id

    def test_advance_without_a_connected_operation_blocks_the_step(self) -> None:
        service = self._service(None)
        plan_id = self._started(service)

        response = service.process_advance(
            plan_request(RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT, plan_id)
        )

        state = response.research_plan_execution
        assert state is not None
        self.assertIs(state.status, ResearchPlanExecutionStatus.BLOCKED)
        self.assertIs(state.steps[0].status, ResearchPlanStepStatus.BLOCKED)
        self.assertEqual(state.completed_steps, 0)
        self.assertFalse(state.performed_research_work)
        self.assertIn("No research operation is connected", response.message)
        self.assertIn("Research operations performed: 0", response.message)

    def test_advance_runs_the_connected_operation_once_for_one_step(self) -> None:
        operation = RecordingStepOperation()
        service = self._service(operation)
        plan_id = self._started(service)

        response = service.process_advance(
            plan_request(RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT, plan_id)
        )

        state = response.research_plan_execution
        assert state is not None
        self.assertEqual(operation.steps, ["step-1"])
        self.assertIs(state.steps[0].status, ResearchPlanStepStatus.COMPLETED)
        self.assertTrue(state.steps[0].work_performed)
        self.assertEqual(state.steps[0].detail, "operation ran")
        self.assertIs(state.steps[1].status, ResearchPlanStepStatus.PENDING)
        self.assertEqual(state.steps_with_research_work, 1)
        self.assertIn("Research operations performed: 1", response.message)
        self.assertNotIn("No research work has run", response.message)

    def test_operation_reporting_nothing_performed_blocks_the_step(self) -> None:
        operation = RecordingStepOperation(performed=False, detail="nothing to do")
        service = self._service(operation)
        plan_id = self._started(service)

        response = service.process_advance(
            plan_request(RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT, plan_id)
        )

        state = response.research_plan_execution
        assert state is not None
        self.assertIs(state.status, ResearchPlanExecutionStatus.BLOCKED)
        self.assertEqual(state.completed_steps, 0)
        self.assertFalse(state.performed_research_work)

    def test_failing_operation_fails_the_step_and_the_plan(self) -> None:
        service = self._service(FailingStepOperation())
        plan_id = self._started(service)

        response = service.process_advance(
            plan_request(RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT, plan_id)
        )

        state = response.research_plan_execution
        assert state is not None
        self.assertIs(state.status, ResearchPlanExecutionStatus.FAILED)
        self.assertIs(state.steps[0].status, ResearchPlanStepStatus.FAILED)
        self.assertFalse(state.steps[0].work_performed)
        self.assertEqual(state.steps_with_research_work, 0)

    def test_advancing_every_step_completes_the_plan(self) -> None:
        operation = RecordingStepOperation()
        service = self._service(operation)
        plan_id = self._started(service)
        advance = plan_request(RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT, plan_id)

        service.process_advance(advance)
        response = service.process_advance(advance)

        state = response.research_plan_execution
        assert state is not None
        self.assertIs(state.status, ResearchPlanExecutionStatus.COMPLETED)
        self.assertEqual(state.completed_steps, 2)
        self.assertEqual(state.steps_with_research_work, 2)
        self.assertEqual(operation.steps, ["step-1", "step-2"])

    def test_advance_beyond_the_last_step_is_rejected(self) -> None:
        service = self._service(RecordingStepOperation())
        plan_id = self._started(service)
        advance = plan_request(RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT, plan_id)
        service.process_advance(advance)
        service.process_advance(advance)

        response = service.process_advance(advance)

        self.assertFalse(response.success)
        self.assertIn("no pending step to advance", response.message)

    def test_advance_on_unknown_plan_reports_lost_state(self) -> None:
        service = self._service(RecordingStepOperation())

        response = service.process_advance(
            plan_request(RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT, "plan-missing")
        )

        self.assertFalse(response.success)
        self.assertIn("It is not resumed after a restart.", response.message)


if __name__ == "__main__":
    unittest.main()
