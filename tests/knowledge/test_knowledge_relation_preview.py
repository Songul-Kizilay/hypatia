"""Tests for the manual knowledge-document relation preview model."""

from __future__ import annotations

import unittest

from core.Exceptions import KnowledgeError
from knowledge.Document import DocumentType
from knowledge.KnowledgeDocumentReference import KnowledgeDocumentReference
from knowledge.KnowledgeGraph import KnowledgeGraphRelation
from knowledge.KnowledgeRelationPreview import KnowledgeRelationPreview


class KnowledgeRelationPreviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = KnowledgeDocumentReference(
            "source", "Source", "source.md", DocumentType.MARKDOWN, 1
        )
        self.target = KnowledgeDocumentReference(
            "target", "Target", "target.md", DocumentType.MARKDOWN, 1
        )

    def test_accepts_the_first_explicit_document_relation(self) -> None:
        preview = KnowledgeRelationPreview(
            self.source,
            KnowledgeGraphRelation.RELATED_TO,
            self.target,
        )

        self.assertIs(preview.source, self.source)
        self.assertEqual(preview.relation, KnowledgeGraphRelation.RELATED_TO)
        self.assertIs(preview.target, self.target)

    def test_rejects_self_relation_and_derived_relation_types(self) -> None:
        with self.assertRaisesRegex(
            KnowledgeError,
            "Knowledge relation source and target must differ.",
        ):
            KnowledgeRelationPreview(
                self.source,
                KnowledgeGraphRelation.RELATED_TO,
                self.source,
            )
        with self.assertRaisesRegex(
            KnowledgeError,
            "Knowledge relation type is not user-selectable.",
        ):
            KnowledgeRelationPreview(
                self.source,
                KnowledgeGraphRelation.CONTAINS,
                self.target,
            )
