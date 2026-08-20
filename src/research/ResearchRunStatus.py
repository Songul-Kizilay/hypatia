"""Lifecycle states for a persisted research run."""

from enum import StrEnum


class ResearchRunStatus(StrEnum):
    """Current bounded lifecycle for source-collection work."""

    COLLECTING = "collecting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def terminal(self) -> bool:
        """Return whether this status closes further run mutation."""
        return self is not ResearchRunStatus.COLLECTING
