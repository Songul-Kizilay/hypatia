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

    def test_preserves_document_identity_for_later_result_citations(self) -> None:
        document = Document(
            title="Project Notes",
            content="One\n\nTwo",
            source="C:/knowledge/project-notes.md",
        )

        chunks = self.parser.parse(document)

        self.assertEqual(
            chunks[0].metadata,
            {
                "document_title": "Project Notes",
                "document_source": "C:/knowledge/project-notes.md",
                "document_type": "unknown",
            },
        )

    def test_ignores_extra_blank_lines(self) -> None:
        document = Document(title="Example", content="One\n\n\n\nTwo")

        chunks = self.parser.parse(document)

        self.assertEqual([chunk.content for chunk in chunks], ["One", "Two"])

    def test_stable_identity_is_repeatable_and_binds_position_and_content(
        self,
    ) -> None:
        document = Document(
            title="Accepted source",
            content="First\n\nSecond",
            document_id="accepted-document",
        )

        first = self.parser.parse(document, stable_chunk_ids=True)
        repeated = self.parser.parse(document, stable_chunk_ids=True)
        changed = self.parser.parse(
            Document(
                title=document.title,
                content="Changed\n\nSecond",
                document_id=document.document_id,
            ),
            stable_chunk_ids=True,
        )
        other_document = self.parser.parse(
            Document(
                title=document.title,
                content=document.content,
                document_id="other-accepted-document",
            ),
            stable_chunk_ids=True,
        )

        self.assertEqual(
            [chunk.chunk_id for chunk in first],
            [chunk.chunk_id for chunk in repeated],
        )
        self.assertNotEqual(first[0].chunk_id, changed[0].chunk_id)
        self.assertEqual(first[1].chunk_id, changed[1].chunk_id)
        self.assertNotEqual(first[0].chunk_id, first[1].chunk_id)
        self.assertNotEqual(first[0].chunk_id, other_document[0].chunk_id)

    def test_default_identity_remains_ephemeral(self) -> None:
        document = Document(
            title="Temporary source",
            content="One paragraph",
            document_id="temporary-document",
        )

        first = self.parser.parse(document)
        repeated = self.parser.parse(document)

        self.assertNotEqual(first[0].chunk_id, repeated[0].chunk_id)

    def test_rejects_nonboolean_stable_identity_option(self) -> None:
        document = Document(title="Example", content="Content")

        with self.assertRaisesRegex(KnowledgeError, "must be boolean"):
            self.parser.parse(document, stable_chunk_ids=1)  # type: ignore[arg-type]

    def test_rejects_empty_document_content(self) -> None:
        document = Document(title="Example", content="Content")
        document.content = "  "

        with self.assertRaises(KnowledgeError):
            self.parser.parse(document)
