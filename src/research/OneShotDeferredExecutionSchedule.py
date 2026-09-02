"""Immutable durable record for one exact future deferred attempt."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from core.Exceptions import ResearchError
from research.DeferredGrantAuthorizer import DeferredGrantAuthorizer
from research.OneShotDeferredExecutionScheduleStatus import (
    OneShotDeferredExecutionScheduleStatus,
)

MAX_ONE_SHOT_SCHEDULE_TEXT_LENGTH = 200


@dataclass(frozen=True, slots=True)
class OneShotDeferredExecutionSchedule:
    """One trusted, non-recurring request to try one granted task once."""

    schedule_id: str
    task_id: str
    grant_id: str
    run_at: datetime
    created_at: datetime
    created_by: DeferredGrantAuthorizer
    status: OneShotDeferredExecutionScheduleStatus = (
        OneShotDeferredExecutionScheduleStatus.PENDING
    )
    resolved_at: datetime | None = None
    outcome: str | None = None

    def __post_init__(self) -> None:
        for label, value in (
            ("schedule ID", self.schedule_id),
            ("task ID", self.task_id),
            ("grant ID", self.grant_id),
        ):
            if not value.strip() or len(value) > MAX_ONE_SHOT_SCHEDULE_TEXT_LENGTH:
                raise ResearchError(f"One-shot deferred {label} is invalid.")
        if not isinstance(self.created_by, DeferredGrantAuthorizer):
            raise ResearchError("One-shot deferred provenance is invalid.")
        self._aware_utc(self.run_at, "run time")
        self._aware_utc(self.created_at, "creation time")
        if self.run_at <= self.created_at:
            raise ResearchError("One-shot deferred run time must be in the future.")
        if self.status is OneShotDeferredExecutionScheduleStatus.PENDING:
            if self.resolved_at is not None or self.outcome is not None:
                raise ResearchError("A pending one-shot schedule cannot be resolved.")
            return
        if self.resolved_at is None or not self.outcome:
            raise ResearchError("A resolved one-shot schedule needs an outcome.")
        self._aware_utc(self.resolved_at, "resolution time")
        if self.resolved_at < self.created_at:
            raise ResearchError("One-shot schedule resolution precedes creation.")
        if len(self.outcome) > MAX_ONE_SHOT_SCHEDULE_TEXT_LENGTH:
            raise ResearchError("One-shot schedule outcome is too long.")

    @property
    def pending(self) -> bool:
        return self.status is OneShotDeferredExecutionScheduleStatus.PENDING

    def claimed(self, at: datetime) -> OneShotDeferredExecutionSchedule:
        if not self.pending:
            raise ResearchError("Only a pending one-shot schedule can be claimed.")
        self._not_before_run_time(at)
        return replace(
            self,
            status=OneShotDeferredExecutionScheduleStatus.CLAIMED,
            resolved_at=at,
            outcome="claimed_before_execution",
        )

    def triggered(self, at: datetime) -> OneShotDeferredExecutionSchedule:
        if self.status is not OneShotDeferredExecutionScheduleStatus.CLAIMED:
            raise ResearchError("Only a claimed one-shot schedule can finish.")
        self._not_before_run_time(at)
        return replace(
            self,
            status=OneShotDeferredExecutionScheduleStatus.TRIGGERED,
            resolved_at=at,
            outcome="exact_task_attempted",
        )

    def skipped(self, at: datetime, reason: str) -> OneShotDeferredExecutionSchedule:
        if self.status not in (
            OneShotDeferredExecutionScheduleStatus.PENDING,
            OneShotDeferredExecutionScheduleStatus.CLAIMED,
        ):
            raise ResearchError("This one-shot schedule is already resolved.")
        normalized = reason.strip()
        if not normalized:
            raise ResearchError("A skipped one-shot schedule needs a reason.")
        self._not_before_run_time(at)
        return replace(
            self,
            status=OneShotDeferredExecutionScheduleStatus.SKIPPED,
            resolved_at=at,
            outcome=normalized,
        )

    def cancelled(self, at: datetime) -> OneShotDeferredExecutionSchedule:
        if not self.pending:
            raise ResearchError("Only a pending one-shot schedule can be cancelled.")
        self._aware_utc(at, "cancellation time")
        return replace(
            self,
            status=OneShotDeferredExecutionScheduleStatus.CANCELLED,
            resolved_at=at,
            outcome="cancelled_by_trusted_local_operator",
        )

    def _not_before_run_time(self, at: datetime) -> None:
        self._aware_utc(at, "resolution time")
        if at < self.run_at:
            raise ResearchError("A one-shot schedule cannot fire before its run time.")

    @staticmethod
    def _aware_utc(value: datetime, label: str) -> None:
        if not isinstance(value, datetime) or value.utcoffset() is None:
            raise ResearchError(f"One-shot deferred {label} must be timezone-aware.")
        if value.utcoffset() != timedelta(0):
            raise ResearchError(f"One-shot deferred {label} must be stored in UTC.")
