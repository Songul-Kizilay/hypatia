"""Replaceable persistence boundary for durable plan authorizations."""

from __future__ import annotations

from typing import Protocol

from research.ResearchPlanAuthorization import ResearchPlanAuthorization


class ResearchPlanAuthorizationStore(Protocol):
    """Load and atomically replace the complete authorization set."""

    def load(self) -> list[ResearchPlanAuthorization]:
        """Return every persisted authorization, or an empty list when absent."""

    def save(self, authorizations: list[ResearchPlanAuthorization]) -> None:
        """Atomically replace the persisted authorization set."""
