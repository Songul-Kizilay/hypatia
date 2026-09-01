"""Two callers, one queue, and no lost rulings.

The desktop could only ever make one scheduler call at a time, so nothing here
was reachable through it. That is exactly why it needed fixing before anything
else learns to call the scheduler — a timer, a second surface, anything without
that discipline — because the service itself had no serialization of its own.

Three races, each driven by barriers rather than timing. Two worker cycles over
one task, where the loser must not run it a second time. Two creates, where the
whole-document write must not drop either. And a cancel that lands while a
worker is out running, where the worker comes back holding a result about a task
that has since moved on — and must not write it.

That last one is the interesting invariant. The run genuinely happened; its
outcome is genuinely stale. Preserving the newer ruling means the outcome is
dropped, reported as superseded, and never merged field by field into a task
somebody deliberately closed.

The lock is never held across autonomy. A test below proves that by having the
fake autonomy call back into the scheduler while it is running: if the lock were
held, that call could not return.

Real scheduler, real task store, gated fakes. No network, no model, no sleeps.
"""

from __future__ import annotations

import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from cognition.BackgroundResearchEvents import (
    TASK_COMPLETED,
    TASK_OUTCOME_SUPERSEDED,
)
from cognition.BackgroundResearchSchedulerApplicationService import (
    BACKGROUND_TASK_CANCEL_INTENT,
    BACKGROUND_TASK_CREATE_INTENT,
    BACKGROUND_TASK_PAUSE_INTENT,
    BACKGROUND_TASK_RESUME_INTENT,
    BACKGROUND_WORKER_CYCLE_INTENT,
    BackgroundResearchSchedulerApplicationService,
)
from eventbus.EventBus import EventBus
from research.BackgroundResearchTaskStatus import BackgroundResearchTaskStatus
from research.JsonFileBackgroundTaskStore import JsonFileBackgroundTaskStore
from research.ResearchAutonomyResult import (
    AutonomyStopReason,
    ResearchAutonomyResult,
)
from research.ResearchPlanExecutionStatus import ResearchPlanExecutionStatus
from response.ResponseComposer import ResponseComposer
from tests.integration.test_operator_scheduler_cycle import SchedulerCycleFixture

SCHEDULER_SOURCE = (
    SRC_DIR / "cognition" / "BackgroundResearchSchedulerApplicationService.py"
).read_text(encoding="utf-8")


class GatedAutonomy:
    """Stands in for autonomy so a run can be held open on purpose."""

    def __init__(self, stop_reason: AutonomyStopReason | None = None) -> None:
        self.entered = Event()
        self.release = Event()
        self.release.set()
        self.calls: list[str] = []
        self._stop_reason = stop_reason or AutonomyStopReason.NO_PENDING_STEP

    def gate(self) -> None:
        """Make the next run block until somebody lets it finish."""
        self.release.clear()

    def process_run(self, request: BrainRequest) -> BrainResponse:
        plan_id = str(request.metadata.get("research_plan_id"))
        self.calls.append(plan_id)
        self.entered.set()
        assert self.release.wait(timeout=10), "autonomy was never released"
        return BrainResponse(
            message="ran",
            request_id=request.request_id,
            intent="research_autonomy",
            memory_count=0,
            research_autonomy=ResearchAutonomyResult(
                plan_id=plan_id,
                stop_reason=self._stop_reason,
                execution_status=ResearchPlanExecutionStatus.RUNNING.value,
            ),
        )


class SerializationFixture(SchedulerCycleFixture):
    """The real scheduler and store, with autonomy replaced by a gate."""

    def setUp(self) -> None:
        super().setUp()
        self.autonomy = GatedAutonomy()
        self.events = EventBus()
        self.seen: list[tuple[str, dict]] = []
        for name in (TASK_COMPLETED, TASK_OUTCOME_SUPERSEDED):
            self.events.subscribe(
                name,
                lambda event, name=name: self.seen.append((name, dict(event.payload))),
            )
        self.scheduler = BackgroundResearchSchedulerApplicationService(
            self.autonomy,  # type: ignore[arg-type]
            ResponseComposer(),
            executions=self.execution,
            task_store=self.task_store,
            event_bus=self.events,
        )

    def _request(self, intent: str, **metadata: object) -> BrainRequest:
        return BrainRequest(
            message="scheduler", metadata={"intent": intent, **metadata}
        )

    def _queue(self) -> str:
        response = self.scheduler.process_create(
            self._request(BACKGROUND_TASK_CREATE_INTENT, research_plan_id="plan-many")
        )
        assert response.background_research_task is not None
        return response.background_research_task.task_id

    def _cycle(self) -> BrainResponse:
        return self.scheduler.process_worker_cycle(
            self._request(BACKGROUND_WORKER_CYCLE_INTENT)
        )

    def _status(self, task_id: str) -> BackgroundResearchTaskStatus:
        [task] = [task for task in self.scheduler.tasks() if task.task_id == task_id]
        return task.status

    def _emitted(self, name: str) -> list[dict]:
        return [payload for emitted, payload in self.seen if emitted == name]


