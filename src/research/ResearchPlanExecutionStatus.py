"""Lifecycle states for one explicitly started research-plan execution."""

from enum import StrEnum


class ResearchPlanExecutionStatus(StrEnum):
    """Bounded execution lifecycle for a user-authored research plan."""

    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"
    INTERRUPTED = "interrupted"

    @property
    def terminal(self) -> bool:
        """Return whether this status closes further execution progress."""
        return self in _TERMINAL_EXECUTION_STATUSES


_TERMINAL_EXECUTION_STATUSES = frozenset(
    {
        ResearchPlanExecutionStatus.COMPLETED,
        ResearchPlanExecutionStatus.FAILED,
        ResearchPlanExecutionStatus.CANCELLED,
    }
)
