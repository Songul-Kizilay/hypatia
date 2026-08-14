"""Tests for the local knowledge-document catalog read model."""

from __future__ import annotations

import unittest
from typing import Any

from core.Exceptions import KnowledgeError
from knowledge.Document import DocumentType
from knowledge.KnowledgeDocumentReference import KnowledgeDocumentReference


class KnowledgeDocumentReferenceTests(unittest.TestCase):
    def test_normalizes_stable_catalog_fields(self) -> None:
        reference = KnowledgeDocumentReference(
            document_id=" document-1 ",
            title=" Notes ",
            source=" notes.md ",
            document_type=DocumentType.MARKDOWN,
            chunk_count=2,
        )

        self.assertEqual(reference.document_id, "document-1")
        self.assertEqual(reference.title, "Notes")
        self.assertEqual(reference.source, "notes.md")
        self.assertEqual(reference.chunk_count, 2)

    def test_rejects_invalid_document_catalog_values(self) -> None:
        base: dict[str, Any] = {
            "document_id": "document-1",
            "title": "Notes",
            "source": "notes.md",
            "document_type": DocumentType.MARKDOWN,
            "chunk_count": 1,
        }
        for field, value in (
            ("document_id", " "),
            ("title", " "),
            ("source", None),
            ("document_type", "markdown"),
            ("chunk_count", -1),
            ("chunk_count", True),
        ):
            with self.subTest(field=field, value=value):
                with self.assertRaises(KnowledgeError):
                    KnowledgeDocumentReference(**(base | {field: value}))
