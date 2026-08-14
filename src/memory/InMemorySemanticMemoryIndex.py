"""Derived, deterministic in-memory index for semantic memory vectors."""

from __future__ import annotations

from math import sqrt

from memory.Embedding import Embedding
from memory.SemanticMemoryMatch import SemanticMemoryMatch


class InMemorySemanticMemoryIndex:
    """Index embeddings by existing memory ID without persisting vectors."""

    def __init__(self, dimension: int | None = None) -> None:
        if dimension is not None and (
            isinstance(dimension, bool)
            or not isinstance(dimension, int)
            or dimension < 1
        ):
            raise ValueError(
                "Semantic memory index dimension must be a positive integer."
            )
        self._dimension = dimension
        self._embeddings: dict[str, Embedding] = {}

    @property
    def dimension(self) -> int | None:
        """Return the fixed dimension, or None until the first indexed embedding."""
        return self._dimension

    def count(self) -> int:
        """Return the number of indexed memory IDs."""
        return len(self._embeddings)

    def upsert(self, memory_id: str, embedding: Embedding) -> None:
        """Insert or replace one memory embedding."""
        self._validate_memory_id(memory_id)
        self._validate_embedding(embedding)
        if self._dimension is None:
            self._dimension = embedding.dimension
        self._embeddings[memory_id] = embedding

    def remove(self, memory_id: str) -> bool:
        """Remove one indexed memory ID and report whether it existed."""
        self._validate_memory_id(memory_id)
        return self._embeddings.pop(memory_id, None) is not None

    def search(
        self,
        query: Embedding,
        *,
        limit: int | None = None,
    ) -> tuple[SemanticMemoryMatch, ...]:
        """Rank indexed non-zero vectors by cosine similarity and memory ID."""
        self._validate_embedding(query)
        self._validate_limit(limit)
        if limit == 0 or not self._embeddings:
            return ()

        query_norm = self._norm(query)
        if query_norm == 0.0:
            return ()

        matches = tuple(
            SemanticMemoryMatch(
                memory_id=memory_id,
                score=self._cosine_similarity(query, embedding, query_norm),
            )
            for memory_id, embedding in self._embeddings.items()
            if self._norm(embedding) != 0.0
        )
        ranked_matches = tuple(
            sorted(matches, key=lambda match: (-match.score, match.memory_id))
        )
        return ranked_matches if limit is None else ranked_matches[:limit]

    def _validate_embedding(self, embedding: Embedding) -> None:
        if not isinstance(embedding, Embedding):
            raise ValueError("Semantic memory index requires an Embedding.")
        if self._dimension is not None and embedding.dimension != self._dimension:
            raise ValueError(
                "Embedding dimension does not match semantic memory index dimension."
            )

    @staticmethod
    def _validate_memory_id(memory_id: str) -> None:
        if (
            not isinstance(memory_id, str)
            or not memory_id
            or memory_id != memory_id.strip()
        ):
            raise ValueError("Semantic memory index requires a non-empty memory ID.")

    @staticmethod
    def _validate_limit(limit: int | None) -> None:
        if limit is None:
            return
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
            raise ValueError(
                "Semantic memory search limit must be a non-negative integer."
            )

    @staticmethod
    def _norm(embedding: Embedding) -> float:
        return sqrt(sum(value * value for value in embedding.values))

    def _cosine_similarity(
        self,
        query: Embedding,
        embedding: Embedding,
        query_norm: float,
    ) -> float:
        embedding_norm = self._norm(embedding)
        return sum(
            query_value * embedding_value
            for query_value, embedding_value in zip(
                query.values, embedding.values, strict=True
            )
        ) / (query_norm * embedding_norm)
