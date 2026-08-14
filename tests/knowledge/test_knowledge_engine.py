"""End-to-end tests for KnowledgeEngine orchestration."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.Exceptions import KnowledgeError
from knowledge.DocumentLoader import DocumentLoader
from knowledge.Indexer import Indexer
from knowledge.KnowledgeEngine import KnowledgeEngine
from knowledge.KnowledgeGraph import KnowledgeGraphRelation
from knowledge.Parser import Parser
from knowledge.Search import Search


class KnowledgeEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_load_runs_the_full_pipeline(self) -> None:
        path = self._write_file("example.md", "Hello\n\nWorld\n\nHypatia")
        engine = KnowledgeEngine()

        document = engine.load(path)

        self.assertEqual(document.title, "example")
        self.assertEqual(engine.document_count(), 1)
        self.assertEqual(engine.chunk_count(), 3)
        self.assertEqual(engine.graph_node_count(), 4)
        self.assertEqual(engine.graph_edge_count(), 5)

    def test_search_returns_indexed_chunk(self) -> None:
        path = self._write_file("example.md", "Hello\n\nHypatia")
        engine = KnowledgeEngine()
        engine.load(path)

        results = engine.search("hypatia")

        self.assertEqual([chunk.content for chunk in results], ["Hypatia"])

    def test_clear_removes_documents_and_chunks(self) -> None:
        path = self._write_file("example.md", "Hello\n\nHypatia")
        engine = KnowledgeEngine()
        engine.load(path)

        engine.clear()

        self.assertEqual(engine.document_count(), 0)
        self.assertEqual(engine.chunk_count(), 0)
        self.assertEqual(engine.graph_node_count(), 0)
        self.assertEqual(engine.graph_edge_count(), 0)
        self.assertEqual(engine.search("hypatia"), [])

    def test_graph_for_search_results_exposes_containing_document_relationships(
        self,
    ) -> None:
        path = self._write_file("example.md", "Hello\n\nHypatia")
        engine = KnowledgeEngine()
        engine.load(path)

        view = engine.graph_for_chunks(engine.search("hypatia"))

        self.assertEqual(len(view.nodes), 2)
        self.assertEqual(len(view.edges), 1)
        self.assertEqual(view.edges[0].relation, KnowledgeGraphRelation.CONTAINS)

    def test_documents_lists_stable_local_source_references_in_load_order(
        self,
    ) -> None:
        first = self._write_file("first.md", "First\n\nHypatia")
        second = self._write_file("second.txt", "Second")
        engine = KnowledgeEngine()
        first_document = engine.load(first)
        second_document = engine.load(second)

        references = engine.documents()

        self.assertEqual(
            [reference.document_id for reference in references],
            [first_document.document_id, second_document.document_id],
        )
        self.assertEqual(
            [reference.title for reference in references], ["first", "second"]
        )
        self.assertEqual([reference.chunk_count for reference in references], [2, 1])

    def test_preview_document_relation_validates_distinct_loaded_documents(
        self,
    ) -> None:
        first = self._write_file("first.md", "First")
        second = self._write_file("second.txt", "Second")
        engine = KnowledgeEngine()
        first_document = engine.load(first)
        second_document = engine.load(second)

        preview = engine.preview_document_relation(
            first_document.document_id,
            second_document.document_id,
        )

        self.assertEqual(preview.source.document_id, first_document.document_id)
        self.assertEqual(preview.relation, KnowledgeGraphRelation.RELATED_TO)
        self.assertEqual(preview.target.document_id, second_document.document_id)
        self.assertEqual(engine.graph_node_count(), 4)
        self.assertEqual(engine.graph_edge_count(), 2)

    def test_preview_document_relation_rejects_unknown_and_self_document_ids(
        self,
    ) -> None:
        engine = KnowledgeEngine()
        document = engine.load(self._write_file("only.md", "Only"))

        with self.assertRaisesRegex(
            KnowledgeError,
            "Knowledge document was not found: missing",
        ):
            engine.preview_document_relation("missing", "other")
        with self.assertRaisesRegex(
            KnowledgeError,
            "Knowledge relation source and target must differ.",
        ):
            engine.preview_document_relation(
                document.document_id,
                document.document_id,
            )

    def test_loads_multiple_documents(self) -> None:
        first = self._write_file("first.md", "First\n\nHypatia")
        second = self._write_file("second.txt", "Second\n\nKnowledge")
        engine = KnowledgeEngine()

        engine.load(first)
        engine.load(second)

        self.assertEqual(engine.document_count(), 2)
        self.assertEqual(engine.chunk_count(), 4)

    def test_accepts_injected_pipeline_dependencies(self) -> None:
        indexer = Indexer()
        engine = KnowledgeEngine(
            loader=DocumentLoader(),
            parser=Parser(),
            indexer=indexer,
            search=Search(indexer),
        )
        path = self._write_file("example.md", "Hypatia")

        engine.load(path)

        self.assertEqual(indexer.count(), 1)

    def _write_file(self, name: str, content: str) -> Path:
        path = self.directory / name
        path.write_text(content, encoding="utf-8")
        return path
