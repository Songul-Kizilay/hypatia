"""Replaceable persistence boundary for research-plan execution snapshots."""

from typing import Protocol

from research.ResearchPlanExecutionSnapshot import ResearchPlanExecutionSnapshot


class ResearchExecutionStore(Protocol):
    """Load and atomically replace the complete execution snapshot set."""

    def load(self) -> list[ResearchPlanExecutionSnapshot]:
        """Return every persisted snapshot, or an empty list when absent."""

    def save(self, snapshots: list[ResearchPlanExecutionSnapshot]) -> None:
        """Atomically replace the persisted snapshot set."""