class TwoWorkerCyclesCannotRunOneTaskTwiceTests(SerializationFixture):
    """The race the desktop's single-flight worker was quietly covering."""

    def _run_two_cycles(self) -> list[BrainResponse]:
        start = Barrier(2, timeout=10)

        def cycle() -> BrainResponse:
            start.wait()
            return self._cycle()

        with ThreadPoolExecutor(max_workers=2) as pool:
            return [
                future.result(timeout=10)
                for future in [
                    pool.submit(cycle),
                    pool.submit(cycle),
                ]
            ]

    def test_only_one_autonomy_run_happens(self) -> None:
        self._queue()

        self._run_two_cycles()

        self.assertEqual(len(self.autonomy.calls), 1)

    def test_the_task_is_claimed_exactly_once(self) -> None:
        task_id = self._queue()

        self._run_two_cycles()

        self.assertEqual(len(self.scheduler.tasks()), 1)
        self.assertIsNot(self._status(task_id), BackgroundResearchTaskStatus.PENDING)

    def test_the_losing_cycle_reports_no_work(self) -> None:
        self._queue()

        responses = self._run_two_cycles()

        counts = sorted(
            "Tasks run this cycle: 0" in response.message for response in responses
        )
        self.assertEqual(counts, [False, True])

    def test_two_cycles_over_an_empty_queue_run_nothing(self) -> None:
        self._run_two_cycles()

        self.assertEqual(self.autonomy.calls, [])

    def test_a_second_cycle_during_the_first_finds_nothing_to_do(self) -> None:
        """The same race, without depending on how two threads interleave.

        A barrier only lines the threads up; either could still finish before
        the other looks. Here the first cycle is held open inside autonomy, so
        the second provably runs while the task is claimed — and the only
        correct answer is that there is nothing runnable.
        """
        self._queue()
        self.autonomy.gate()

        with ThreadPoolExecutor(max_workers=1) as pool:
            first = pool.submit(self._cycle)
            self.assertTrue(self.autonomy.entered.wait(timeout=10))

            second = self._cycle()

            self.autonomy.release.set()
            first.result(timeout=10)

        self.assertIn("Tasks run this cycle: 0", second.message)
        self.assertEqual(len(self.autonomy.calls), 1)

    def test_the_held_task_is_not_selectable_by_anybody(self) -> None:
        self._queue()
        self.autonomy.gate()

        with ThreadPoolExecutor(max_workers=1) as pool:
            first = pool.submit(self._cycle)
            self.assertTrue(self.autonomy.entered.wait(timeout=10))

            [held] = self.scheduler.tasks()
            claimed_status = held.status

            self.autonomy.release.set()
            first.result(timeout=10)

        self.assertIs(claimed_status, BackgroundResearchTaskStatus.RUNNING)


