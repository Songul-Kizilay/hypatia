"""One-shot deferred scheduling, persistence and trust-boundary proofs."""

from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cognition.TrustedDeferredExecutionControlService import (
    TrustedDeferredExecutionControlService,
)
from cognition.TrustedOneShotDeferredExecutionScheduler import (
    MAX_ONE_SHOT_DEFERRED_DELAY,
    TrustedOneShotDeferredExecutionScheduler,
)
from core.Bootstrap import Bootstrap
from core.CancellationSignal import CancellationSignal
from core.Exceptions import ResearchError
from desktop.DesktopController import DesktopController
from desktop.TkinterDesktopWindow import TkinterDesktopWindow
from research.DeferredExecutionGrantStore import DeferredExecutionGrantReader
from research.DeferredGrantAuthorizer import DeferredGrantAuthorizer
from research.JsonFileOneShotDeferredExecutionScheduleStore import (
    JsonFileOneShotDeferredExecutionScheduleStore,
)
from research.OneShotDeferredExecutionSchedule import OneShotDeferredExecutionSchedule
from research.OneShotDeferredExecutionScheduleStatus import (
    OneShotDeferredExecutionScheduleStatus,
)
from tests.research.test_deferred_execution_grants import (
    Context,
    MemoryGrantStore,
    grant_for,
)

NOW = datetime(2026, 9, 2, 10, 0, tzinfo=UTC)
RUN_AT = NOW + timedelta(hours=1)


class MemoryScheduleStore:
    def __init__(self) -> None:
        self.records: list[OneShotDeferredExecutionSchedule] = []
        self.saves = 0

    def load(self) -> list[OneShotDeferredExecutionSchedule]:
        return list(self.records)

    def save(self, schedules: list[OneShotDeferredExecutionSchedule]) -> None:
        self.records = list(schedules)
        self.saves += 1


class MutableClock:
    def __init__(self, now: datetime = NOW) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


class ExactRunner:
    def __init__(self, context: Context) -> None:
        self.context = context
        self.calls: list[str] = []
        self.tokens: list[object] = []
        self.result = context.task

    def run_exact_deferred_background_task(  # type: ignore[no-untyped-def]
        self, task_id: str, cancellation_token=None
    ):
        self.calls.append(task_id)
        self.tokens.append(cancellation_token)
        return self.result


class RefusingBrain:
    def process(self, request):  # type: ignore[no-untyped-def]
        raise AssertionError("One-shot trusted control must not reach Brain.")


class OneShotFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.context = Context()
        self.grants = MemoryGrantStore()
        self.grants.records = [grant_for(self.context)]
        self.schedules = MemoryScheduleStore()
        self.clock = MutableClock()
        self.runner = ExactRunner(self.context)
        self.deferred_control = TrustedDeferredExecutionControlService(
            self.context,
            self.grants,
            clock=self.clock,
            id_factory=lambda: "unused-grant",
        )
        self.service = TrustedOneShotDeferredExecutionScheduler(
            self.deferred_control,
            DeferredExecutionGrantReader(self.grants),
            self.schedules,
            self.runner,
            clock=self.clock,
            id_factory=lambda: "schedule-1",
        )

    def schedule(self) -> OneShotDeferredExecutionSchedule:
        view = self.service.schedule("task-1", RUN_AT)
        assert view.schedule is not None
        return view.schedule


class TrustedOneShotControlTests(OneShotFixture):
    def test_preview_binds_exact_task_grant_and_utc_time(self) -> None:
        view = self.service.preview("task-1", RUN_AT)
        self.assertEqual((view.task_id, view.grant_id), ("task-1", "grant-1"))
        self.assertEqual(view.run_at, RUN_AT)
        self.assertIn("adds no authority or budget", view.confirmation_text())
        self.assertIn("never repeats", view.confirmation_text())

    def test_scheduling_persists_zero_work(self) -> None:
        before = (self.context.allowance, self.context.execution)
        schedule = self.schedule()
        self.assertIs(schedule.status, OneShotDeferredExecutionScheduleStatus.PENDING)
        self.assertEqual(self.runner.calls, [])
        self.assertEqual((self.context.allowance, self.context.execution), before)

    def test_no_or_stale_grant_cannot_schedule(self) -> None:
        self.grants.records = []
        with self.assertRaises(ResearchError):
            self.service.schedule("task-1", RUN_AT)
        self.grants.records = [grant_for(self.context, plan_digest="0" * 64)]
        with self.assertRaises(ResearchError):
            self.service.schedule("task-1", RUN_AT)

    def test_time_must_be_future_aware_and_within_seven_days(self) -> None:
        invalid = (
            NOW.replace(tzinfo=None) + timedelta(hours=1),
            NOW,
            NOW + MAX_ONE_SHOT_DEFERRED_DELAY + timedelta(seconds=1),
        )
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ResearchError):
                self.service.preview("task-1", value)

    def test_only_one_pending_schedule_per_task(self) -> None:
        self.schedule()
        with self.assertRaises(ResearchError):
            self.service.schedule("task-1", RUN_AT + timedelta(hours=1))

    def test_cancel_changes_only_schedule_state(self) -> None:
        self.schedule()
        before = (self.context.task, self.context.execution, list(self.grants.records))
        cancelled = self.service.cancel("task-1")
        self.assertIs(
            cancelled.status, OneShotDeferredExecutionScheduleStatus.CANCELLED
        )
        self.assertEqual((self.context.task, self.context.execution), before[:2])
        self.assertEqual(self.grants.records, before[2])
        self.assertEqual(self.runner.calls, [])

    def test_controller_uses_direct_port_not_brain(self) -> None:
        controller = DesktopController(RefusingBrain(), None, self.service)
        controller.schedule_one_shot_deferred_execution("task-1", RUN_AT)
        self.assertEqual(len(self.schedules.records), 1)
        self.assertEqual(self.runner.calls, [])


