"""Unit tests for the Document model."""

from __future__ import annotations

import unittest

from knowledge.Document import Document, DocumentType


class DocumentTests(unittest.TestCase):
    def test_initializes_common_document_fields(self) -> None:
        document = Document(
            title=" Notes ",
            content=" Hypatia facts ",
            source="notes.md",
            document_type=DocumentType.MARKDOWN,
            metadata={"author": "Songul"},
        )

        self.assertEqual(document.title, "Notes")
        self.assertEqual(document.content, "Hypatia facts")
        self.assertEqual(document.document_type, DocumentType.MARKDOWN)
        self.assertEqual(document.metadata, {"author": "Songul"})
        self.assertEqual(document.size(), len("Hypatia facts"))
        self.assertFalse(document.is_empty())

    def test_rejects_blank_title(self) -> None:
        with self.assertRaises(ValueError):
            Document(title=" ", content="Content")

    def test_rejects_blank_content(self) -> None:
        with self.assertRaises(ValueError):
            Document(title="Title", content=" ")

    def test_update_content_refreshes_timestamp(self) -> None:
        document = Document(title="Title", content="Old content")
        created_at = document.updated_at

        document.update_content(" New content ")

        self.assertEqual(document.content, "New content")
        self.assertGreaterEqual(document.updated_at, created_at)
