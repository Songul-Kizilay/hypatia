"""Persistence boundary for explicitly accepted research source text."""

from __future__ import annotations

from typing import Protocol

from research.ResearchSourceContentRecord import ResearchSourceContentRecord


class ResearchSourceContentStore(Protocol):
    """Load or atomically replace the complete accepted-content snapshot."""

    def load(self) -> list[ResearchSourceContentRecord]:
        """Return all validated records in deterministic storage order."""

    def save(self, records: list[ResearchSourceContentRecord]) -> None:
        """Atomically replace the complete validated record collection."""