class OneShotFireTests(OneShotFixture):
    def test_fire_before_deadline_is_refused_without_claim(self) -> None:
        schedule = self.schedule()
        with self.assertRaises(ResearchError):
            self.service.fire(schedule.schedule_id)
        self.assertTrue(self.schedules.records[0].pending)
        self.assertEqual(self.runner.calls, [])

    def test_due_fire_claims_then_runs_exact_task_once(self) -> None:
        schedule = self.schedule()
        self.clock.now = RUN_AT
        finished = self.service.fire(schedule.schedule_id)
        self.assertIs(finished.status, OneShotDeferredExecutionScheduleStatus.TRIGGERED)
        self.assertEqual(self.runner.calls, ["task-1"])
        with self.assertRaises(ResearchError):
            self.service.fire(schedule.schedule_id)
        self.assertEqual(self.runner.calls, ["task-1"])

    def test_fire_forwards_cooperative_cancellation(self) -> None:
        schedule = self.schedule()
        signal = CancellationSignal()
        self.clock.now = RUN_AT
        self.service.fire(schedule.schedule_id, signal)
        self.assertEqual(self.runner.tokens, [signal])

    def test_revoked_grant_is_skipped_at_fire_time(self) -> None:
        schedule = self.schedule()
        self.grants.records = []
        self.clock.now = RUN_AT
        finished = self.service.fire(schedule.schedule_id)
        self.assertEqual(finished.outcome, "trusted_grant_unavailable_at_fire_time")
        self.assertEqual(self.runner.calls, [])

    def test_live_refusal_is_consumed_without_fallback(self) -> None:
        schedule = self.schedule()
        self.runner.result = None
        self.clock.now = RUN_AT
        finished = self.service.fire(schedule.schedule_id)
        self.assertEqual(finished.outcome, "not_eligible_at_fire_time")
        self.assertEqual(self.runner.calls, ["task-1"])
        self.assertIsNone(self.service.next_pending())

    def test_busy_desktop_skips_once_and_never_runs(self) -> None:
        schedule = self.schedule()
        self.clock.now = RUN_AT
        skipped = self.service.skip_due_to_busy(schedule.schedule_id)
        self.assertEqual(skipped.outcome, "desktop_worker_busy_at_fire_time")
        self.assertEqual(self.runner.calls, [])
        self.assertIsNone(self.service.next_pending())


class PersistenceTests(unittest.TestCase):
    def schedule(self) -> OneShotDeferredExecutionSchedule:
        return OneShotDeferredExecutionSchedule(
            schedule_id="schedule-1",
            task_id="task-1",
            grant_id="grant-1",
            run_at=RUN_AT,
            created_at=NOW,
            created_by=DeferredGrantAuthorizer.TRUSTED_LOCAL_OPERATOR,
        )

    def test_round_trip_preserves_pending_exact_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "one-shot.json"
            JsonFileOneShotDeferredExecutionScheduleStore(path).save([self.schedule()])
            restored = JsonFileOneShotDeferredExecutionScheduleStore(path).load()
        self.assertEqual(restored, [self.schedule()])

    def test_claimed_record_is_not_replayed_after_restart(self) -> None:
        claimed = self.schedule().claimed(RUN_AT)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "one-shot.json"
            JsonFileOneShotDeferredExecutionScheduleStore(path).save([claimed])
            restored = JsonFileOneShotDeferredExecutionScheduleStore(path).load()
        self.assertFalse(restored[0].pending)

    def test_non_utc_storage_is_rejected(self) -> None:
        local_offset = timezone(timedelta(hours=3))
        with self.assertRaises(ResearchError):
            OneShotDeferredExecutionSchedule(
                schedule_id="schedule-local",
                task_id="task-1",
                grant_id="grant-1",
                run_at=RUN_AT.astimezone(local_offset),
                created_at=NOW,
                created_by=DeferredGrantAuthorizer.TRUSTED_LOCAL_OPERATOR,
            )

    def test_malformed_duplicate_and_multiple_pending_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "one-shot.json"
            path.write_text("{ bad json", encoding="utf-8")
            with self.assertRaises(ResearchError):
                JsonFileOneShotDeferredExecutionScheduleStore(path).load()
            store = JsonFileOneShotDeferredExecutionScheduleStore(path)
            schedule = self.schedule()
            with self.assertRaises(ResearchError):
                store.save([schedule, schedule])
            second = OneShotDeferredExecutionSchedule(
                schedule_id="schedule-2",
                task_id="task-1",
                grant_id="grant-1",
                run_at=RUN_AT + timedelta(hours=1),
                created_at=NOW,
                created_by=DeferredGrantAuthorizer.TRUSTED_LOCAL_OPERATOR,
            )
            with self.assertRaises(ResearchError):
                store.save([schedule, second])


