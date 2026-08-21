"""Derived, deterministic in-memory index for semantic memory vectors."""

from __future__ import annotations

from math import fsum, sqrt

from memory.Embedding import MAX_EMBEDDING_DIMENSION, Embedding
from memory.SemanticMemoryMatch import SemanticMemoryMatch

MAX_SEMANTIC_MEMORY_INDEX_ENTRIES = 20_000
MAX_SEMANTIC_MEMORY_INDEX_MEMORY_ID_CHARACTERS = 1_024
MAX_SEMANTIC_MEMORY_INDEX_VALUES = 4_000_000


def validate_semantic_memory_index_population(
    entry_count: int,
    dimension: int | None = None,
) -> None:
    """Reject a prospective live index before retaining excessive vectors."""
    if entry_count > MAX_SEMANTIC_MEMORY_INDEX_ENTRIES:
        raise ValueError("Semantic memory index has too many entries.")
    if (
        dimension is not None
        and entry_count * dimension > MAX_SEMANTIC_MEMORY_INDEX_VALUES
    ):
        raise ValueError("Semantic memory index has too many embedding values.")


class InMemorySemanticMemoryIndex:
    """Index embeddings by existing memory ID without persisting vectors."""

    def __init__(self, dimension: int | None = None) -> None:
        if dimension is not None and (
            isinstance(dimension, bool)
            or not isinstance(dimension, int)
            or dimension < 1
            or dimension > MAX_EMBEDDING_DIMENSION
        ):
            raise ValueError(
                "Semantic memory index dimension must be a supported positive "
                "integer."
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
        prospective_count = len(self._embeddings) + (
            0 if memory_id in self._embeddings else 1
        )
        validate_semantic_memory_index_population(
            prospective_count,
            embedding.dimension,
        )
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

        query_scale, query_scaled_norm = self._scaled_norm(query)
        if query_scale == 0.0:
            return ()

        matches_list: list[SemanticMemoryMatch] = []
        for memory_id, embedding in self._embeddings.items():
            embedding_scale, embedding_scaled_norm = self._scaled_norm(embedding)
            if embedding_scale == 0.0:
                continue
            matches_list.append(
                SemanticMemoryMatch(
                    memory_id=memory_id,
                    score=self._cosine_similarity(
                        query,
                        embedding,
                        query_scale,
                        query_scaled_norm,
                        embedding_scale,
                        embedding_scaled_norm,
                    ),
                )
            )
        matches = tuple(matches_list)
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
        if len(memory_id) > MAX_SEMANTIC_MEMORY_INDEX_MEMORY_ID_CHARACTERS:
            raise ValueError("Semantic memory index memory ID is too long.")

    @staticmethod
    def _validate_limit(limit: int | None) -> None:
        if limit is None:
            return
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
            raise ValueError(
                "Semantic memory search limit must be a non-negative integer."
            )

    @staticmethod
    def _scaled_norm(embedding: Embedding) -> tuple[float, float]:
        scale = max(abs(value) for value in embedding.values)
        if scale == 0.0:
            return 0.0, 0.0
        return scale, sqrt(fsum((value / scale) ** 2 for value in embedding.values))

    def _cosine_similarity(
        self,
        query: Embedding,
        embedding: Embedding,
        query_scale: float,
        query_scaled_norm: float,
        embedding_scale: float,
        embedding_scaled_norm: float,
    ) -> float:
        score = fsum(
            (query_value / query_scale / query_scaled_norm)
            * (embedding_value / embedding_scale / embedding_scaled_norm)
            for query_value, embedding_value in zip(
                query.values, embedding.values, strict=True
            )
        )
        return max(-1.0, min(1.0, score))
