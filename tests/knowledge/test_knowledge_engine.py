"""End-to-end tests for KnowledgeEngine orchestration."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from knowledge.DocumentLoader import DocumentLoader
from knowledge.Indexer import Indexer
from knowledge.KnowledgeEngine import KnowledgeEngine
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
        self.assertEqual(engine.search("hypatia"), [])

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
