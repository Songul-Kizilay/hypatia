"""Unit tests for the paragraph Parser."""

from __future__ import annotations

import unittest

from core.Exceptions import KnowledgeError
from knowledge.Chunk import ChunkType
from knowledge.Document import Document
from knowledge.Parser import Parser


class ParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = Parser()

    def test_splits_document_into_paragraph_chunks(self) -> None:
        document = Document(title="Example", content="Hello\n\nWorld\n\nHypatia")

        chunks = self.parser.parse(document)

        self.assertEqual(
            [chunk.content for chunk in chunks], ["Hello", "World", "Hypatia"]
        )
        self.assertEqual([chunk.index for chunk in chunks], [0, 1, 2])

    def test_assigns_document_id_to_every_chunk(self) -> None:
        document = Document(title="Example", content="One\n\nTwo")

        chunks = self.parser.parse(document)

        self.assertTrue(
            all(chunk.document_id == document.document_id for chunk in chunks)
        )

    def test_marks_chunks_as_paragraphs(self) -> None:
        document = Document(title="Example", content="One\n\nTwo")

        chunks = self.parser.parse(document)

        self.assertTrue(
            all(chunk.chunk_type is ChunkType.PARAGRAPH for chunk in chunks)
        )

    def test_ignores_extra_blank_lines(self) -> None:
        document = Document(title="Example", content="One\n\n\n\nTwo")

        chunks = self.parser.parse(document)

        self.assertEqual([chunk.content for chunk in chunks], ["One", "Two"])

    def test_rejects_empty_document_content(self) -> None:
        document = Document(title="Example", content="Content")
        document.content = "  "

        with self.assertRaises(KnowledgeError):
            self.parser.parse(document)
