"""Traceable external source acquired for an explicit research request."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
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

    So resource identity stays with the URL and origin is recorded beside it.
    Left empty, the two coincide and the source is exactly what it says it is.
    The indexed document is a content version of that resource, never the URL
    itself: the same URL can serve different text at different times.
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

    @property
    def content_sha256(self) -> str:
        """SHA-256 of the exact stored text, as persisted content records use."""
        return sha256(self.content.encode("utf-8")).hexdigest()

    def content_version_id(self) -> str:
        """Immutable identity of this exact representation, not of the URL.

        The same URL serving different text is a different content version, so
        a later fetch can never be resolved to an earlier fetch's document.  The
        same representation fetched twice yields the same version; that shares
        immutable storage only, never the observation that fetched it.
        """
        representation = json.dumps(
            [
                self.url,
                self.title,
                self.content_type,
                self.content_resource,
                self.acquisition,
                self.content_sha256,
            ],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        digest = sha256(representation.encode("utf-8")).hexdigest()
        return str(uuid5(NAMESPACE_URL, f"hypatia:source-content-version:{digest}"))

    def legacy_document_id(self) -> str:
        """The URL-only identity used before content versioning (v0.3.380)."""
        return str(uuid5(NAMESPACE_URL, self.url))

    def to_document(self, document_id: str | None = None) -> Document:
        """Create one content-versioned web document for the knowledge pipeline.

        The identity is the content version by default.  Only restoration of
        content accepted before versioning may pass the legacy URL identity,
        which it must prove by matching the persisted record exactly.
        """
        if document_id is None:
            document_id = self.content_version_id()
        elif document_id not in {self.content_version_id(), self.legacy_document_id()}:
            raise ResearchError("Research source document identity is invalid.")
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
            document_id=document_id,
            created_at=self.fetched_at,
            updated_at=self.fetched_at,
        )
