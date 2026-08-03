"""In-memory chunk index for the Knowledge Foundation."""

from __future__ import annotations

from collections.abc import Iterable

from core.Exceptions import KnowledgeError
from knowledge.Chunk import Chunk


class Indexer:
    """Maintains a unique chunk ID to Chunk mapping in memory."""

    def __init__(self) -> None:
        self._index: dict[str, Chunk] = {}

    def index(self, chunks: Iterable[Chunk]) -> dict[str, Chunk]:
        """Replace the current index with the supplied chunks."""
        indexed_chunks: dict[str, Chunk] = {}

        for chunk in chunks:
            if not isinstance(chunk, Chunk):
                raise KnowledgeError("Indexer accepts only Chunk instances.")
            if chunk.chunk_id in indexed_chunks:
                raise KnowledgeError(f"Chunk is already indexed: {chunk.chunk_id}")
            indexed_chunks[chunk.chunk_id] = chunk

        self._index = indexed_chunks
        return self.all()

    def add(self, chunk: Chunk) -> None:
        """Add a chunk to the index."""
        if not isinstance(chunk, Chunk):
            raise KnowledgeError("Indexer accepts only Chunk instances.")
        if self.contains(chunk.chunk_id):
            raise KnowledgeError(f"Chunk is already indexed: {chunk.chunk_id}")

        self._index[chunk.chunk_id] = chunk

    def remove(self, chunk_id: str) -> Chunk:
        """Remove and return a chunk by ID."""
        if not self.contains(chunk_id):
            raise KnowledgeError(f"Chunk was not found: {chunk_id}")

        return self._index.pop(chunk_id)

    def get(self, chunk_id: str) -> Chunk:
        """Return a chunk by ID."""
        if not self.contains(chunk_id):
            raise KnowledgeError(f"Chunk was not found: {chunk_id}")

        return self._index[chunk_id]

    def contains(self, chunk_id: str) -> bool:
        """Return whether a chunk ID exists in the index."""
        return chunk_id in self._index

    def count(self) -> int:
        """Return the number of indexed chunks."""
        return len(self._index)

    def clear(self) -> None:
        """Remove every chunk from the index."""
        self._index.clear()

    def all(self) -> dict[str, Chunk]:
        """Return a shallow copy of all indexed chunks."""
        return dict(self._index)
