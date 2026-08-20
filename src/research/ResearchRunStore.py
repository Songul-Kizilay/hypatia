"""Persistence boundary for complete research-run snapshots."""

from __future__ import annotations

from typing import Protocol

from research.ResearchRun import ResearchRun


class ResearchRunStore(Protocol):
    """Load and atomically replace complete research-run snapshots."""

    def load(self) -> list[ResearchRun]:
        """Load all persisted runs in creation order."""

    def save(self, runs: list[ResearchRun]) -> None:
        """Atomically persist all runs in creation order."""
