"""Bounded persisted content for one explicitly accepted research source."""

from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass
from datetime import datetime

from core.Exceptions import ResearchError
from research.ResearchSource import ResearchSource

MAX_SOURCE_CONTENT_UTF8_BYTES = 4_000_000
_MAXIMUM_DOCUMENT_ID_CHARACTERS = 200
_MAXIMUM_URL_CHARACTERS = 4_096
_MAXIMUM_TITLE_CHARACTERS = 1_000
_MAXIMUM_CONTENT_TYPE_CHARACTERS = 255
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class ResearchSourceContentRecord:
    """Bind exact accepted text to provenance and a complete integrity digest."""

    document_id: str
    url: str
    title: str
    content: str
    content_type: str
    fetched_at: datetime
    stored_at: datetime
    content_byte_count: int
    content_sha256: str

    def __post_init__(self) -> None:
        normalized_values = (
            self._bounded_text(
                self.document_id,
                "Research source content document ID",
                _MAXIMUM_DOCUMENT_ID_CHARACTERS,
            ),
            self._bounded_text(
                self.url,
                "Research source content URL",
                _MAXIMUM_URL_CHARACTERS,
            ),
            self._bounded_text(
                self.title,
                "Research source content title",
                _MAXIMUM_TITLE_CHARACTERS,
            ),
            self._bounded_text(
                self.content_type,
                "Research source content type",
                _MAXIMUM_CONTENT_TYPE_CHARACTERS,
            ).casefold(),
        )
        document_id, url, title, content_type = normalized_values
        if not isinstance(self.content, str) or not self.content.strip():
            raise ResearchError("Research source persisted content cannot be empty.")
        try:
            encoded_content = self.content.encode("utf-8")
        except UnicodeEncodeError as error:
            raise ResearchError(
                "Research source persisted content is not valid Unicode."
            ) from error
        if len(encoded_content) > MAX_SOURCE_CONTENT_UTF8_BYTES:
            raise ResearchError("Research source persisted content is too large.")
        for timestamp, label in (
            (self.fetched_at, "fetch time"),
            (self.stored_at, "storage time"),
        ):
            if not isinstance(timestamp, datetime) or timestamp.utcoffset() is None:
                raise ResearchError(
                    f"Research source content {label} must be timezone-aware."
                )
        if self.stored_at < self.fetched_at:
            raise ResearchError(
                "Research source content cannot be stored before it was fetched."
            )
        if (
            isinstance(self.content_byte_count, bool)
            or not isinstance(self.content_byte_count, int)
            or self.content_byte_count != len(encoded_content)
        ):
            raise ResearchError("Research source persisted byte count is invalid.")
        normalized_sha256 = (
            self.content_sha256.strip().casefold()
            if isinstance(self.content_sha256, str)
            else ""
        )
        observed_sha256 = hashlib.sha256(encoded_content).hexdigest()
        if not _SHA256_PATTERN.fullmatch(normalized_sha256) or not hmac.compare_digest(
            normalized_sha256,
            observed_sha256,
        ):
            raise ResearchError("Research source persisted fingerprint is invalid.")
        object.__setattr__(self, "document_id", document_id)
        object.__setattr__(self, "url", url)
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "content_type", content_type)
        object.__setattr__(self, "content_sha256", normalized_sha256)

    @classmethod
    def from_source(
        cls,
        source: ResearchSource,
        document_id: str,
        stored_at: datetime,
    ) -> ResearchSourceContentRecord:
        """Create one integrity-bound record from an acquired source."""
        if not isinstance(source, ResearchSource):
            raise ResearchError("Persisted source content expects a ResearchSource.")
        try:
            encoded_content = source.content.encode("utf-8")
        except UnicodeEncodeError as error:
            raise ResearchError(
                "Research source persisted content is not valid Unicode."
            ) from error
        return cls(
            document_id=document_id,
            url=source.url,
            title=source.title,
            content=source.content,
            content_type=source.content_type,
            fetched_at=source.fetched_at,
            stored_at=stored_at,
            content_byte_count=len(encoded_content),
            content_sha256=hashlib.sha256(encoded_content).hexdigest(),
        )

    @staticmethod
    def _bounded_text(value: str, label: str, maximum: int) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ResearchError(f"{label} cannot be empty.")
        normalized = value.strip()
        if len(normalized) > maximum:
            raise ResearchError(f"{label} is too long.")
        return normalized
