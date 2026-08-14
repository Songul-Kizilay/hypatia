"""Orchestration layer for the Knowledge Foundation pipeline."""

from __future__ import annotations

from pathlib import Path

from knowledge.Chunk import Chunk
from knowledge.Document import Document
from knowledge.DocumentLoader import DocumentLoader
from knowledge.Indexer import Indexer
from knowledge.KnowledgeDocumentReference import KnowledgeDocumentReference
from knowledge.KnowledgeGraph import KnowledgeGraph, KnowledgeGraphView
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
        graph: KnowledgeGraph | None = None,
    ) -> None:
        self._loader = loader or DocumentLoader()
        self._parser = parser or Parser()
        self._indexer = indexer or Indexer()
        self._search_engine = search or Search(self._indexer)
        self._graph = graph or KnowledgeGraph()
        self._documents: dict[str, Document] = {}

    def load(self, path: str | Path) -> Document:
        """Load a document, parse it into chunks, and add them to the index."""
        document = self._loader.load(path)
        chunks = self._parser.parse(document)

        for chunk in chunks:
            self._indexer.add(chunk)

        self._graph.index_document(document, chunks)
        self._documents[document.document_id] = document
        return document

    def search(self, query: str | None) -> list[Chunk]:
        """Find indexed chunks matching a query."""
        return self._search_engine.find(query)

    def clear(self) -> None:
        """Clear every indexed chunk and loaded document reference."""
        self._indexer.clear()
        self._graph.clear()
        self._documents.clear()

    def graph_for_chunks(self, chunks: list[Chunk]) -> KnowledgeGraphView:
        """Return the derived structural graph for indexed search results."""
        return self._graph.view_for_chunks(chunks)

    def documents(self) -> list[KnowledgeDocumentReference]:
        """List loaded source documents in deterministic load order."""
        indexed_chunks = tuple(self._indexer.all().values())
        return [
            KnowledgeDocumentReference(
                document_id=document.document_id,
                title=document.title,
                source=document.source,
                document_type=document.document_type,
                chunk_count=sum(
                    chunk.document_id == document.document_id
                    for chunk in indexed_chunks
                ),
            )
            for document in self._documents.values()
        ]

    def document_count(self) -> int:
        """Return the number of loaded documents."""
        return len(self._documents)

    def chunk_count(self) -> int:
        """Return the number of indexed chunks."""
        return self._indexer.count()

    def graph_node_count(self) -> int:
        """Return the count of derived local knowledge-graph nodes."""
        return self._graph.node_count()

    def graph_edge_count(self) -> int:
        """Return the count of derived local knowledge-graph edges."""
        return self._graph.edge_count()