class TwoCreatesBothSurviveTests(SerializationFixture):
    """The whole-document store makes a lost create a real possibility."""

    def _create_concurrently(self, count: int) -> list[BrainResponse]:
        start = Barrier(count, timeout=10)

        def create() -> BrainResponse:
            start.wait()
            return self.scheduler.process_create(
                self._request(
                    BACKGROUND_TASK_CREATE_INTENT, research_plan_id="plan-many"
                )
            )

        with ThreadPoolExecutor(max_workers=count) as pool:
            futures = [pool.submit(create) for _ in range(count)]
            return [future.result(timeout=10) for future in futures]

    def test_both_creates_produce_a_task(self) -> None:
        responses = self._create_concurrently(2)

        self.assertTrue(all(r.background_research_task is not None for r in responses))

    def test_the_task_identities_are_distinct(self) -> None:
        responses = self._create_concurrently(2)

        identifiers = {r.background_research_task.task_id for r in responses}
        self.assertEqual(len(identifiers), 2)

    def test_neither_task_is_lost_in_memory(self) -> None:
        self._create_concurrently(2)

        self.assertEqual(len(self.scheduler.tasks()), 2)

    def test_neither_task_is_lost_on_disk(self) -> None:
        """The point of the whole exercise: the durable document holds both."""
        responses = self._create_concurrently(2)

        stored = {task.task_id for task in self.task_store.load()}
        self.assertEqual(
            stored, {r.background_research_task.task_id for r in responses}
        )

    def test_many_concurrent_creates_all_survive_a_reload(self) -> None:
        self._create_concurrently(8)

        rebuilt = BackgroundResearchSchedulerApplicationService(
            self.autonomy,  # type: ignore[arg-type]
            ResponseComposer(),
            executions=self.execution,
            task_store=self.task_store,
        )

        self.assertEqual(len(rebuilt.tasks()), 8)


class ANewerRulingIsNotOverwrittenTests(SerializationFixture):
    """A worker returns to find the task has moved on. It must not write."""

    def _run_with_cancel_midflight(self, task_id: str) -> None:
        self.autonomy.gate()
        with ThreadPoolExecutor(max_workers=1) as pool:
            cycle = pool.submit(self._cycle)
            self.assertTrue(self.autonomy.entered.wait(timeout=10))

            self.scheduler.process_cancel(
                self._request(BACKGROUND_TASK_CANCEL_INTENT, background_task_id=task_id)
            )

            self.autonomy.release.set()
            cycle.result(timeout=10)

    def test_a_cancel_landing_midflight_survives_the_worker(self) -> None:
        task_id = self._queue()

        self._run_with_cancel_midflight(task_id)

        self.assertIs(self._status(task_id), BackgroundResearchTaskStatus.CANCELLED)

    def test_the_cancelled_task_is_not_reopened(self) -> None:
        task_id = self._queue()

        self._run_with_cancel_midflight(task_id)

        self.assertNotIn(
            self._status(task_id),
            (
                BackgroundResearchTaskStatus.PENDING,
                BackgroundResearchTaskStatus.RUNNING,
                BackgroundResearchTaskStatus.COMPLETED,
            ),
        )

    def test_the_durable_store_agrees(self) -> None:
        task_id = self._queue()

        self._run_with_cancel_midflight(task_id)

        [stored] = self.task_store.load()
        self.assertIs(stored.status, BackgroundResearchTaskStatus.CANCELLED)

    def test_no_completed_event_claims_a_transition_that_never_committed(
        self,
    ) -> None:
        task_id = self._queue()

        self._run_with_cancel_midflight(task_id)

        self.assertEqual(self._emitted(TASK_COMPLETED), [])

    def test_the_superseded_outcome_is_reported_truthfully(self) -> None:
        task_id = self._queue()

        self._run_with_cancel_midflight(task_id)

        [payload] = self._emitted(TASK_OUTCOME_SUPERSEDED)
        self.assertEqual(payload["task_id"], task_id)
        self.assertEqual(
            payload["status"], BackgroundResearchTaskStatus.CANCELLED.value
        )

    def test_the_cycle_reports_the_task_as_it_actually_stands(self) -> None:
        task_id = self._queue()
        self.autonomy.gate()

        with ThreadPoolExecutor(max_workers=1) as pool:
            cycle = pool.submit(self._cycle)
            self.assertTrue(self.autonomy.entered.wait(timeout=10))
            self.scheduler.process_cancel(
                self._request(BACKGROUND_TASK_CANCEL_INTENT, background_task_id=task_id)
            )
            self.autonomy.release.set()
            response = cycle.result(timeout=10)

        self.assertIn(BackgroundResearchTaskStatus.CANCELLED.value, response.message)

    def test_a_stale_failure_cannot_overwrite_a_newer_ruling_either(self) -> None:
        """Not only successes: a stale failure is just as stale."""
        self.autonomy._stop_reason = AutonomyStopReason.STEP_FAILED
        task_id = self._queue()

        self._run_with_cancel_midflight(task_id)

        self.assertIs(self._status(task_id), BackgroundResearchTaskStatus.CANCELLED)


