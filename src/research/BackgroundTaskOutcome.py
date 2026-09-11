"""Typed classification of what one autonomy run means for its task.

Retry decisions are made from the autonomy stop-reason enum, never by parsing
an exception message. The table is exhaustive: a new stop reason without a
declared outcome raises rather than defaulting to a retry.

Only budget exhaustion is retryable. It means the task did not fail — it ran out
of allowance for this cycle and more work remains. A blocked, failed, or
interrupted run is never retried automatically, because retrying an
authorization refusal, a validation refusal, or unknown mid-flight work would be
a retry storm at best and a repeated side effect at worst.
"""

from __future__ import annotations

from enum import StrEnum

from core.Exceptions import ResearchError
from research.ResearchAutonomyResult import AutonomyStopReason


class BackgroundTaskOutcome(StrEnum):
    """What one autonomy run means for the task that scheduled it."""

    COMPLETED = "completed"
    RETRYABLE_BUDGET_EXHAUSTED = "retryable_budget_exhausted"
    BLOCKED = "blocked"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
    CANCELLED = "cancelled"

    @property
    def retryable(self) -> bool:
        """Return whether a scheduler may schedule another attempt."""
        return self is BackgroundTaskOutcome.RETRYABLE_BUDGET_EXHAUSTED


_OUTCOMES: dict[AutonomyStopReason, BackgroundTaskOutcome] = {
    AutonomyStopReason.EXECUTION_TERMINAL: BackgroundTaskOutcome.COMPLETED,
    AutonomyStopReason.NO_PENDING_STEP: BackgroundTaskOutcome.COMPLETED,
    AutonomyStopReason.STEP_BLOCKED: BackgroundTaskOutcome.BLOCKED,
    AutonomyStopReason.ADVANCE_REFUSED: BackgroundTaskOutcome.BLOCKED,
    AutonomyStopReason.STEP_INTERRUPTED: BackgroundTaskOutcome.INTERRUPTED,
    AutonomyStopReason.STEP_FAILED: BackgroundTaskOutcome.FAILED,
    AutonomyStopReason.CANCELLED: BackgroundTaskOutcome.CANCELLED,
    AutonomyStopReason.STEP_BUDGET_EXHAUSTED: (
        BackgroundTaskOutcome.RETRYABLE_BUDGET_EXHAUSTED
    ),
    AutonomyStopReason.NETWORK_BUDGET_EXHAUSTED: (
        BackgroundTaskOutcome.RETRYABLE_BUDGET_EXHAUSTED
    ),
    AutonomyStopReason.LLM_BUDGET_EXHAUSTED: (
        BackgroundTaskOutcome.RETRYABLE_BUDGET_EXHAUSTED
    ),
    AutonomyStopReason.TIME_BUDGET_EXHAUSTED: (
        BackgroundTaskOutcome.RETRYABLE_BUDGET_EXHAUSTED
    ),
}


def outcome_for(stop_reason: AutonomyStopReason) -> BackgroundTaskOutcome:
    """Classify one stop reason, refusing an undeclared one."""
    if not isinstance(stop_reason, AutonomyStopReason):
        raise ResearchError("Autonomy stop reason is invalid.")
    outcome = _OUTCOMES.get(stop_reason)
    if outcome is None:
        raise ResearchError(
            f"Autonomy stop reason '{stop_reason.value}' has no declared outcome."
        )
    return outcome
