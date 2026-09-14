"""Traceable external source acquired for an explicit research request."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from core.Exceptions import ResearchError
from knowledge.Document import Document, DocumentType

#: How the bytes were obtained. The default names the ordinary path: an HTTPS
#: GET of the URL itself, where the resource read and the resource named are the
#: same thing. A provider-specific route sets its own value precisely because
#: that equality no longer holds.
HTTPS_ACQUISITION = "explicit_https"


@dataclass(frozen=True, slots=True)
class ResearchSource:
    """Preserve source identity and extracted text before knowledge indexing.

    `url` is what this source *is* — the resource a person opens, the identity
    duplicate detection and provider comparison both join on. `content_resource`
    is where the bytes actually came from, and it exists because those are not
    always the same: an NVD record is named by its human-facing detail page and
    read from the CVE API, and recording the API endpoint as the source's
    identity would make every accepted CVE the same resource as every other.

    So identity stays with the URL and origin is recorded beside it. Left empty,
    the two coincide and the source is exactly what it says it is.
    """

    url: str
    title: str
    content: str
    content_type: str
    fetched_at: datetime
    content_resource: str = ""
    acquisition: str = HTTPS_ACQUISITION

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
        for name in ("content_resource", "acquisition"):
            value = getattr(self, name)
            if not isinstance(value, str):
                raise ResearchError(f"Research source {name} must be text.")
            object.__setattr__(self, name, value.strip())
        if not self.acquisition:
            raise ResearchError("Research source acquisition cannot be empty.")

    def to_document(self) -> Document:
        """Create a stable web document for the existing knowledge pipeline.

        The document identity stays derived from the URL, so the same resource
        accepted twice is the same document however its bytes were obtained.
        """
        metadata = {
            "content_type": self.content_type,
            "fetched_at": self.fetched_at.astimezone(UTC).isoformat(),
            "acquisition": self.acquisition,
        }
        if self.content_resource:
            metadata["content_resource"] = self.content_resource
        return Document(
            title=self.title,
            content=self.content,
            source=self.url,
            document_type=DocumentType.WEB,
            metadata=metadata,
            document_id=str(uuid5(NAMESPACE_URL, self.url)),
            created_at=self.fetched_at,
            updated_at=self.fetched_at,
        )
