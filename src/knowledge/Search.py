"""Plain-text search over the in-memory knowledge index."""

from __future__ import annotations

from core.Exceptions import KnowledgeError
from knowledge.Chunk import Chunk
from knowledge.Indexer import Indexer


class Search:
    """Finds chunks whose content contains a requested text fragment."""

    def __init__(self, indexer: Indexer) -> None:
        self._indexer = indexer

    def find(self, query: str | None) -> list[Chunk]:
        """Return matching chunks in their index insertion order."""
        normalized_query = self._validate_query(query)
        return [
            chunk
            for chunk in self._indexer.all().values()
            if normalized_query in chunk.content.casefold()
        ]

    def find_first(self, query: str | None) -> Chunk | None:
        """Return the first matching chunk, or None when no match exists."""
        results = self.find(query)
        return results[0] if results else None

    def exists(self, query: str | None) -> bool:
        """Return whether at least one chunk matches the query."""
        return self.find_first(query) is not None

    @staticmethod
    def _validate_query(query: str | None) -> str:
        if not isinstance(query, str) or not query.strip():
            raise KnowledgeError("Search query cannot be empty.")
        return query.casefold().strip()
