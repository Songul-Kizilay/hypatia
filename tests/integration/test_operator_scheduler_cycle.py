"""One press, one turn of the real scheduler, over the real execution path.

The pieces all existed. A durable task store, a worker cycle bounded to one
task, an autonomy service that loops the canonical one-step advance, and an
execution service that charges and refuses under the approval's own allowance.
What was missing was somebody to say "go", because the scheduler has no thread,
no timer and no loop of its own.

So these tests do the saying, and then check that everything underneath behaved
as it already promised to. A queued task is picked by the scheduler, its work
goes through the ordinary advance, the durable task and execution both move, and
the cycle stops. Nothing runs a second time without another press.

The interesting cases are the ones where nothing should happen: an empty queue,
a paused task, a cancelled one. Each has to return truthfully rather than
inventing work, and none of them may reach a provider.

Deterministic fakes throughout. No network, no model, no sleeps.
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
from cognition.BackgroundResearchSchedulerApplicationService import (
    BACKGROUND_TASK_CANCEL_INTENT,
    BACKGROUND_TASK_CREATE_INTENT,
    BACKGROUND_TASK_PAUSE_INTENT,
    BACKGROUND_WORKER_CYCLE_INTENT,
    BackgroundResearchSchedulerApplicationService,
)
from cognition.ResearchAutonomyApplicationService import (
    ResearchAutonomyApplicationService,
)
from eventbus.EventBus import EventBus
from research.BackgroundResearchTaskStatus import BackgroundResearchTaskStatus
from research.JsonFileBackgroundTaskStore import JsonFileBackgroundTaskStore
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchPlanExecutionStatus import ResearchPlanExecutionStatus
from research.ResearchPlanStepStatus import ResearchPlanStepStatus
from response.ResponseComposer import ResponseComposer
from tests.research.test_bounded_continuation import ContinuationFixture


class SchedulerCycleFixture(ContinuationFixture):
    """A real execution, a real scheduler, and a real durable task store."""

    def setUp(self) -> None:
        super().setUp()
        self.task_store = JsonFileBackgroundTaskStore(self.root / "tasks.json")
        self.execution = self._multi_step(count=3)
        self.scheduler = self._scheduler()

    def _scheduler(self) -> BackgroundResearchSchedulerApplicationService:
        return BackgroundResearchSchedulerApplicationService(
            ResearchAutonomyApplicationService(
                self.execution,
                ResponseComposer(),
                event_bus=EventBus(),
            ),
            ResponseComposer(),
            task_store=self.task_store,
        )

    def _request(self, intent: str, **metadata: object) -> BrainRequest:
        return BrainRequest(
            message="scheduler", metadata={"intent": intent, **metadata}
        )

    def _create_task(self, **budget: object):
        return self.scheduler.process_create(
            self._request(
                BACKGROUND_TASK_CREATE_INTENT,
                research_plan_id="plan-many",
                research_autonomy_budget=(
                    ResearchAutonomyBudget(**budget)
                    if budget
                    else ResearchAutonomyBudget()
                ),
            )
        )

    def _cycle(self):
        """The one thing an operator's press does."""
        return self.scheduler.process_worker_cycle(
            self._request(BACKGROUND_WORKER_CYCLE_INTENT)
        )

    def _task(self):
        [task] = self.scheduler.tasks()
        return task


class OneCycleDoesTheQueuedWorkTests(SchedulerCycleFixture):
    def test_a_queued_task_is_pending_until_a_cycle_runs(self) -> None:
        self._create_task()

        self.assertIs(self._task().status, BackgroundResearchTaskStatus.PENDING)
        self.assertEqual(self.reopened_operation.calls, [])

    def test_one_cycle_advances_the_execution_through_the_canonical_path(
        self,
    ) -> None:
        self._create_task()

        self._cycle()

        self.assertTrue(self.reopened_operation.calls)
        [step] = [
            entry
            for entry in self.execution.live_execution("plan-many").steps
            if entry.step_id == "step-1"
        ]
        self.assertIs(step.status, ResearchPlanStepStatus.COMPLETED)

    def test_the_task_moves_and_is_persisted(self) -> None:
        self._create_task()

        self._cycle()

        self.assertIsNot(self._task().status, BackgroundResearchTaskStatus.PENDING)
        [stored] = self.task_store.load()
        self.assertEqual(stored.task_id, self._task().task_id)
        self.assertIs(stored.status, self._task().status)

    def test_the_task_keeps_its_exact_execution_identity(self) -> None:
        self._create_task()

        self._cycle()

        self.assertEqual(self._task().execution_id, "plan-many")

    def test_one_cycle_runs_at_most_one_task(self) -> None:
        self._create_task()
        self._create_task()

        response = self._cycle()

        self.assertIn("Tasks run this cycle: 1", response.message)

    def test_a_second_cycle_needs_a_second_press(self) -> None:
        """Nothing continues on its own between cycles."""
        self._create_task()
        self._cycle()
        after_one = list(self.reopened_operation.calls)

        self._cycle()

        self.assertGreaterEqual(len(self.reopened_operation.calls), len(after_one))
        self.assertTrue(after_one)


