"""Replaceable persistence boundary for Kali operation authorizations."""

from __future__ import annotations

from typing import Protocol

from research.ResearchKaliOperationAuthorization import (
    ResearchKaliOperationAuthorization,
)


class ResearchKaliOperationAuthorizationStore(Protocol):
    """Load and atomically replace the complete operation authorization set."""

    def load(self) -> list[ResearchKaliOperationAuthorization]:
        """Return every persisted authorization, or an empty list when absent."""

    def save(
        self,
        authorizations: list[ResearchKaliOperationAuthorization],
    ) -> None:
        """Atomically replace the persisted operation authorization set."""
