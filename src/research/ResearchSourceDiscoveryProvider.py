"""Replaceable read-only source-discovery boundary."""

from __future__ import annotations

from typing import Protocol

from research.ResearchSourceCandidate import ResearchSourceCandidate


class ResearchSourceDiscoveryProvider(Protocol):
    """Find metadata candidates without fetching or accepting source content."""

    @property
    def provider_name(self) -> str:
        """Return the stable provider identity stored in the audit record."""
        ...

    def discover(
        self,
        query: str,
        *,
        limit: int,
    ) -> list[ResearchSourceCandidate]:
        """Return at most ``limit`` ordered, unaccepted source candidates."""
        ...