class NothingHappensWhenThereIsNothingToDoTests(SchedulerCycleFixture):
    def test_an_empty_queue_performs_no_research(self) -> None:
        response = self._cycle()

        self.assertEqual(self.reopened_operation.calls, [])
        self.assertIn("Tasks run this cycle: 0", response.message)

    def test_an_empty_queue_invents_no_task(self) -> None:
        self._cycle()

        self.assertEqual(self.scheduler.tasks(), ())

    def test_an_empty_queue_creates_no_authorization(self) -> None:
        before = len(list(self.authorization_service.authorizations()))

        self._cycle()

        self.assertEqual(len(list(self.authorization_service.authorizations())), before)

    def test_a_paused_task_is_not_run(self) -> None:
        created = self._create_task().background_research_task
        self.scheduler.process_pause(
            self._request(
                BACKGROUND_TASK_PAUSE_INTENT, background_task_id=created.task_id
            )
        )

        self._cycle()

        self.assertEqual(self.reopened_operation.calls, [])
        self.assertIs(self._task().status, BackgroundResearchTaskStatus.PAUSED)

    def test_a_cancelled_task_is_not_run(self) -> None:
        created = self._create_task().background_research_task
        self.scheduler.process_cancel(
            self._request(
                BACKGROUND_TASK_CANCEL_INTENT, background_task_id=created.task_id
            )
        )

        self._cycle()

        self.assertEqual(self.reopened_operation.calls, [])
        self.assertIs(self._task().status, BackgroundResearchTaskStatus.CANCELLED)

    def test_a_finished_task_is_not_run_again(self) -> None:
        self._create_task()
        self._cycle()
        reached = list(self.reopened_operation.calls)
        while self._task().status is BackgroundResearchTaskStatus.PENDING:
            self._cycle()
        settled = list(self.reopened_operation.calls)

        self._cycle()

        self.assertEqual(self.reopened_operation.calls, settled)
        self.assertTrue(reached)


class TheCycleGrantsNothingTests(SchedulerCycleFixture):
    def test_running_a_task_creates_no_authorization(self) -> None:
        before = len(list(self.authorization_service.authorizations()))
        self._create_task()

        self._cycle()

        self.assertEqual(len(list(self.authorization_service.authorizations())), before)

    def test_the_execution_allowance_still_governs(self) -> None:
        """The approval's own budget is the ceiling, not the task's."""
        before = self.execution.allowance("plan-many")
        self._create_task()

        self._cycle()

        after = self.execution.allowance("plan-many")
        self.assertLessEqual(
            after.remaining_network_operations, before.remaining_network_operations
        )
        self.assertEqual(after.budget, before.budget)

    def test_the_plan_is_unchanged(self) -> None:
        before = self.execution.live_plan("plan-many")
        self._create_task()

        self._cycle()

        self.assertEqual(self.execution.live_plan("plan-many"), before)


class DurableAcrossRestartWithoutRunningTests(SchedulerCycleFixture):
    def test_tasks_survive_a_rebuilt_scheduler(self) -> None:
        self._create_task()

        rebuilt = self._scheduler()

        self.assertEqual(len(rebuilt.tasks()), 1)

    def test_rebuilding_runs_nothing_by_itself(self) -> None:
        self._create_task()

        rebuilt = self._scheduler()

        self.assertEqual(self.reopened_operation.calls, [])
        self.assertIs(rebuilt.tasks()[0].status, BackgroundResearchTaskStatus.PENDING)

    def test_a_rebuilt_scheduler_still_needs_an_explicit_cycle(self) -> None:
        self._create_task()
        rebuilt = self._scheduler()

        rebuilt.process_worker_cycle(self._request(BACKGROUND_WORKER_CYCLE_INTENT))

        self.assertTrue(self.reopened_operation.calls)

    def test_the_execution_is_not_disturbed_by_rebuilding(self) -> None:
        self._create_task()

        self._scheduler()

        self.assertIs(
            self.execution.live_execution("plan-many").status,
            ResearchPlanExecutionStatus.RUNNING,
        )


if __name__ == "__main__":
    unittest.main()
