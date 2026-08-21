"""Build a fresh derived semantic-memory index from active memory records."""

from __future__ import annotations

from core.Exceptions import MemoryError
from memory.Embedding import Embedding
from memory.EmbeddingProvider import EmbeddingProvider, validate_embedding_source_text
from memory.InMemorySemanticMemoryIndex import (
    InMemorySemanticMemoryIndex,
    validate_semantic_memory_index_population,
)
from memory.MemoryManager import MemoryManager
from memory.SemanticEmbeddingCache import SemanticEmbeddingCache


class SemanticMemoryIndexBuilder:
    """Create replacement indexes without mutating persistence or runtime state."""

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        embedding_cache: SemanticEmbeddingCache | None = None,
    ) -> None:
        self._embedding_provider = embedding_provider
        self._embedding_cache = embedding_cache

    def build(self, memory_manager: MemoryManager) -> InMemorySemanticMemoryIndex:
        """Embed current active records into a new index in memory-record order."""
        records = memory_manager.all()
        validate_semantic_memory_index_population(len(records))
        for record in records:
            self._validate_source_text(record.content)
        index = InMemorySemanticMemoryIndex()
        cache_entries: list[tuple[str, str, Embedding]] = []
        for record in records:
            embedding = self._cached_embedding(record.memory_id, record.content)
            if embedding is None:
                embedding = self._embedding_provider.embed(record.content)
            if not cache_entries:
                validate_semantic_memory_index_population(
                    len(records),
                    embedding.dimension,
                )
            index.upsert(record.memory_id, embedding)
            cache_entries.append((record.memory_id, record.content, embedding))
        self._replace_cache(tuple(cache_entries))
        return index

    def embed(self, source_text: str) -> Embedding:
        """Create one query embedding through the configured provider."""
        self._validate_source_text(source_text)
        return self._embedding_provider.embed(source_text)

    def upsert_memory_record(
        self,
        index: InMemorySemanticMemoryIndex,
        memory_id: str,
        source_text: str,
    ) -> None:
        """Update the live index before best-effort cache retention."""
        self._validate_source_text(source_text)
        embedding = self._embedding_provider.embed(source_text)
        index.upsert(memory_id, embedding)
        if self._embedding_cache is not None:
            try:
                self._embedding_cache.upsert(memory_id, source_text, embedding)
            except Exception:
                pass

    def remove_memory_record(self, memory_id: str) -> None:
        """Best-effort remove a stale entry from the optional derived cache."""
        if self._embedding_cache is not None:
            try:
                self._embedding_cache.remove(memory_id)
            except Exception:
                pass

    def _cached_embedding(self, memory_id: str, source_text: str) -> Embedding | None:
        if self._embedding_cache is None:
            return None
        try:
            return self._embedding_cache.get(memory_id, source_text)
        except Exception:
            return None

    def _replace_cache(
        self,
        entries: tuple[tuple[str, str, Embedding], ...],
    ) -> None:
        if self._embedding_cache is not None:
            try:
                self._embedding_cache.replace(entries)
            except Exception:
                pass

    @staticmethod
    def _validate_source_text(source_text: object) -> None:
        try:
            validate_embedding_source_text(source_text)
        except ValueError as error:
            raise MemoryError("Embedding source text invalid.") from error
