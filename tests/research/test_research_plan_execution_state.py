from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError
from research.ResearchPlan import ResearchPlan
from research.ResearchPlanExecutionState import ResearchPlanExecutionState
from research.ResearchPlanExecutionStatus import ResearchPlanExecutionStatus
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepState import ResearchPlanStepState
from research.ResearchPlanStepStatus import ResearchPlanStepStatus


def build_plan(step_count: int = 2) -> ResearchPlan:
    return ResearchPlan(
        plan_id="plan-1",
        question="What evidence supports the claim?",
        steps=tuple(
            ResearchPlanStep(
                step_id=f"step-{index}",
                instruction=f"Instruction {index}",
            )
            for index in range(1, step_count + 1)
        ),
        created_at=datetime(2026, 8, 23, tzinfo=UTC),
    )


class ResearchPlanExecutionStatusTests(unittest.TestCase):
    def test_terminal_statuses_are_exact(self) -> None:
        terminal = {status for status in ResearchPlanExecutionStatus if status.terminal}
        self.assertEqual(
            terminal,
            {
                ResearchPlanExecutionStatus.COMPLETED,
                ResearchPlanExecutionStatus.FAILED,
                ResearchPlanExecutionStatus.CANCELLED,
            },
        )
        self.assertFalse(ResearchPlanExecutionStatus.READY.terminal)
        self.assertFalse(ResearchPlanExecutionStatus.RUNNING.terminal)
        self.assertFalse(ResearchPlanExecutionStatus.BLOCKED.terminal)

    def test_step_terminal_statuses_are_exact(self) -> None:
        terminal = {status for status in ResearchPlanStepStatus if status.terminal}
        self.assertEqual(
            terminal,
            {
                ResearchPlanStepStatus.COMPLETED,
                ResearchPlanStepStatus.FAILED,
                ResearchPlanStepStatus.CANCELLED,
            },
        )
        self.assertFalse(ResearchPlanStepStatus.PENDING.terminal)
        self.assertFalse(ResearchPlanStepStatus.BLOCKED.terminal)


