"""Lifecycle states for one exact non-recurring deferred attempt."""

from enum import StrEnum


class OneShotDeferredExecutionScheduleStatus(StrEnum):
    PENDING = "pending"
    CLAIMED = "claimed"
    TRIGGERED = "triggered"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
