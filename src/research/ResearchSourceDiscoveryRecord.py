"""Persistent audit record for one bounded source-discovery operation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.Exceptions import ResearchError
from research.ResearchSourceCandidate import ResearchSourceCandidate


@dataclass(frozen=True, slots=True)
class ResearchSourceDiscoveryRecord:
    """Keep the query, provider, ordered candidates, and discovery time."""

    discovery_id: str
    query: str
    provider: str
    candidates: tuple[ResearchSourceCandidate, ...]
    discovered_at: datetime

    def __post_init__(self) -> None:
        for value, field_name, maximum in (
            (self.discovery_id, "Research source discovery ID", 200),
            (self.query, "Research source discovery query", 2_000),
            (self.provider, "Research source discovery provider", 200),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ResearchError(f"{field_name} cannot be empty.")
            if len(value.strip()) > maximum:
                raise ResearchError(f"{field_name} is too long.")
        if any(
            character in self.discovery_id or character in self.provider
            for character in ("\r", "\n", "\t")
        ):
            raise ResearchError("Research source discovery identity is invalid.")
        if not isinstance(self.candidates, tuple):
            raise ResearchError(
                "Research source discovery candidates must be an immutable tuple."
            )
        if len(self.candidates) > 10:
            raise ResearchError(
                "Research source discovery cannot contain more than 10 candidates."
            )
        if not all(
            isinstance(candidate, ResearchSourceCandidate)
            for candidate in self.candidates
        ):
            raise ResearchError(
                "Research source discovery contains an invalid candidate."
            )
        urls = [candidate.url for candidate in self.candidates]
        if len(urls) != len(set(urls)):
            raise ResearchError("Research source discovery contains duplicate URLs.")
        if (
            not isinstance(self.discovered_at, datetime)
            or self.discovered_at.utcoffset() is None
        ):
            raise ResearchError(
                "Research source discovery time must be timezone-aware."
            )

        object.__setattr__(self, "discovery_id", self.discovery_id.strip())
        object.__setattr__(self, "query", self.query.strip())
        object.__setattr__(self, "provider", self.provider.strip())
