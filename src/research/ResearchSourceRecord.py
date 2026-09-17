"""Persisted provenance for a source accepted into a research run."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.Exceptions import ResearchError
from research.ResearchSource import ResearchSource

EXTERNAL_SOURCE_TAINT_LABEL = "external_untrusted_data"
EXTERNAL_SOURCE_INSTRUCTION_AUTHORITY = "none"


@dataclass(frozen=True, slots=True)
class ResearchSourceRecord:
    """Keep source provenance without duplicating downloaded page content."""

    document_id: str
    url: str
    title: str
    content_type: str
    fetched_at: datetime
    added_at: datetime
    taint_label: str = EXTERNAL_SOURCE_TAINT_LABEL
    instruction_authority: str = EXTERNAL_SOURCE_INSTRUCTION_AUTHORITY
    #: SHA-256 of the exact text this run fetched and accepted: the content
    #: version it observed.  ``None`` for sources accepted before versioning,
    #: whose observed content was not recorded and is never inferred.
    content_sha256: str | None = None
    #: The authorized URL this run requested.  ``url`` is where the fetch ended
    #: after validated redirects, so the two can differ.  ``None`` for sources
    #: accepted before it was recorded; it is never inferred from ``url``.
    requested_url: str | None = None
    #: The recorded identity of the discovery candidate this run selected and
    #: requested, when the source came from a discovery.  ``None`` when the
    #: source was not selected from a discovery or predates candidate identity;
    #: it is never recovered by matching URLs.
    discovery_candidate_id: str | None = None

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.document_id, "Research source document ID"),
            (self.url, "Research source URL"),
            (self.title, "Research source title"),
            (self.content_type, "Research source content type"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ResearchError(f"{field_name} cannot be empty.")
        for timestamp, field_name in (
            (self.fetched_at, "Research source fetch time"),
            (self.added_at, "Research source addition time"),
        ):
            if not isinstance(timestamp, datetime) or timestamp.utcoffset() is None:
                raise ResearchError(f"{field_name} must be timezone-aware.")
        if self.taint_label != EXTERNAL_SOURCE_TAINT_LABEL:
            raise ResearchError("External research source taint label is invalid.")
        if self.instruction_authority != EXTERNAL_SOURCE_INSTRUCTION_AUTHORITY:
            raise ResearchError(
                "External research source instruction authority must be none."
            )
        if self.content_sha256 is not None and (
            not isinstance(self.content_sha256, str)
            or len(self.content_sha256) != 64
            or any(c not in "0123456789abcdef" for c in self.content_sha256)
        ):
            raise ResearchError("Research source content fingerprint is invalid.")
        if self.requested_url is not None:
            if (
                not isinstance(self.requested_url, str)
                or not self.requested_url.strip()
                or len(self.requested_url.strip()) > 4_096
            ):
                raise ResearchError("Research source requested URL is invalid.")
            object.__setattr__(self, "requested_url", self.requested_url.strip())
        if self.discovery_candidate_id is not None and (
            not isinstance(self.discovery_candidate_id, str)
            or not self.discovery_candidate_id.strip()
            or self.discovery_candidate_id != self.discovery_candidate_id.strip()
            or len(self.discovery_candidate_id) > 200
        ):
            raise ResearchError("Research source discovery candidate ID is invalid.")
        object.__setattr__(self, "document_id", self.document_id.strip())
        object.__setattr__(self, "url", self.url.strip())
        object.__setattr__(self, "title", self.title.strip())
        object.__setattr__(self, "content_type", self.content_type.strip().casefold())

    @classmethod
    def from_source(
        cls,
        source: ResearchSource,
        document_id: str,
        added_at: datetime,
        requested_url: str | None = None,
        discovery_candidate_id: str | None = None,
    ) -> ResearchSourceRecord:
        """Build a persistent provenance record from a fetched source."""
        if not isinstance(source, ResearchSource):
            raise ResearchError("Research source record expects a ResearchSource.")
        return cls(
            document_id=document_id,
            url=source.url,
            title=source.title,
            content_type=source.content_type,
            fetched_at=source.fetched_at,
            added_at=added_at,
            content_sha256=source.content_sha256,
            requested_url=requested_url,
            discovery_candidate_id=discovery_candidate_id,
        )
