"""Traceable external source acquired for an explicit research request."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from core.Exceptions import ResearchError
from knowledge.Document import Document, DocumentType


@dataclass(frozen=True, slots=True)
class ResearchSource:
    """Preserve source identity and extracted text before knowledge indexing."""

    url: str
    title: str
    content: str
    content_type: str
    fetched_at: datetime

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.url, "Research source URL"),
            (self.title, "Research source title"),
            (self.content, "Research source content"),
            (self.content_type, "Research source content type"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ResearchError(f"{field_name} cannot be empty.")
        if (
            not isinstance(self.fetched_at, datetime)
            or self.fetched_at.utcoffset() is None
        ):
            raise ResearchError("Research source fetch time must be timezone-aware.")
        object.__setattr__(self, "url", self.url.strip())
        object.__setattr__(self, "title", self.title.strip())
        object.__setattr__(self, "content", self.content.strip())
        object.__setattr__(self, "content_type", self.content_type.strip().casefold())

    def to_document(self) -> Document:
        """Create a stable web document for the existing knowledge pipeline."""
        return Document(
            title=self.title,
            content=self.content,
            source=self.url,
            document_type=DocumentType.WEB,
            metadata={
                "content_type": self.content_type,
                "fetched_at": self.fetched_at.astimezone(UTC).isoformat(),
                "acquisition": "explicit_https",
            },
            document_id=str(uuid5(NAMESPACE_URL, self.url)),
            created_at=self.fetched_at,
            updated_at=self.fetched_at,
        )
