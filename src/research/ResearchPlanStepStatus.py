"""Lifecycle states for one step inside a research-plan execution."""

from enum import StrEnum


class ResearchPlanStepStatus(StrEnum):
    """Bounded execution lifecycle for one authored plan step."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"

    @property
    def terminal(self) -> bool:
        """Return whether this status closes further step progress."""
        return self in _TERMINAL_STEP_STATUSES


_TERMINAL_STEP_STATUSES = frozenset(
    {
        ResearchPlanStepStatus.COMPLETED,
        ResearchPlanStepStatus.FAILED,
        ResearchPlanStepStatus.CANCELLED,
    }
)
