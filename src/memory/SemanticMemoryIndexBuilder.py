"""Build a fresh derived semantic-memory index from active memory records."""

from __future__ import annotations

from collections.abc import Callable
from math import isfinite
from time import monotonic

from core.Exceptions import MemoryError
from memory.Embedding import Embedding
from memory.EmbeddingProvider import EmbeddingProvider, validate_embedding_source_text
from memory.InMemorySemanticMemoryIndex import (
    MAX_SEMANTIC_MEMORY_INDEX_ENTRIES,
    InMemorySemanticMemoryIndex,
    validate_semantic_memory_index_population,
)
from memory.MemoryManager import MemoryManager
from memory.MemoryRecord import MemoryRecord
from memory.SemanticEmbeddingCache import SemanticEmbeddingCache

DEFAULT_SEMANTIC_REBUILD_PROVIDER_CALLS = 256
MAX_SEMANTIC_REBUILD_PROVIDER_CALLS = MAX_SEMANTIC_MEMORY_INDEX_ENTRIES
DEFAULT_SEMANTIC_REBUILD_TIMEOUT_SECONDS = 120.0
MAX_SEMANTIC_REBUILD_TIMEOUT_SECONDS = 3_600.0


class SemanticMemoryIndexBuilder:
    """Create replacement indexes without mutating persistence or runtime state."""

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        embedding_cache: SemanticEmbeddingCache | None = None,
        *,
        max_rebuild_provider_calls: int = DEFAULT_SEMANTIC_REBUILD_PROVIDER_CALLS,
        max_rebuild_seconds: float = DEFAULT_SEMANTIC_REBUILD_TIMEOUT_SECONDS,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if (
            isinstance(max_rebuild_provider_calls, bool)
            or not isinstance(max_rebuild_provider_calls, int)
            or max_rebuild_provider_calls < 0
            or max_rebuild_provider_calls > MAX_SEMANTIC_REBUILD_PROVIDER_CALLS
        ):
            raise ValueError(
                "Semantic rebuild provider-call budget must be an integer "
                f"between 0 and {MAX_SEMANTIC_REBUILD_PROVIDER_CALLS:,}."
            )
        if (
            isinstance(max_rebuild_seconds, bool)
            or not isinstance(max_rebuild_seconds, (int, float))
            or not isfinite(max_rebuild_seconds)
            or max_rebuild_seconds <= 0
            or max_rebuild_seconds > MAX_SEMANTIC_REBUILD_TIMEOUT_SECONDS
        ):
            raise ValueError(
                "Semantic rebuild timeout must be a positive number no greater "
                f"than {MAX_SEMANTIC_REBUILD_TIMEOUT_SECONDS:g}."
            )
        self._embedding_provider = embedding_provider
        self._embedding_cache = embedding_cache
        self._max_rebuild_provider_calls = max_rebuild_provider_calls
        self._max_rebuild_seconds = float(max_rebuild_seconds)
        self._clock = clock

    def build(self, memory_manager: MemoryManager) -> InMemorySemanticMemoryIndex:
        """Embed current active records into a new index in memory-record order."""
        deadline = self._clock() + self._max_rebuild_seconds
        records = memory_manager.all()
        validate_semantic_memory_index_population(len(records))
        for record in records:
            self._validate_source_text(record.content)
        cached_embeddings = self._cached_embeddings(records)
        self._ensure_rebuild_time_available(deadline)
        provider_call_count = sum(embedding is None for embedding in cached_embeddings)
        if provider_call_count > self._max_rebuild_provider_calls:
            raise MemoryError("Semantic index rebuild provider-call budget exceeded.")

        index = InMemorySemanticMemoryIndex()
        cache_entries: list[tuple[str, str, Embedding]] = []
        for record, cached_embedding in zip(
            records,
            cached_embeddings,
            strict=True,
        ):
            self._ensure_rebuild_time_available(deadline)
            embedding = cached_embedding
            if embedding is None:
                embedding = self._embedding_provider.embed(
                    record.content,
                    timeout_seconds=self._remaining_rebuild_seconds(deadline),
                )
                self._ensure_rebuild_time_available(deadline)
            if not cache_entries:
                validate_semantic_memory_index_population(
                    len(records),
                    embedding.dimension,
                )
            index.upsert(record.memory_id, embedding)
            cache_entries.append((record.memory_id, record.content, embedding))
        self._ensure_rebuild_time_available(deadline)
        self._replace_cache(tuple(cache_entries))
        return index

    def _remaining_rebuild_seconds(self, deadline: float) -> float:
        remaining = deadline - self._clock()
        if remaining <= 0:
            raise MemoryError("Semantic index rebuild time budget exceeded.")
        return remaining

    def _ensure_rebuild_time_available(self, deadline: float) -> None:
        if self._clock() > deadline:
            raise MemoryError("Semantic index rebuild time budget exceeded.")

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

    def _cached_embeddings(
        self,
        records: list[MemoryRecord],
    ) -> tuple[Embedding | None, ...]:
        if self._embedding_cache is None:
            return (None,) * len(records)
        cached_embeddings: list[Embedding | None] = []
        try:
            for record in records:
                embedding = self._embedding_cache.get(
                    record.memory_id,
                    record.content,
                )
                if embedding is not None and not isinstance(embedding, Embedding):
                    raise TypeError(
                        "Semantic embedding cache returned an invalid value."
                    )
                cached_embeddings.append(embedding)
        except Exception:
            return (None,) * len(records)
        return tuple(cached_embeddings)

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
