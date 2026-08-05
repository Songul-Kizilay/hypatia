"""Persistence contract for complete session registry snapshots."""

from __future__ import annotations

from typing import Protocol

from session.SessionRegistrySnapshot import SessionRegistrySnapshot


class SessionStore(Protocol):
    """Persistence boundary for complete session registry snapshots."""

    def load(self) -> SessionRegistrySnapshot | None:
        """Load a validated snapshot, or return None when no store exists."""

    def save(self, snapshot: SessionRegistrySnapshot) -> None:
        """Persist the complete session registry snapshot."""