class TheLockIsNeverHeldAcrossAutonomyTests(SerializationFixture):
    """Proven by doing scheduler work from inside a running autonomy call."""

    def test_the_queue_is_readable_while_a_task_runs(self) -> None:
        reached: list[int] = []

        def peek(request: BrainRequest) -> BrainResponse:
            reached.append(len(self.scheduler.tasks()))
            return GatedAutonomy.process_run(self.autonomy, request)

        self.autonomy.process_run = peek  # type: ignore[method-assign]
        self._queue()

        self._cycle()

        self.assertEqual(reached, [1])

    def test_another_task_can_be_created_while_one_runs(self) -> None:
        created: list[str] = []

        def create_midflight(request: BrainRequest) -> BrainResponse:
            response = self.scheduler.process_create(
                self._request(
                    BACKGROUND_TASK_CREATE_INTENT, research_plan_id="plan-many"
                )
            )
            assert response.background_research_task is not None
            created.append(response.background_research_task.task_id)
            return GatedAutonomy.process_run(self.autonomy, request)

        self.autonomy.process_run = create_midflight  # type: ignore[method-assign]
        self._queue()

        self._cycle()

        self.assertEqual(len(created), 1)
        self.assertEqual(len(self.scheduler.tasks()), 2)

    def test_selecting_and_claiming_share_one_lock_acquisition(self) -> None:
        """Not two acquisitions with a gap between them.

        The gap is the whole bug, and it cannot be caught by running threads:
        both callers would come away holding their own PENDING snapshot, and
        ``started()`` succeeds on a snapshot regardless of what the queue now
        says. So both would claim, and both would run. There is no seam to gate
        in that gap either, which is exactly why the shape is pinned here.
        """
        start = SCHEDULER_SOURCE.index("    def _claim_next_runnable(")
        claim = SCHEDULER_SOURCE[
            start : SCHEDULER_SOURCE.index("\n    def ", start + 1)
        ]

        self.assertEqual(claim.count("with self._task_lock:"), 1)
        self.assertIn("self._next_runnable()", claim)
        self.assertIn(".started(", claim)

    def test_the_run_happens_outside_the_claim(self) -> None:
        start = SCHEDULER_SOURCE.index("    def _claim_next_runnable(")
        claim = SCHEDULER_SOURCE[
            start : SCHEDULER_SOURCE.index("\n    def ", start + 1)
        ]

        self.assertIn("with self._task_lock:", claim)
        self.assertNotIn("process_run", claim)

    def test_every_writer_takes_the_same_lock(self) -> None:
        for name in (
            "process_create",
            "_transition",
            "_claim_next_runnable",
            "_persist",
            "_restore",
            "tasks",
        ):
            with self.subTest(name=name):
                start = SCHEDULER_SOURCE.index(f"    def {name}(")
                body = SCHEDULER_SOURCE[
                    start : SCHEDULER_SOURCE.index("\n    def ", start + 1)
                ]

                self.assertIn("with self._task_lock:", body)


