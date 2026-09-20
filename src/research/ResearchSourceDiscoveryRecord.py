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
    #: A stable identity for each candidate, in candidate order, assigned when
    #: the discovery is recorded.  Selection records this identity, never the
    #: URL, so provenance does not depend on later URL matching.  Empty for
    #: discoveries recorded before candidate identity existed.
    candidate_ids: tuple[str, ...] = ()

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
        if not isinstance(self.candidate_ids, tuple) or (
            self.candidate_ids
            and (
                len(self.candidate_ids) != len(self.candidates)
                or len(set(self.candidate_ids)) != len(self.candidate_ids)
                or any(
                    not isinstance(value, str)
                    or not value.strip()
                    or value != value.strip()
                    or len(value) > 200
                    for value in self.candidate_ids
                )
            )
        ):
            raise ResearchError("Research source discovery candidate IDs are invalid.")
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

    def candidate_id_of(self, candidate: ResearchSourceCandidate) -> str | None:
        """Return the recorded identity of this exact candidate object, if any.

        Used at selection time on a candidate taken from this record, never to
        match a URL seen later.  ``None`` when identities were not recorded.
        """
        if not self.candidate_ids:
            return None
        for index, value in enumerate(self.candidates):
            if value is candidate:
                return self.candidate_ids[index]
        return None
