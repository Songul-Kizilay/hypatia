"""Trusted-desktop boundary for one exact, non-recurring future attempt."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from threading import RLock
from uuid import uuid4

from cognition.TrustedDeferredExecutionControlService import (
    TrustedDeferredExecutionControlService,
)
from core.CancellationSignal import CancellationToken
from core.Exceptions import HypatiaError, ResearchError
from research.DeferredExecutionGrantStore import ReadsDeferredExecutionGrants
from research.DeferredGrantAuthorizer import DeferredGrantAuthorizer
from research.OneShotDeferredExecutionSchedule import OneShotDeferredExecutionSchedule
from research.OneShotDeferredExecutionScheduleStatus import (
    OneShotDeferredExecutionScheduleStatus,
)
from research.OneShotDeferredExecutionScheduleStore import (
    OneShotDeferredExecutionScheduleStore,
    RunsExactDeferredTask,
)
from research.OneShotDeferredExecutionScheduleView import (
    OneShotDeferredExecutionScheduleView,
)

MAX_ONE_SHOT_DEFERRED_DELAY = timedelta(days=7)


class TrustedOneShotDeferredExecutionScheduler:
    """Persist and attempt one trusted exact future run, at most once."""

    def __init__(
        self,
        deferred_control: TrustedDeferredExecutionControlService,
        grants: ReadsDeferredExecutionGrants,
        schedules: OneShotDeferredExecutionScheduleStore,
        runner: RunsExactDeferredTask,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._deferred_control = deferred_control
        self._grants = grants
        self._schedules = schedules
        self._runner = runner
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or (lambda: str(uuid4()))
        self._lock = RLock()

    def preview(
        self, task_id: str, run_at: datetime
    ) -> OneShotDeferredExecutionScheduleView:
        normalized_run_at = self._valid_run_at(run_at)
        deferred = self._deferred_control.preview(task_id.strip())
        if deferred.grant is None or not deferred.decision.allowed:
            raise ResearchError(
                "This exact task has no currently valid trusted deferred grant."
            )
        return OneShotDeferredExecutionScheduleView(
            task_id=deferred.task_id,
            grant_id=deferred.grant.grant_id,
            run_at=normalized_run_at,
            # The same grant whose id is shown, so the restrictions named are
            # that grant's own record rather than anything re-derived.
            grant=deferred.grant,
        )

    def schedule(
        self, task_id: str, run_at: datetime
    ) -> OneShotDeferredExecutionScheduleView:
        view = self.preview(task_id, run_at)
        with self._lock:
            schedules = self._schedules.load()
            if any(
                value.task_id == view.task_id and value.pending for value in schedules
            ):
                raise ResearchError("This task already has a pending one-shot run.")
            schedule = OneShotDeferredExecutionSchedule(
                schedule_id=self._id_factory(),
                task_id=view.task_id,
                grant_id=view.grant_id,
                run_at=view.run_at,
                created_at=self._now(),
                created_by=DeferredGrantAuthorizer.TRUSTED_LOCAL_OPERATOR,
            )
            schedules.append(schedule)
            self._schedules.save(schedules)
        return OneShotDeferredExecutionScheduleView(
            task_id=schedule.task_id,
            grant_id=schedule.grant_id,
            run_at=schedule.run_at,
            schedule=schedule,
            grant=view.grant,
        )

    def cancel(self, task_id: str) -> OneShotDeferredExecutionSchedule:
        normalized = task_id.strip()
        if not normalized:
            raise ResearchError("One-shot deferred task ID cannot be empty.")
        with self._lock:
            schedules = self._schedules.load()
            match = self._pending_for_task(schedules, normalized)
            if match is None:
                raise ResearchError("This task has no pending one-shot run.")
            cancelled = match.cancelled(self._now())
            self._save_replacement(schedules, cancelled)
            return cancelled

    def status(self, task_id: str) -> OneShotDeferredExecutionScheduleView | None:
        """Report the latest schedule together with the grant it names.

        Resolved by the schedule's own grant ID, never by whichever grant is
        currently active for the task: those can differ, and the schedule will
        run under the one it recorded. An id that no longer resolves reports as
        unavailable rather than borrowing another grant's answer.
        """
        normalized = task_id.strip()
        if not normalized:
            raise ResearchError("One-shot deferred task ID cannot be empty.")
        with self._lock:
            matches = [
                value for value in self._schedules.load() if value.task_id == normalized
            ]
        if not matches:
            return None
        schedule = max(matches, key=lambda value: (value.created_at, value.schedule_id))
        return OneShotDeferredExecutionScheduleView(
            task_id=schedule.task_id,
            grant_id=schedule.grant_id,
            run_at=schedule.run_at,
            schedule=schedule,
            grant=self._grants.for_grant_id(schedule.grant_id),
        )

    def next_pending(self) -> OneShotDeferredExecutionSchedule | None:
        with self._lock:
            pending = [value for value in self._schedules.load() if value.pending]
        return (
            min(pending, key=lambda value: (value.run_at, value.schedule_id))
            if pending
            else None
        )

    def fire(
        self,
        schedule_id: str,
        cancellation_token: CancellationToken | None = None,
    ) -> OneShotDeferredExecutionSchedule:
        """Claim durably before the one exact task attempt; never replay."""
        normalized = schedule_id.strip()
        if not normalized:
            raise ResearchError("One-shot deferred schedule ID cannot be empty.")
        now = self._now()
        with self._lock:
            schedules = self._schedules.load()
            schedule = self._exact_pending(schedules, normalized)
            if now < schedule.run_at:
                raise ResearchError("This one-shot deferred run is not due yet.")
            grant = self._grants.active_for_task(schedule.task_id)
            if grant is None or grant.grant_id != schedule.grant_id:
                skipped = schedule.skipped(
                    now, "trusted_grant_unavailable_at_fire_time"
                )
                self._save_replacement(schedules, skipped)
                return skipped
            claimed = schedule.claimed(now)
            self._save_replacement(schedules, claimed)

        try:
            result = self._runner.run_exact_deferred_background_task(
                claimed.task_id,
                cancellation_token,
            )
        except HypatiaError:
            self._finish_claimed(claimed.schedule_id, "execution_boundary_refused")
            raise
        except Exception:
            self._finish_claimed(claimed.schedule_id, "execution_boundary_failed")
            raise
        if result is None:
            return self._finish_claimed(
                claimed.schedule_id, "not_eligible_at_fire_time"
            )
        return self._finish_claimed(claimed.schedule_id)

    def skip_due_to_busy(self, schedule_id: str) -> OneShotDeferredExecutionSchedule:
        normalized = schedule_id.strip()
        now = self._now()
        with self._lock:
            schedules = self._schedules.load()
            schedule = self._exact_pending(schedules, normalized)
            skipped = schedule.skipped(now, "desktop_worker_busy_at_fire_time")
            self._save_replacement(schedules, skipped)
            return skipped

    def _finish_claimed(
        self, schedule_id: str, skip_reason: str | None = None
    ) -> OneShotDeferredExecutionSchedule:
        with self._lock:
            schedules = self._schedules.load()
            matches = [value for value in schedules if value.schedule_id == schedule_id]
            if len(matches) != 1:
                raise ResearchError("The claimed one-shot schedule disappeared.")
            claimed = matches[0]
            if claimed.status is not OneShotDeferredExecutionScheduleStatus.CLAIMED:
                raise ResearchError("The one-shot schedule is no longer claimed.")
            now = self._now()
            finished = (
                claimed.triggered(now)
                if skip_reason is None
                else claimed.skipped(now, skip_reason)
            )
            self._save_replacement(schedules, finished)
            return finished

    def _valid_run_at(self, run_at: datetime) -> datetime:
        if run_at.tzinfo is None or run_at.utcoffset() is None:
            raise ResearchError("One-shot deferred run time must include a timezone.")
        normalized = run_at.astimezone(UTC)
        now = self._now()
        if normalized <= now:
            raise ResearchError("One-shot deferred run time must be in the future.")
        if normalized - now > MAX_ONE_SHOT_DEFERRED_DELAY:
            raise ResearchError("One-shot deferred run time cannot exceed seven days.")
        return normalized

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ResearchError("One-shot deferred clock must be timezone-aware.")
        return value.astimezone(UTC)

    @staticmethod
    def _pending_for_task(
        schedules: list[OneShotDeferredExecutionSchedule], task_id: str
    ) -> OneShotDeferredExecutionSchedule | None:
        matches = [
            value for value in schedules if value.task_id == task_id and value.pending
        ]
        return matches[0] if len(matches) == 1 else None

    @staticmethod
    def _exact_pending(
        schedules: list[OneShotDeferredExecutionSchedule], schedule_id: str
    ) -> OneShotDeferredExecutionSchedule:
        matches = [
            value
            for value in schedules
            if value.schedule_id == schedule_id and value.pending
        ]
        if len(matches) != 1:
            raise ResearchError("No exact pending one-shot schedule has that ID.")
        return matches[0]

    def _save_replacement(
        self,
        schedules: list[OneShotDeferredExecutionSchedule],
        replacement: OneShotDeferredExecutionSchedule,
    ) -> None:
        self._schedules.save(
            [
                replacement if value.schedule_id == replacement.schedule_id else value
                for value in schedules
            ]
        )
