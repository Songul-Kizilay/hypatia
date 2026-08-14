"""Tests for active local knowledge-relation catalog entries."""

from __future__ import annotations

import unittest

from core.Exceptions import KnowledgeError
from knowledge.Document import DocumentType
from knowledge.KnowledgeDocumentReference import KnowledgeDocumentReference
from knowledge.KnowledgeGraph import KnowledgeGraphRelation
from knowledge.KnowledgeRelationReference import KnowledgeRelationReference


class KnowledgeRelationReferenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = KnowledgeDocumentReference(
            "source", "Source", "source.md", DocumentType.MARKDOWN, 1
        )
        self.target = KnowledgeDocumentReference(
            "target", "Target", "target.md", DocumentType.MARKDOWN, 1
        )

    def test_accepts_an_active_persisted_related_to_reference(self) -> None:
        reference = KnowledgeRelationReference(
            self.source,
            KnowledgeGraphRelation.RELATED_TO,
            self.target,
            persisted=True,
        )

        self.assertTrue(reference.persisted)
        self.assertEqual(reference.relation, KnowledgeGraphRelation.RELATED_TO)

    def test_rejects_a_non_user_selectable_relation_reference(self) -> None:
        with self.assertRaisesRegex(
            KnowledgeError, "Knowledge relation type is not user-selectable."
        ):
            KnowledgeRelationReference(
                self.source,
                KnowledgeGraphRelation.CONTAINS,
                self.target,
                persisted=False,
            )
