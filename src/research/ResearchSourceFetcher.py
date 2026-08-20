"""Replaceable external-source acquisition boundary."""

from __future__ import annotations

from typing import Protocol

from research.ResearchSource import ResearchSource


class ResearchSourceFetcher(Protocol):
    """Fetch one user-selected source without deciding what should be researched."""

    def fetch(self, url: str) -> ResearchSource:
        """Return extracted, traceable source content or raise ResearchError."""
