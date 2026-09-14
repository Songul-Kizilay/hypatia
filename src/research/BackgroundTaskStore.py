"""Replaceable persistence boundary for background research tasks."""

from typing import Protocol

from research.BackgroundResearchTask import BackgroundResearchTask


class BackgroundTaskStore(Protocol):
    """Load and atomically replace the complete background task set."""

    def load(self) -> list[BackgroundResearchTask]:
        """Return every persisted task, or an empty list when absent."""

    def save(self, tasks: list[BackgroundResearchTask]) -> None:
        """Atomically replace the persisted task set."""
