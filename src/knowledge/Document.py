"""Common source document model for the Knowledge Foundation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class DocumentType(StrEnum):
    """Supported source document formats."""

    TEXT = "text"
    MARKDOWN = "markdown"
    PDF = "pdf"
    WEB = "web"
    NOTE = "note"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class Document:
    """Represents source content before it is parsed or indexed."""

    title: str
    content: str
    source: str = ""
    document_type: DocumentType = DocumentType.UNKNOWN
    metadata: dict[str, Any] = field(default_factory=dict)
    document_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self.title = self._validate_text(self.title, "Document title")
        self.content = self._validate_text(self.content, "Document content")
        self.source = self.source.strip()

    def update_content(self, content: str) -> None:
        """Replace the document content and refresh its update timestamp."""
        self.content = self._validate_text(content, "Document content")
        self.updated_at = datetime.now(UTC)

    def size(self) -> int:
        """Return the content length in characters."""
        return len(self.content)

    def is_empty(self) -> bool:
        """Return True if the document has no content."""
        return not self.content.strip()

    @staticmethod
    def _validate_text(value: str, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} cannot be empty.")
        return value.strip()