class UncontendedBehaviourIsUnchangedTests(SerializationFixture):
    """Serialization must be invisible when nobody is competing."""

    def test_create_still_queues_one_pending_task(self) -> None:
        task_id = self._queue()

        self.assertIs(self._status(task_id), BackgroundResearchTaskStatus.PENDING)

    def test_pause_then_resume_still_works(self) -> None:
        task_id = self._queue()

        self.scheduler.process_pause(
            self._request(BACKGROUND_TASK_PAUSE_INTENT, background_task_id=task_id)
        )
        paused = self._status(task_id)
        self.scheduler.process_resume(
            self._request(BACKGROUND_TASK_RESUME_INTENT, background_task_id=task_id)
        )

        self.assertIs(paused, BackgroundResearchTaskStatus.PAUSED)
        self.assertIs(self._status(task_id), BackgroundResearchTaskStatus.PENDING)

    def test_cancel_still_closes_the_task(self) -> None:
        task_id = self._queue()

        self.scheduler.process_cancel(
            self._request(BACKGROUND_TASK_CANCEL_INTENT, background_task_id=task_id)
        )

        self.assertIs(self._status(task_id), BackgroundResearchTaskStatus.CANCELLED)

    def test_illegal_transitions_are_still_refused(self) -> None:
        """A lock is not permission."""
        task_id = self._queue()
        self.scheduler.process_cancel(
            self._request(BACKGROUND_TASK_CANCEL_INTENT, background_task_id=task_id)
        )

        response = self.scheduler.process_pause(
            self._request(BACKGROUND_TASK_PAUSE_INTENT, background_task_id=task_id)
        )

        self.assertIn("rejected", response.message.casefold())
        self.assertIs(self._status(task_id), BackgroundResearchTaskStatus.CANCELLED)

    def test_pausing_a_running_task_is_still_illegal(self) -> None:
        """Unchanged domain rule, deliberately not widened for concurrency."""
        task_id = self._queue()
        self.autonomy.gate()

        with ThreadPoolExecutor(max_workers=1) as pool:
            cycle = pool.submit(self._cycle)
            self.assertTrue(self.autonomy.entered.wait(timeout=10))

            response = self.scheduler.process_pause(
                self._request(BACKGROUND_TASK_PAUSE_INTENT, background_task_id=task_id)
            )

            self.autonomy.release.set()
            cycle.result(timeout=10)

        self.assertIn("rejected", response.message.casefold())

    def test_a_normal_cycle_still_commits_its_outcome(self) -> None:
        task_id = self._queue()

        self._cycle()

        self.assertIs(self._status(task_id), BackgroundResearchTaskStatus.COMPLETED)
        self.assertEqual(len(self._emitted(TASK_OUTCOME_SUPERSEDED)), 0)
        self.assertEqual(len(self._emitted(TASK_COMPLETED)), 1)

    def test_a_finished_task_stays_terminal(self) -> None:
        task_id = self._queue()
        self._cycle()

        self._cycle()

        self.assertIs(self._status(task_id), BackgroundResearchTaskStatus.COMPLETED)
        self.assertEqual(len(self.autonomy.calls), 1)


class NothingElseChangedTests(SerializationFixture):
    def test_the_execution_is_untouched_by_task_synchronization(self) -> None:
        before = self.execution.live_execution("plan-many")
        task_id = self._queue()

        self.scheduler.process_cancel(
            self._request(BACKGROUND_TASK_CANCEL_INTENT, background_task_id=task_id)
        )

        self.assertEqual(self.execution.live_execution("plan-many"), before)

    def test_the_allowance_is_untouched(self) -> None:
        before = self.execution.allowance("plan-many")

        self._queue()

        self.assertEqual(self.execution.allowance("plan-many"), before)

    def test_no_authorization_is_created(self) -> None:
        before = len(list(self.authorization_service.authorizations()))

        self._queue()
        self._cycle()

        self.assertEqual(len(list(self.authorization_service.authorizations())), before)

    def test_retryability_still_comes_only_from_running_out(self) -> None:
        from research.BackgroundTaskOutcome import BackgroundTaskOutcome

        retryable = [outcome for outcome in BackgroundTaskOutcome if outcome.retryable]

        self.assertEqual(retryable, [BackgroundTaskOutcome.RETRYABLE_BUDGET_EXHAUSTED])

    def test_budget_exhaustion_still_requeues_the_task(self) -> None:
        self.autonomy._stop_reason = AutonomyStopReason.STEP_BUDGET_EXHAUSTED
        task_id = self._queue()

        self._cycle()

        self.assertIs(self._status(task_id), BackgroundResearchTaskStatus.PENDING)

    def test_a_failure_is_still_never_retried(self) -> None:
        self.autonomy._stop_reason = AutonomyStopReason.STEP_FAILED
        task_id = self._queue()

        self._cycle()

        self.assertIs(self._status(task_id), BackgroundResearchTaskStatus.FAILED)

    def test_no_process_wide_or_file_lock_was_added(self) -> None:
        for wider in ("flock", "msvcrt", "lock_path", "ExclusiveStoreOwnership"):
            with self.subTest(name=wider):
                self.assertNotIn(wider, SCHEDULER_SOURCE)

    def test_restart_restores_the_exact_tasks(self) -> None:
        task_id = self._queue()

        rebuilt = BackgroundResearchSchedulerApplicationService(
            self.autonomy,  # type: ignore[arg-type]
            ResponseComposer(),
            executions=self.execution,
            task_store=JsonFileBackgroundTaskStore(self.root / "tasks.json"),
        )

        [restored] = rebuilt.tasks()
        self.assertEqual(restored.task_id, task_id)
        self.assertEqual(restored.execution_id, "plan-many")
        self.assertIs(restored.status, BackgroundResearchTaskStatus.PENDING)
        self.assertEqual(self.autonomy.calls, [])


if __name__ == "__main__":
    unittest.main()
