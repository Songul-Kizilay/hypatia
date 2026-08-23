"""Structured outcome of one bounded autonomous research run.

Stopping is not failure. A run that exhausts its budget, reaches a blocked or
interrupted step, or finds nothing left to do has behaved correctly; the reason
says which happened.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from core.Exceptions import ResearchError


class AutonomyStopReason(StrEnum):
    """Bounded explanations for why an autonomous run stopped."""

    EXECUTION_TERMINAL = "execution_terminal"
    NO_PENDING_STEP = "no_pending_step"
    STEP_BLOCKED = "step_blocked"
    STEP_INTERRUPTED = "step_interrupted"
    STEP_FAILED = "step_failed"
    CANCELLED = "cancelled"
    STEP_BUDGET_EXHAUSTED = "step_budget_exhausted"
    NETWORK_BUDGET_EXHAUSTED = "network_budget_exhausted"
    LLM_BUDGET_EXHAUSTED = "llm_budget_exhausted"
    TIME_BUDGET_EXHAUSTED = "time_budget_exhausted"


@dataclass(frozen=True, slots=True)
class ResearchAutonomyResult:
    """Report exactly what one autonomous run did and why it stopped."""

    plan_id: str
    stop_reason: AutonomyStopReason
    execution_status: str
    steps_attempted: int = 0
    operations_performed: int = 0
    network_operations: int = 0
    llm_operations: int = 0
    elapsed_seconds: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.plan_id, str) or not self.plan_id.strip():
            raise ResearchError("Autonomy result plan ID cannot be empty.")
        if not isinstance(self.stop_reason, AutonomyStopReason):
            raise ResearchError("Autonomy result stop reason is invalid.")
        if not isinstance(self.execution_status, str):
            raise ResearchError("Autonomy result execution status is invalid.")
        for value, label in (
            (self.steps_attempted, "steps attempted"),
            (self.operations_performed, "operations performed"),
            (self.network_operations, "network operations"),
            (self.llm_operations, "LLM operations"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ResearchError(f"Autonomy result {label} is invalid.")
        if self.operations_performed > self.steps_attempted:
            raise ResearchError(
                "Autonomy cannot perform more operations than steps attempted."
            )
        if (
            isinstance(self.elapsed_seconds, bool)
            or not isinstance(self.elapsed_seconds, int | float)
            or self.elapsed_seconds < 0
        ):
            raise ResearchError("Autonomy result elapsed time is invalid.")
        object.__setattr__(self, "plan_id", self.plan_id.strip())
