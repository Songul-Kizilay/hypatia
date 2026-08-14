"""Stable source attribution for one retrieved local knowledge chunk."""

from __future__ import annotations

from dataclasses import dataclass

from knowledge.Chunk import Chunk


@dataclass(frozen=True, slots=True)
class KnowledgeCitation:
    """Identifies the local source and paragraph represented by one result."""

    document_id: str
    document_title: str
    source: str
    chunk_index: int
    chunk_id: str

    @classmethod
    def from_chunk(cls, chunk: Chunk) -> KnowledgeCitation:
        """Create an attribution without requiring a second document lookup."""
        return cls(
            document_id=chunk.document_id,
            document_title=_metadata_text(chunk, "document_title", "(untitled)"),
            source=_metadata_text(chunk, "document_source", ""),
            chunk_index=chunk.index,
            chunk_id=chunk.chunk_id,
        )


def _metadata_text(chunk: Chunk, key: str, fallback: str) -> str:
    value = chunk.metadata.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else fallback
