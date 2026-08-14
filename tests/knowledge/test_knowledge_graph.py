"""Tests for the deterministic local knowledge-graph foundation."""

from __future__ import annotations

import unittest

from core.Exceptions import KnowledgeError
from knowledge.Chunk import Chunk
from knowledge.Document import Document, DocumentType
from knowledge.KnowledgeGraph import (
    KnowledgeGraph,
    KnowledgeGraphNodeKind,
    KnowledgeGraphRelation,
)


class KnowledgeGraphTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = Document(
            document_id="document-1",
            title="Research Notes",
            content="First\n\nSecond",
            source="notes.md",
            document_type=DocumentType.MARKDOWN,
        )
        self.first = Chunk(
            chunk_id="chunk-1",
            document_id=self.document.document_id,
            index=0,
            content="First",
        )
        self.second = Chunk(
            chunk_id="chunk-2",
            document_id=self.document.document_id,
            index=1,
            content="Second",
        )
        self.graph = KnowledgeGraph()

    def test_indexes_document_chunk_and_order_relationships(self) -> None:
        self.graph.index_document(self.document, [self.first, self.second])

        self.assertEqual(self.graph.node_count(), 3)
        self.assertEqual(self.graph.edge_count(), 3)

        view = self.graph.view_for_chunks([self.second])

        self.assertEqual(
            [(node.kind, node.label) for node in view.nodes],
            [
                (KnowledgeGraphNodeKind.DOCUMENT, "Research Notes"),
                (KnowledgeGraphNodeKind.CHUNK, "Paragraph 2"),
            ],
        )
        self.assertEqual(
            view.edges[0].relation,
            KnowledgeGraphRelation.CONTAINS,
        )
        self.assertEqual(
            view.edges[0].source_node_id,
            KnowledgeGraph.document_node_id("document-1"),
        )
        self.assertEqual(
            view.edges[0].target_node_id,
            KnowledgeGraph.chunk_node_id("chunk-2"),
        )

    def test_graph_view_keeps_selected_chunk_order_and_deduplicates_edges(self) -> None:
        self.graph.index_document(self.document, [self.first, self.second])

        view = self.graph.view_for_chunks([self.second, self.first, self.second])

        self.assertEqual(
            [edge.target_node_id for edge in view.edges],
            [
                KnowledgeGraph.chunk_node_id("chunk-2"),
                KnowledgeGraph.chunk_node_id("chunk-1"),
            ],
        )

    def test_adds_explicit_document_relation_and_exposes_it_from_either_endpoint(
        self,
    ) -> None:
        related_document = Document(
            document_id="document-2",
            title="Related Notes",
            content="Related",
            source="related.md",
            document_type=DocumentType.MARKDOWN,
        )
        related_chunk = Chunk(
            chunk_id="chunk-related",
            document_id=related_document.document_id,
            index=0,
            content="Related",
        )
        self.graph.index_document(self.document, [self.first, self.second])
        self.graph.index_document(related_document, [related_chunk])

        edge = self.graph.add_document_relation(
            self.document.document_id,
            KnowledgeGraphRelation.RELATED_TO,
            related_document.document_id,
        )
        view = self.graph.view_for_chunks([related_chunk])

        self.assertEqual(edge.relation, KnowledgeGraphRelation.RELATED_TO)
        self.assertIn(edge, view.edges)
        self.assertEqual(
            [node.label for node in view.nodes],
            ["Related Notes", "Paragraph 1", "Research Notes"],
        )

    def test_rejects_duplicate_or_nonselectable_document_relation(self) -> None:
        related_document = Document(
            document_id="document-2",
            title="Related Notes",
            content="Related",
            source="related.md",
            document_type=DocumentType.MARKDOWN,
        )
        related_chunk = Chunk(
            chunk_id="chunk-related",
            document_id=related_document.document_id,
            index=0,
            content="Related",
        )
        self.graph.index_document(self.document, [self.first, self.second])
        self.graph.index_document(related_document, [related_chunk])
        self.graph.add_document_relation(
            self.document.document_id,
            KnowledgeGraphRelation.RELATED_TO,
            related_document.document_id,
        )

        with self.assertRaisesRegex(
            KnowledgeError, "Knowledge graph relation is already applied."
        ):
            self.graph.add_document_relation(
                self.document.document_id,
                KnowledgeGraphRelation.RELATED_TO,
                related_document.document_id,
            )
        with self.assertRaisesRegex(
            KnowledgeError, "Knowledge graph relation is not user-selectable."
        ):
            self.graph.add_document_relation(
                self.document.document_id,
                KnowledgeGraphRelation.CONTAINS,
                related_document.document_id,
            )

    def test_rejects_chunk_from_another_document(self) -> None:
        foreign_chunk = Chunk(
            chunk_id="foreign",
            document_id="other-document",
            index=0,
            content="Foreign",
        )

        with self.assertRaisesRegex(
            KnowledgeError,
            "Knowledge graph chunks must belong to their document.",
        ):
            self.graph.index_document(self.document, [foreign_chunk])

        self.assertEqual(self.graph.node_count(), 0)
        self.assertEqual(self.graph.edge_count(), 0)

    def test_rejects_duplicate_chunk_ids_without_partially_changing_the_graph(
        self,
    ) -> None:
        duplicate = Chunk(
            chunk_id=self.first.chunk_id,
            document_id=self.document.document_id,
            index=1,
            content="Duplicate",
        )

        with self.assertRaisesRegex(
            KnowledgeError,
            "Knowledge graph node is already indexed: chunk:chunk-1",
        ):
            self.graph.index_document(self.document, [self.first, duplicate])

        self.assertEqual(self.graph.node_count(), 0)
        self.assertEqual(self.graph.edge_count(), 0)

    def test_rejects_a_graph_view_for_an_unindexed_chunk(self) -> None:
        with self.assertRaisesRegex(
            KnowledgeError,
            "Knowledge graph chunk was not found: chunk-1",
        ):
            self.graph.view_for_chunks([self.first])

    def test_clear_removes_derived_graph_state_only(self) -> None:
        self.graph.index_document(self.document, [self.first, self.second])

        self.graph.clear()

        self.assertEqual(self.graph.node_count(), 0)
        self.assertEqual(self.graph.edge_count(), 0)
