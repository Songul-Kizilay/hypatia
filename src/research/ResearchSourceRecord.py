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
        )