class BootstrapCompositionTests(unittest.TestCase):
    def test_opt_in_composes_control_but_runs_nothing_at_startup(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                "os.environ",
                {"HYPATIA_BACKGROUND_RESEARCH_ENABLED": "true"},
                clear=True,
            ),
        ):
            root = Path(directory)
            bootstrap = Bootstrap(
                memory_path=root / "memory.json",
                session_path=root / "sessions.json",
                research_run_path=root / "runs.json",
            )
            try:
                bootstrap.initialize()
                service = bootstrap.container.resolve(
                    TrustedOneShotDeferredExecutionScheduler
                )
                self.assertIsNone(service.next_pending())
            finally:
                bootstrap.shutdown()


class Value:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value


class Root:
    def __init__(self) -> None:
        self.after_calls: list[tuple[int, object]] = []

    def after(self, delay_ms: int, callback):  # type: ignore[no-untyped-def]
        self.after_calls.append((delay_ms, callback))
        return "after-1"

    def after_cancel(self, after_id: str) -> None:
        pass


class WindowWakeupTests(unittest.TestCase):
    def test_window_arms_only_next_one_shot_wakeup(self) -> None:
        now = datetime.now(UTC)
        schedule = OneShotDeferredExecutionSchedule(
            schedule_id="schedule-1",
            task_id="task-1",
            grant_id="grant-1",
            run_at=now + timedelta(minutes=5),
            created_at=now,
            created_by=DeferredGrantAuthorizer.TRUSTED_LOCAL_OPERATOR,
        )
        root = Root()
        window = object.__new__(TkinterDesktopWindow)
        window._controller = SimpleNamespace(
            one_shot_deferred_execution_available=True,
            next_one_shot_deferred_execution=lambda: schedule,
        )
        window._root = root
        window._closing = False
        window._one_shot_after_id = None
        window._one_shot_deferred_status = Value()
        window._arm_one_shot_deferred_execution()
        self.assertEqual(len(root.after_calls), 1)
        self.assertGreater(root.after_calls[0][0], 0)

    def test_declining_confirmation_persists_nothing(self) -> None:
        calls: list[str] = []
        window = object.__new__(TkinterDesktopWindow)
        window._controller = SimpleNamespace(
            preview_one_shot_deferred_execution=lambda task_id, run_at: SimpleNamespace(
                confirmation_text=lambda: "exact preview"
            ),
            schedule_one_shot_deferred_execution=lambda task_id, run_at: calls.append(
                task_id
            ),
        )
        window._root = object()
        window._scheduler_task_id = Value("task-1")
        window._one_shot_run_at = Value("2026-09-02 14:00")
        window._one_shot_deferred_status = Value()
        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=False
        ):
            window._schedule_one_shot_deferred_execution()
        self.assertEqual(calls, [])


class StructuralBoundaryTests(unittest.TestCase):
    def test_no_brain_intent_loop_or_worker_exists_in_schedule_service(self) -> None:
        source = Path(
            "src/cognition/TrustedOneShotDeferredExecutionScheduler.py"
        ).read_text(encoding="utf-8")
        for forbidden in (
            "BrainRequest(",
            "metadata.get(",
            "Timer(",
            "Thread(",
            "sleep(",
            "while ",
            "schedule_every",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_schedule_service_cannot_mint_or_revoke_grants(self) -> None:
        source = Path(
            "src/cognition/TrustedOneShotDeferredExecutionScheduler.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("DeferredExecutionGrant(", source)
        self.assertNotIn(".grant(", source)
        self.assertNotIn(".revoke(", source)


if __name__ == "__main__":
    unittest.main()