class ResearchPlanExecutionStateTests(unittest.TestCase):
    def test_prepare_creates_inert_ready_state(self) -> None:
        state = ResearchPlanExecutionState.prepare(build_plan())

        self.assertEqual(state.plan_id, "plan-1")
        self.assertIs(state.status, ResearchPlanExecutionStatus.READY)
        self.assertEqual(len(state.steps), 2)
        self.assertTrue(
            all(step.status is ResearchPlanStepStatus.PENDING for step in state.steps)
        )
        self.assertEqual(state.pending_steps, 2)
        self.assertEqual(state.completed_steps, 0)
        self.assertIsNone(state.running_step_id)
        self.assertEqual(state.next_pending_step_id, "step-1")

    def test_prepare_rejects_a_non_plan(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchPlanExecutionState.prepare("plan")  # type: ignore[arg-type]

    def test_start_requires_the_ready_status(self) -> None:
        running = ResearchPlanExecutionState.prepare(build_plan()).start()

        self.assertIs(running.status, ResearchPlanExecutionStatus.RUNNING)
        with self.assertRaises(ResearchError):
            running.start()

    def test_steps_run_in_authored_order(self) -> None:
        state = ResearchPlanExecutionState.prepare(build_plan()).start()

        with self.assertRaises(ResearchError):
            state.start_step("step-2")

        state = state.start_step("step-1")
        self.assertEqual(state.running_step_id, "step-1")

    def test_only_one_step_runs_at_a_time(self) -> None:
        state = ResearchPlanExecutionState.prepare(build_plan()).start()
        state = state.start_step("step-1")

        with self.assertRaises(ResearchError):
            state.start_step("step-2")

    def test_full_success_completes_the_plan(self) -> None:
        state = ResearchPlanExecutionState.prepare(build_plan()).start()
        state = state.start_step("step-1").complete_step("step-1", "found evidence")
        self.assertIs(state.status, ResearchPlanExecutionStatus.RUNNING)
        self.assertEqual(state.completed_steps, 1)

        state = state.start_step("step-2").complete_step("step-2")

        self.assertIs(state.status, ResearchPlanExecutionStatus.COMPLETED)
        self.assertEqual(state.completed_steps, 2)
        self.assertTrue(state.status.terminal)
        self.assertEqual(state.steps[0].detail, "found evidence")

    def test_completed_status_cannot_be_fabricated_with_unfinished_steps(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchPlanExecutionState(
                plan_id="plan-1",
                status=ResearchPlanExecutionStatus.COMPLETED,
                steps=(
                    ResearchPlanStepState(
                        step_id="step-1",
                        status=ResearchPlanStepStatus.COMPLETED,
                    ),
                    ResearchPlanStepState(step_id="step-2"),
                ),
            )

    def test_failure_preserves_completed_progress(self) -> None:
        state = ResearchPlanExecutionState.prepare(build_plan()).start()
        state = state.start_step("step-1").complete_step("step-1")
        state = state.start_step("step-2").fail_step("step-2", "source unavailable")

        self.assertIs(state.status, ResearchPlanExecutionStatus.FAILED)
        self.assertEqual(state.detail, "source unavailable")
        self.assertIs(state.steps[0].status, ResearchPlanStepStatus.COMPLETED)
        self.assertIs(state.steps[1].status, ResearchPlanStepStatus.FAILED)
        self.assertEqual(state.completed_steps, 1)

    def test_terminal_plan_rejects_further_transitions(self) -> None:
        state = ResearchPlanExecutionState.prepare(build_plan(1)).start()
        state = state.start_step("step-1").complete_step("step-1")

        self.assertIs(state.status, ResearchPlanExecutionStatus.COMPLETED)
        with self.assertRaises(ResearchError):
            state.start_step("step-1")
        with self.assertRaises(ResearchError):
            state.cancel()

    def test_blocking_a_step_blocks_the_plan_for_review(self) -> None:
        state = ResearchPlanExecutionState.prepare(build_plan()).start()
        state = state.block_step("step-2", "needs user source selection")

        self.assertIs(state.status, ResearchPlanExecutionStatus.BLOCKED)
        self.assertIs(state.steps[1].status, ResearchPlanStepStatus.BLOCKED)
        self.assertEqual(state.steps[1].detail, "needs user source selection")
        self.assertFalse(state.status.terminal)

    def test_blocked_plan_can_still_be_cancelled(self) -> None:
        state = ResearchPlanExecutionState.prepare(build_plan()).start()
        state = state.block_step("step-1", "blocked").cancel("user cancelled")

        self.assertIs(state.status, ResearchPlanExecutionStatus.CANCELLED)

    def test_cancel_preserves_finished_steps_and_cancels_the_rest(self) -> None:
        state = ResearchPlanExecutionState.prepare(build_plan(3)).start()
        state = state.start_step("step-1").complete_step("step-1")
        state = state.start_step("step-2")

        state = state.cancel("user cancelled")

        self.assertIs(state.status, ResearchPlanExecutionStatus.CANCELLED)
        self.assertIs(state.steps[0].status, ResearchPlanStepStatus.COMPLETED)
        self.assertIs(state.steps[1].status, ResearchPlanStepStatus.CANCELLED)
        self.assertIs(state.steps[2].status, ResearchPlanStepStatus.CANCELLED)
        self.assertEqual(state.detail, "user cancelled")

    def test_transitions_never_mutate_the_previous_state(self) -> None:
        ready = ResearchPlanExecutionState.prepare(build_plan())
        running = ready.start()
        started = running.start_step("step-1")

        self.assertIs(ready.status, ResearchPlanExecutionStatus.READY)
        self.assertIs(running.status, ResearchPlanExecutionStatus.RUNNING)
        self.assertIsNone(running.running_step_id)
        self.assertEqual(started.running_step_id, "step-1")

    def test_unknown_step_is_rejected(self) -> None:
        state = ResearchPlanExecutionState.prepare(build_plan()).start()

        with self.assertRaises(ResearchError):
            state.complete_step("step-9")

    def test_step_transitions_require_a_running_plan(self) -> None:
        ready = ResearchPlanExecutionState.prepare(build_plan())

        for action in (
            lambda: ready.start_step("step-1"),
            lambda: ready.complete_step("step-1"),
            lambda: ready.fail_step("step-1", "reason"),
            lambda: ready.block_step("step-1", "reason"),
        ):
            with self.assertRaises(ResearchError):
                action()

    def test_completing_a_step_that_is_not_running_is_rejected(self) -> None:
        state = ResearchPlanExecutionState.prepare(build_plan()).start()

        with self.assertRaises(ResearchError):
            state.complete_step("step-1")

    def test_detail_is_bounded(self) -> None:
        state = ResearchPlanExecutionState.prepare(build_plan()).start()
        state = state.start_step("step-1")

        with self.assertRaises(ResearchError):
            state.complete_step("step-1", "x" * 501)

    def test_empty_and_duplicate_step_states_are_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchPlanExecutionState(
                plan_id="plan-1",
                status=ResearchPlanExecutionStatus.READY,
                steps=(),
            )
        with self.assertRaises(ResearchError):
            ResearchPlanExecutionState(
                plan_id="plan-1",
                status=ResearchPlanExecutionStatus.READY,
                steps=(
                    ResearchPlanStepState(step_id="step-1"),
                    ResearchPlanStepState(step_id="step-1"),
                ),
            )

    def test_multiple_running_steps_are_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchPlanExecutionState(
                plan_id="plan-1",
                status=ResearchPlanExecutionStatus.RUNNING,
                steps=(
                    ResearchPlanStepState(
                        step_id="step-1",
                        status=ResearchPlanStepStatus.RUNNING,
                    ),
                    ResearchPlanStepState(
                        step_id="step-2",
                        status=ResearchPlanStepStatus.RUNNING,
                    ),
                ),
            )


if __name__ == "__main__":
    unittest.main()
