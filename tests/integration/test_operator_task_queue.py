"""The operator's five controls, driven into the real scheduler.

The unit tests either check what the desktop sends or check what the service
does. Nothing yet proved the two halves meet: that the metadata keys the
controller emits are the keys the scheduler reads, that the intents it names are
the intents that route, and that a task created from the desktop is the same
durable record a later cycle picks up.

So here the brain is replaced by the real scheduler's own routing, and every
step goes through the controller a button would call. Queue an execution, see it
listed, pause it and watch a cycle do nothing, resume it and watch a cycle do
the work, cancel and watch the queue close.

The last part is the one worth being careful about: cancelling a task must stop
the scheduler choosing it and must leave the execution alone. Two identities,
two different meanings of "cancel", and the test pins that they stay apart.

Real execution service, real task store, deterministic fakes underneath. No
network, no model, no sleeps, no timers.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from desktop.DesktopController import DesktopController
from research.BackgroundResearchTaskStatus import BackgroundResearchTaskStatus
from research.ResearchPlanExecutionStatus import ResearchPlanExecutionStatus
from tests.integration.test_operator_scheduler_cycle import SchedulerCycleFixture


class SchedulerRoutingBrain:
    """Routes desktop requests exactly as the engine routes them."""

    def __init__(self, scheduler) -> None:
        self._scheduler = scheduler

    def process(self, request: BrainRequest) -> BrainResponse:
        scheduler = self._scheduler
        for predicate, handler in (
            (scheduler.is_create_request, scheduler.process_create),
            (scheduler.is_pause_request, scheduler.process_pause),
            (scheduler.is_resume_request, scheduler.process_resume),
            (scheduler.is_cancel_request, scheduler.process_cancel),
            (scheduler.is_list_request, scheduler.process_list),
            (scheduler.is_worker_cycle_request, scheduler.process_worker_cycle),
        ):
            if predicate(request):
                return handler(request)
        raise AssertionError(f"No scheduler route for {request.metadata}")


class OperatorQueueFixture(SchedulerCycleFixture):
    def setUp(self) -> None:
        super().setUp()
        self.controller = DesktopController(SchedulerRoutingBrain(self.scheduler))

    def _queue(self) -> str:
        response = self.controller.create_background_task("plan-many")
        return response.background_research_task.task_id

    def _cycle_through_the_desktop(self) -> BrainResponse:
        return self.controller.run_background_scheduler_cycle()


class TheDesktopReachesTheRealSchedulerTests(OperatorQueueFixture):
    def test_creating_from_the_desktop_makes_a_durable_task(self) -> None:
        task_id = self._queue()

        [stored] = self.task_store.load()
        self.assertEqual(stored.task_id, task_id)

    def test_the_created_task_names_the_execution_that_was_typed(self) -> None:
        self._queue()

        self.assertEqual(self._task().execution_id, "plan-many")

    def test_creating_from_the_desktop_runs_no_research(self) -> None:
        self._queue()

        self.assertEqual(self.reopened_operation.calls, [])
        self.assertIs(self._task().status, BackgroundResearchTaskStatus.PENDING)

    def test_listing_shows_the_queued_task_and_its_execution(self) -> None:
        task_id = self._queue()

        listed = self.controller.list_background_tasks()

        self.assertIn(task_id, listed.message)
        self.assertIn("plan-many", listed.message)

    def test_listing_runs_nothing(self) -> None:
        self._queue()

        self.controller.list_background_tasks()

        self.assertEqual(self.reopened_operation.calls, [])
        self.assertIs(self._task().status, BackgroundResearchTaskStatus.PENDING)

    def test_an_empty_queue_lists_without_inventing_a_task(self) -> None:
        self.controller.list_background_tasks()

        self.assertEqual(self.scheduler.tasks(), ())


class PausingHoldsTheTaskBackTests(OperatorQueueFixture):
    def test_pausing_from_the_desktop_pauses_the_durable_task(self) -> None:
        task_id = self._queue()

        self.controller.pause_background_task(task_id)

        self.assertIs(self._task().status, BackgroundResearchTaskStatus.PAUSED)
        [stored] = self.task_store.load()
        self.assertIs(stored.status, BackgroundResearchTaskStatus.PAUSED)

    def test_a_cycle_skips_a_paused_task(self) -> None:
        task_id = self._queue()
        self.controller.pause_background_task(task_id)

        self._cycle_through_the_desktop()

        self.assertEqual(self.reopened_operation.calls, [])

    def test_pausing_does_not_touch_the_execution(self) -> None:
        task_id = self._queue()
        before = self.execution.live_execution("plan-many")

        self.controller.pause_background_task(task_id)

        after = self.execution.live_execution("plan-many")
        self.assertIs(after.status, before.status)
        self.assertIs(after.status, ResearchPlanExecutionStatus.RUNNING)

    def test_resuming_lets_the_next_cycle_do_the_work(self) -> None:
        task_id = self._queue()
        self.controller.pause_background_task(task_id)
        self.controller.resume_background_task(task_id)

        self._cycle_through_the_desktop()

        self.assertTrue(self.reopened_operation.calls)

    def test_resuming_alone_runs_nothing(self) -> None:
        """Selectable again is not the same as running."""
        task_id = self._queue()
        self.controller.pause_background_task(task_id)

        self.controller.resume_background_task(task_id)

        self.assertEqual(self.reopened_operation.calls, [])


class CancellingTheTaskIsNotCancellingTheExecutionTests(OperatorQueueFixture):
    def test_cancelling_closes_the_queue_entry(self) -> None:
        task_id = self._queue()

        self.controller.cancel_background_task(task_id)

        self.assertIs(self._task().status, BackgroundResearchTaskStatus.CANCELLED)

    def test_a_cycle_never_picks_a_cancelled_task(self) -> None:
        task_id = self._queue()
        self.controller.cancel_background_task(task_id)

        self._cycle_through_the_desktop()

        self.assertEqual(self.reopened_operation.calls, [])

    def test_the_execution_keeps_running_after_the_task_is_cancelled(self) -> None:
        """The point of keeping the two identities apart."""
        task_id = self._queue()

        self.controller.cancel_background_task(task_id)

        self.assertIs(
            self.execution.live_execution("plan-many").status,
            ResearchPlanExecutionStatus.RUNNING,
        )

    def test_the_execution_plan_is_untouched(self) -> None:
        before = self.execution.live_plan("plan-many")
        task_id = self._queue()

        self.controller.cancel_background_task(task_id)

        self.assertEqual(self.execution.live_plan("plan-many"), before)

    def test_the_allowance_is_untouched(self) -> None:
        before = self.execution.allowance("plan-many")
        task_id = self._queue()

        self.controller.cancel_background_task(task_id)

        self.assertEqual(self.execution.allowance("plan-many"), before)


class TheServiceRefusesTruthfullyTests(OperatorQueueFixture):
    """The desktop predicts nothing; refusals come from the domain."""

    def test_an_unknown_task_is_refused(self) -> None:
        response = self.controller.pause_background_task("task-nobody-made")

        self.assertIn("Background research task not found:", response.message)
        self.assertIn("task-nobody-made", response.message)

    def test_pausing_an_already_cancelled_task_is_refused(self) -> None:
        task_id = self._queue()
        self.controller.cancel_background_task(task_id)

        response = self.controller.pause_background_task(task_id)

        self.assertIn("Background research task rejected:", response.message)
        self.assertIn("No task state changed.", response.message)
        self.assertIs(self._task().status, BackgroundResearchTaskStatus.CANCELLED)

    def test_resuming_a_task_that_was_never_paused_is_refused(self) -> None:
        task_id = self._queue()

        response = self.controller.resume_background_task(task_id)

        self.assertIn("Background research task rejected:", response.message)

    def test_a_refused_move_runs_no_research(self) -> None:
        task_id = self._queue()
        self.controller.cancel_background_task(task_id)

        self.controller.resume_background_task(task_id)

        self.assertEqual(self.reopened_operation.calls, [])

    def test_the_desktop_never_sends_an_empty_identity(self) -> None:
        for action in (
            self.controller.pause_background_task,
            self.controller.resume_background_task,
            self.controller.cancel_background_task,
        ):
            with self.subTest(name=action.__name__):
                with self.assertRaises(ValueError):
                    action("")

    def test_queueing_an_unknown_execution_is_not_validated_here(self) -> None:
        """A known gap, pinned so it is not mistaken for a guarantee.

        ``process_create`` accepts any execution identifier without checking it
        exists. That is the scheduler's contract today, and the desktop does not
        paper over it with a hidden check of its own — a cycle that later picks
        the task is where the truth comes out.
        """
        response = self.controller.create_background_task("plan-that-never-existed")

        self.assertIsNotNone(response.background_research_task)


class NothingRunsWithoutTheCyclePressTests(OperatorQueueFixture):
    def test_queueing_pausing_and_resuming_never_reach_a_provider(self) -> None:
        task_id = self._queue()
        self.controller.list_background_tasks()
        self.controller.pause_background_task(task_id)
        self.controller.resume_background_task(task_id)

        self.assertEqual(self.reopened_operation.calls, [])

    def test_queueing_a_second_task_does_not_run_the_first(self) -> None:
        """Adding to the queue must not quietly turn it.

        The single-task case cannot see this: a cycle slipped into the create
        path finds an empty queue and does nothing, so it looks innocent. With
        something already waiting, the same slip spends that task's execution
        on a press the operator never made.
        """
        self._queue()

        self._queue()

        self.assertEqual(self.reopened_operation.calls, [])
        self.assertEqual(
            [task.status for task in self.scheduler.tasks()],
            [BackgroundResearchTaskStatus.PENDING] * 2,
        )

    def test_listing_does_not_run_a_waiting_task(self) -> None:
        self._queue()

        self.controller.list_background_tasks()

        self.assertEqual(self.reopened_operation.calls, [])

    def test_only_the_cycle_advances_the_execution(self) -> None:
        self._queue()

        self._cycle_through_the_desktop()

        self.assertTrue(self.reopened_operation.calls)

    def test_the_queue_survives_a_rebuilt_scheduler_without_running(self) -> None:
        self._queue()

        rebuilt = self._scheduler()

        self.assertEqual(len(rebuilt.tasks()), 1)
        self.assertEqual(self.reopened_operation.calls, [])

    def test_queueing_grants_no_authorization(self) -> None:
        before = len(list(self.authorization_service.authorizations()))

        self._queue()

        self.assertEqual(len(list(self.authorization_service.authorizations())), before)


if __name__ == "__main__":
    unittest.main()
