"""Persistence contract for complete memory snapshots."""

from __future__ import annotations

from typing import Protocol

from memory.MemoryRecord import MemoryRecord


class MemoryStore(Protocol):
    """Persistence boundary for memory snapshots."""

    def load(self) -> list[MemoryRecord]:
        """Load and return a fully validated memory snapshot."""

    def save(self, records: list[MemoryRecord]) -> None:
        """Persist the complete memory snapshot."""
