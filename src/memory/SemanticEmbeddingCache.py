"""Optional local cache boundary for derived semantic embeddings."""

from __future__ import annotations

from typing import Protocol

from memory.Embedding import Embedding


class SemanticEmbeddingCache(Protocol):
    """Reuse validated embeddings only when their source content still matches."""

    def get(self, memory_id: str, source_text: str) -> Embedding | None:
        """Return a cached embedding for the exact current memory content."""

    def replace(
        self,
        entries: tuple[tuple[str, str, Embedding], ...],
    ) -> None:
        """Atomically replace cached entries after a complete index rebuild."""

    def upsert(self, memory_id: str, source_text: str, embedding: Embedding) -> None:
        """Store one derived embedding after a successful primary-memory write."""

    def remove(self, memory_id: str) -> None:
        """Remove one cached embedding after its source memory is removed."""
