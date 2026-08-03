"""Chunk model for source content prepared for later indexing."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class ChunkType(StrEnum):
    """Supported semantic chunk categories."""

    TEXT = "text"
    PARAGRAPH = "paragraph"
    SENTENCE = "sentence"
    TABLE = "table"
    CODE = "code"
    QUOTE = "quote"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class Chunk:
    """Represents one ordered segment of a source document."""

    document_id: str
    index: int
    content: str
    chunk_type: ChunkType = ChunkType.UNKNOWN
    metadata: dict[str, Any] = field(default_factory=dict)
    chunk_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self.document_id = self._validate_text(self.document_id, "Document ID")
        self.content = self._validate_text(self.content, "Chunk content")

    def update_content(self, content: str) -> None:
        """Replace the chunk content and refresh its update timestamp."""
        self.content = self._validate_text(content, "Chunk content")
        self.updated_at = datetime.now(UTC)

    def size(self) -> int:
        """Return the character count of this chunk's content."""
        return len(self.content)

    def is_empty(self) -> bool:
        """Return whether the chunk content has no visible characters."""
        return not self.content.strip()

    @staticmethod
    def _validate_text(value: str, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} cannot be empty.")
        return value.strip()
