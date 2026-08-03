"""Unit tests for DocumentLoader."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.Exceptions import KnowledgeError
from knowledge.Document import DocumentType
from knowledge.DocumentLoader import DocumentLoader


class DocumentLoaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.loader = DocumentLoader()
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_loads_text_file(self) -> None:
        path = self._write_file("ideas.txt", "Hypatia ideas")

        document = self.loader.load(path)

        self.assertEqual(document.title, "ideas")
        self.assertEqual(document.content, "Hypatia ideas")
        self.assertEqual(document.document_type, DocumentType.TEXT)

    def test_loads_markdown_file(self) -> None:
        path = self._write_file("notes.md", "# Notes")

        document = self.loader.load(path)

        self.assertEqual(document.title, "notes")
        self.assertEqual(document.document_type, DocumentType.MARKDOWN)

    def test_preserves_source_path(self) -> None:
        path = self._write_file("source.txt", "Content")

        document = self.loader.load(path)

        self.assertEqual(document.source, str(path))

    def test_rejects_missing_file(self) -> None:
        with self.assertRaises(KnowledgeError):
            self.loader.load(self.directory / "missing.txt")

    def test_rejects_unsupported_extension(self) -> None:
        path = self._write_file("document.pdf", "Not a real PDF")

        with self.assertRaises(KnowledgeError):
            self.loader.load(path)

    def test_rejects_empty_file(self) -> None:
        path = self._write_file("empty.md", "  \n")

        with self.assertRaises(KnowledgeError):
            self.loader.load(path)

    def _write_file(self, name: str, content: str) -> Path:
        path = self.directory / name
        path.write_text(content, encoding="utf-8")
        return path
