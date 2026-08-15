"""End-to-end tests for KnowledgeEngine orchestration."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.Exceptions import KnowledgeError
from knowledge.DocumentLoader import DocumentLoader
from knowledge.Indexer import Indexer
from knowledge.JsonFileKnowledgeRelationStore import JsonFileKnowledgeRelationStore
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

    def test_reload_after_clear_preserves_a_file_source_document_id(self) -> None:
        path = self._write_file("example.md", "Hello\n\nHypatia")
        engine = KnowledgeEngine()
        first_document = engine.load(path)

        engine.clear()
        second_document = engine.load(path)

        self.assertEqual(first_document.document_id, second_document.document_id)

    def test_rejects_duplicate_local_source_without_partially_changing_state(
        self,
    ) -> None:
        path = self._write_file("example.md", "Hypatia\n\nKnowledge")
        engine = KnowledgeEngine()
        first_document = engine.load(path)
        counts_before = (
            engine.document_count(),
            engine.chunk_count(),
            engine.graph_node_count(),
            engine.graph_edge_count(),
        )
        search_ids_before = [chunk.chunk_id for chunk in engine.search("hypatia")]

        with self.assertRaisesRegex(
            KnowledgeError,
            "Knowledge document is already loaded.",
        ):
            engine.load(path)

        self.assertEqual(
            (
                engine.document_count(),
                engine.chunk_count(),
                engine.graph_node_count(),
                engine.graph_edge_count(),
            ),
            counts_before,
        )
        self.assertEqual(
            [chunk.chunk_id for chunk in engine.search("hypatia")],
            search_ids_before,
        )
        self.assertEqual(
            [reference.document_id for reference in engine.documents()],
            [first_document.document_id],
        )

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

    def test_apply_document_relation_changes_only_the_derived_graph(self) -> None:
        first = self._write_file("first.md", "First")
        second = self._write_file("second.md", "Second")
        engine = KnowledgeEngine()
        first_document = engine.load(first)
        second_document = engine.load(second)

        application = engine.apply_document_relation(
            first_document.document_id,
            second_document.document_id,
        )
        second_view = engine.graph_for_chunks(engine.search("second"))

        self.assertEqual(
            application.preview.source.document_id, first_document.document_id
        )
        self.assertEqual(
            application.preview.target.document_id, second_document.document_id
        )
        self.assertEqual(application.edge.relation, KnowledgeGraphRelation.RELATED_TO)
        self.assertEqual(engine.graph_edge_count(), 3)
        self.assertIn(application.edge, second_view.edges)
        with self.assertRaisesRegex(
            KnowledgeError, "Knowledge graph relation is already applied."
        ):
            engine.apply_document_relation(
                first_document.document_id,
                second_document.document_id,
            )

    def test_persisted_relation_restores_after_sources_reload_in_a_new_engine(
        self,
    ) -> None:
        first = self._write_file("first.md", "First")
        second = self._write_file("second.md", "Second")
        relation_path = self.directory / "relations.json"
        first_engine = KnowledgeEngine(
            relation_store=JsonFileKnowledgeRelationStore(relation_path)
        )
        first_document = first_engine.load(first)
        second_document = first_engine.load(second)

        application = first_engine.apply_document_relation(
            first_document.document_id,
            second_document.document_id,
        )
        second_engine = KnowledgeEngine(
            relation_store=JsonFileKnowledgeRelationStore(relation_path)
        )
        reloaded_first = second_engine.load(first)
        reloaded_second = second_engine.load(second)

        self.assertTrue(application.persisted)
        self.assertEqual(second_engine.persisted_relation_count(), 1)
        self.assertEqual(reloaded_first.document_id, first_document.document_id)
        self.assertEqual(reloaded_second.document_id, second_document.document_id)
        self.assertEqual(second_engine.graph_edge_count(), 3)

    def test_failed_relation_persistence_rolls_back_the_graph_change(self) -> None:
        first = self._write_file("first.md", "First")
        second = self._write_file("second.md", "Second")
        store = JsonFileKnowledgeRelationStore(self.directory / "relations.json")
        engine = KnowledgeEngine(relation_store=store)
        first_document = engine.load(first)
        second_document = engine.load(second)
        graph_edges_before = engine.graph_edge_count()

        with patch.object(store, "save", side_effect=KnowledgeError("write failed")):
            with self.assertRaisesRegex(KnowledgeError, "write failed"):
                engine.apply_document_relation(
                    first_document.document_id,
                    second_document.document_id,
                )

        self.assertEqual(engine.graph_edge_count(), graph_edges_before)
        self.assertEqual(engine.persisted_relation_count(), 0)

    def test_relation_removal_updates_graph_and_persisted_snapshot(self) -> None:
        first = self._write_file("first.md", "First")
        second = self._write_file("second.md", "Second")
        relation_path = self.directory / "relations.json"
        store = JsonFileKnowledgeRelationStore(relation_path)
        engine = KnowledgeEngine(relation_store=store)
        first_document = engine.load(first)
        second_document = engine.load(second)
        engine.apply_document_relation(
            first_document.document_id,
            second_document.document_id,
        )

        preview = engine.preview_document_relation_removal(
            first_document.document_id,
            second_document.document_id,
        )
        revocation = engine.remove_document_relation(
            first_document.document_id,
            second_document.document_id,
        )
        reloaded_engine = KnowledgeEngine(
            relation_store=JsonFileKnowledgeRelationStore(relation_path)
        )
        reloaded_engine.load(first)
        reloaded_engine.load(second)

        self.assertTrue(preview.persisted)
        self.assertTrue(revocation.preview.persisted)
        self.assertEqual(engine.graph_edge_count(), 2)
        self.assertEqual(engine.persisted_relation_count(), 0)
        self.assertEqual(store.load(), [])
        self.assertEqual(reloaded_engine.graph_edge_count(), 2)

    def test_relations_lists_only_active_relations_with_persistence_status(
        self,
    ) -> None:
        first = self._write_file("first.md", "First")
        second = self._write_file("second.md", "Second")
        engine = KnowledgeEngine(
            relation_store=JsonFileKnowledgeRelationStore(
                self.directory / "relations.json"
            )
        )
        first_document = engine.load(first)
        second_document = engine.load(second)

        self.assertEqual(engine.relations(), [])
        engine.apply_document_relation(
            first_document.document_id,
            second_document.document_id,
        )
        relations = engine.relations()

        self.assertEqual(len(relations), 1)
        self.assertEqual(relations[0].source.document_id, first_document.document_id)
        self.assertEqual(relations[0].target.document_id, second_document.document_id)
        self.assertEqual(relations[0].relation, KnowledgeGraphRelation.RELATED_TO)
        self.assertTrue(relations[0].persisted)

    def test_failed_relation_removal_persistence_restores_the_graph_edge(self) -> None:
        first = self._write_file("first.md", "First")
        second = self._write_file("second.md", "Second")
        store = JsonFileKnowledgeRelationStore(self.directory / "relations.json")
        engine = KnowledgeEngine(relation_store=store)
        first_document = engine.load(first)
        second_document = engine.load(second)
        engine.apply_document_relation(
            first_document.document_id,
            second_document.document_id,
        )

        with patch.object(store, "save", side_effect=KnowledgeError("write failed")):
            with self.assertRaisesRegex(KnowledgeError, "write failed"):
                engine.remove_document_relation(
                    first_document.document_id,
                    second_document.document_id,
                )

        self.assertEqual(engine.graph_edge_count(), 3)
        self.assertEqual(engine.persisted_relation_count(), 1)
        self.assertEqual(len(store.load()), 1)

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
