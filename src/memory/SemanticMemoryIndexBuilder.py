"""Build a fresh derived semantic-memory index from active memory records."""

from __future__ import annotations

from memory.Embedding import Embedding
from memory.EmbeddingProvider import EmbeddingProvider
from memory.InMemorySemanticMemoryIndex import InMemorySemanticMemoryIndex
from memory.MemoryManager import MemoryManager


class SemanticMemoryIndexBuilder:
    """Create replacement indexes without mutating persistence or runtime state."""

    def __init__(self, embedding_provider: EmbeddingProvider) -> None:
        self._embedding_provider = embedding_provider

    def build(self, memory_manager: MemoryManager) -> InMemorySemanticMemoryIndex:
        """Embed current active records into a new index in memory-record order."""
        index = InMemorySemanticMemoryIndex()
        for record in memory_manager.all():
            index.upsert(
                record.memory_id,
                self._embedding_provider.embed(record.content),
            )
        return index

    def embed(self, source_text: str) -> Embedding:
        """Create one query embedding through the configured provider."""
        return self._embedding_provider.embed(source_text)
