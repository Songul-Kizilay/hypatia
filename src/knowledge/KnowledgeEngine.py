"""Orchestration layer for the Knowledge Foundation pipeline."""

from __future__ import annotations

from pathlib import Path

from knowledge.Chunk import Chunk
from knowledge.Document import Document
from knowledge.DocumentLoader import DocumentLoader
from knowledge.Indexer import Indexer
from knowledge.Parser import Parser
from knowledge.Search import Search


class KnowledgeEngine:
    """Coordinates loading, parsing, indexing, and searching knowledge."""

    def __init__(
        self,
        loader: DocumentLoader | None = None,
        parser: Parser | None = None,
        indexer: Indexer | None = None,
        search: Search | None = None,
    ) -> None:
        self._loader = loader or DocumentLoader()
        self._parser = parser or Parser()
        self._indexer = indexer or Indexer()
        self._search_engine = search or Search(self._indexer)
        self._documents: dict[str, Document] = {}

    def load(self, path: str | Path) -> Document:
        """Load a document, parse it into chunks, and add them to the index."""
        document = self._loader.load(path)
        chunks = self._parser.parse(document)

        for chunk in chunks:
            self._indexer.add(chunk)

        self._documents[document.document_id] = document
        return document

    def search(self, query: str | None) -> list[Chunk]:
        """Find indexed chunks matching a query."""
        return self._search_engine.find(query)

    def clear(self) -> None:
        """Clear every indexed chunk and loaded document reference."""
        self._indexer.clear()
        self._documents.clear()

    def document_count(self) -> int:
        """Return the number of loaded documents."""
        return len(self._documents)

    def chunk_count(self) -> int:
        """Return the number of indexed chunks."""
        return self._indexer.count()
