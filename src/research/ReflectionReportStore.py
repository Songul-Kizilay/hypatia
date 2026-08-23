"""Replaceable persistence boundary for research reflection reports."""

from typing import Protocol

from research.ResearchReflectionReport import ResearchReflectionReport


class ReflectionReportStore(Protocol):
    """Load and atomically replace the complete reflection report set."""

    def load(self) -> list[ResearchReflectionReport]:
        """Return every persisted report, or an empty list when absent."""

    def save(self, reports: list[ResearchReflectionReport]) -> None:
        """Atomically replace the persisted report set."""
