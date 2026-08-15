"""Orchestration layer for the Knowledge Foundation pipeline."""

from __future__ import annotations

from pathlib import Path

from core.Exceptions import KnowledgeError
from knowledge.Chunk import Chunk
from knowledge.Document import Document
from knowledge.DocumentLoader import DocumentLoader
from knowledge.Indexer import Indexer
from knowledge.JsonFileKnowledgeRelationStore import JsonFileKnowledgeRelationStore
from knowledge.KnowledgeDocumentReference import KnowledgeDocumentReference
from knowledge.KnowledgeGraph import (
    KnowledgeGraph,
    KnowledgeGraphRelation,
    KnowledgeGraphView,
)
from knowledge.KnowledgeRelationApplication import KnowledgeRelationApplication
from knowledge.KnowledgeRelationPreview import KnowledgeRelationPreview
from knowledge.KnowledgeRelationRecord import KnowledgeRelationRecord
from knowledge.KnowledgeRelationReference import KnowledgeRelationReference
from knowledge.KnowledgeRelationRevocation import KnowledgeRelationRevocation
from knowledge.KnowledgeRelationRevocationPreview import (
    KnowledgeRelationRevocationPreview,
)
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
        relation_store: JsonFileKnowledgeRelationStore | None = None,
    ) -> None:
        self._loader = loader or DocumentLoader()
        self._parser = parser or Parser()
        self._indexer = indexer or Indexer()
        self._search_engine = search or Search(self._indexer)
        self._graph = graph or KnowledgeGraph()
        self._documents: dict[str, Document] = {}
        self._relation_store = relation_store
        self._persisted_relations = (
            relation_store.load() if relation_store is not None else []
        )

    def load(self, path: str | Path) -> Document:
        """Load a document, parse it into chunks, and add them to the index."""
        document = self._loader.load(path)
        if document.document_id in self._documents:
            raise KnowledgeError("Knowledge document is already loaded.")
        chunks = self._parser.parse(document)

        for chunk in chunks:
            self._indexer.add(chunk)

        self._graph.index_document(document, chunks)
        self._documents[document.document_id] = document
        self._restore_persisted_relations_for(document.document_id)
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
            self._document_reference(document, indexed_chunks)
            for document in self._documents.values()
        ]

    def relations(self) -> list[KnowledgeRelationReference]:
        """List active explicit relations in deterministic graph insertion order."""
        indexed_chunks = tuple(self._indexer.all().values())
        references: list[KnowledgeRelationReference] = []
        for edge in self._graph.document_relations():
            source_document_id = self._document_id_from_node_id(edge.source_node_id)
            target_document_id = self._document_id_from_node_id(edge.target_node_id)
            source = self._document_by_id(source_document_id)
            target = self._document_by_id(target_document_id)
            record = KnowledgeRelationRecord(
                source.document_id,
                edge.relation,
                target.document_id,
            )
            references.append(
                KnowledgeRelationReference(
                    source=self._document_reference(source, indexed_chunks),
                    relation=edge.relation,
                    target=self._document_reference(target, indexed_chunks),
                    persisted=record in self._persisted_relations,
                )
            )
        return references

    def preview_document_relation(
        self,
        source_document_id: str,
        target_document_id: str,
    ) -> KnowledgeRelationPreview:
        """Validate a manual document relation without changing graph state."""
        source = self._document_by_id(source_document_id)
        target = self._document_by_id(target_document_id)
        indexed_chunks = tuple(self._indexer.all().values())
        return KnowledgeRelationPreview(
            source=self._document_reference(source, indexed_chunks),
            relation=KnowledgeGraphRelation.RELATED_TO,
            target=self._document_reference(target, indexed_chunks),
        )

    def apply_document_relation(
        self,
        source_document_id: str,
        target_document_id: str,
    ) -> KnowledgeRelationApplication:
        """Apply one explicitly requested relation after fresh validation."""
        preview = self.preview_document_relation(source_document_id, target_document_id)
        record = KnowledgeRelationRecord(
            preview.source.document_id,
            preview.relation,
            preview.target.document_id,
        )
        if record in self._persisted_relations or self._graph.has_document_relation(
            record.source_document_id,
            record.relation,
            record.target_document_id,
        ):
            raise KnowledgeError("Knowledge graph relation is already applied.")
        edge = self._graph.add_document_relation(
            record.source_document_id,
            record.relation,
            record.target_document_id,
        )
        if self._relation_store is not None:
            try:
                self._relation_store.save([*self._persisted_relations, record])
            except KnowledgeError:
                self._graph.remove_document_relation(edge)
                raise
            self._persisted_relations.append(record)
        return KnowledgeRelationApplication(
            preview, edge, persisted=self._relation_store is not None
        )

    def preview_document_relation_removal(
        self,
        source_document_id: str,
        target_document_id: str,
    ) -> KnowledgeRelationRevocationPreview:
        """Validate a requested relation removal without changing graph state."""
        relation = self.preview_document_relation(
            source_document_id, target_document_id
        )
        if not self._graph.has_document_relation(
            relation.source.document_id,
            relation.relation,
            relation.target.document_id,
        ):
            raise KnowledgeError("Knowledge graph relation is not applied.")
        record = KnowledgeRelationRecord(
            relation.source.document_id,
            relation.relation,
            relation.target.document_id,
        )
        return KnowledgeRelationRevocationPreview(
            relation=relation,
            persisted=record in self._persisted_relations,
        )

    def remove_document_relation(
        self,
        source_document_id: str,
        target_document_id: str,
    ) -> KnowledgeRelationRevocation:
        """Remove one explicit relationship with a persistence rollback boundary."""
        preview = self.preview_document_relation_removal(
            source_document_id, target_document_id
        )
        relation = preview.relation
        edge = self._graph.document_relation(
            relation.source.document_id,
            relation.relation,
            relation.target.document_id,
        )
        if edge is None:
            raise KnowledgeError("Knowledge graph relation is not applied.")

        record = KnowledgeRelationRecord(
            relation.source.document_id,
            relation.relation,
            relation.target.document_id,
        )
        remaining_records = [
            candidate for candidate in self._persisted_relations if candidate != record
        ]
        self._graph.remove_document_relation(edge)
        if self._relation_store is not None and preview.persisted:
            try:
                self._relation_store.save(remaining_records)
            except KnowledgeError:
                self._graph.add_document_relation(
                    relation.source.document_id,
                    relation.relation,
                    relation.target.document_id,
                )
                raise
            self._persisted_relations = remaining_records
        return KnowledgeRelationRevocation(preview, edge)

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

    def persisted_relation_count(self) -> int:
        """Return the count of explicit relationships kept in the local store."""
        return len(self._persisted_relations)

    def _restore_persisted_relations_for(self, document_id: str) -> None:
        for record in self._persisted_relations:
            if document_id not in {
                record.source_document_id,
                record.target_document_id,
            } or (
                record.source_document_id not in self._documents
                or record.target_document_id not in self._documents
            ):
                continue
            if not self._graph.has_document_relation(
                record.source_document_id,
                record.relation,
                record.target_document_id,
            ):
                self._graph.add_document_relation(
                    record.source_document_id,
                    record.relation,
                    record.target_document_id,
                )

    def _document_by_id(self, document_id: str) -> Document:
        if not isinstance(document_id, str) or not document_id.strip():
            raise KnowledgeError("Knowledge document ID cannot be empty.")
        normalized_id = document_id.strip()
        document = self._documents.get(normalized_id)
        if document is None:
            raise KnowledgeError(f"Knowledge document was not found: {normalized_id}")
        return document

    @staticmethod
    def _document_id_from_node_id(node_id: str) -> str:
        prefix = "document:"
        if not node_id.startswith(prefix):
            raise KnowledgeError("Knowledge graph relation has an invalid endpoint.")
        return node_id[len(prefix) :]

    @staticmethod
    def _document_reference(
        document: Document,
        indexed_chunks: tuple[Chunk, ...],
    ) -> KnowledgeDocumentReference:
        return KnowledgeDocumentReference(
            document_id=document.document_id,
            title=document.title,
            source=document.source,
            document_type=document.document_type,
            chunk_count=sum(
                chunk.document_id == document.document_id for chunk in indexed_chunks
            ),
        )
