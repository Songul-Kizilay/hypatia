"""Tests for the explicit relation-removal result models."""

from __future__ import annotations

import unittest

from core.Exceptions import KnowledgeError
from knowledge.Document import DocumentType
from knowledge.KnowledgeDocumentReference import KnowledgeDocumentReference
from knowledge.KnowledgeGraph import KnowledgeGraphEdge, KnowledgeGraphRelation
from knowledge.KnowledgeRelationPreview import KnowledgeRelationPreview
from knowledge.KnowledgeRelationRevocation import KnowledgeRelationRevocation
from knowledge.KnowledgeRelationRevocationPreview import (
    KnowledgeRelationRevocationPreview,
)


class KnowledgeRelationRevocationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = KnowledgeDocumentReference(
            "source", "Source", "source.md", DocumentType.MARKDOWN, 1
        )
        self.target = KnowledgeDocumentReference(
            "target", "Target", "target.md", DocumentType.MARKDOWN, 1
        )
        self.relation = KnowledgeRelationPreview(
            self.source, KnowledgeGraphRelation.RELATED_TO, self.target
        )

    def test_accepts_a_matching_explicit_relation_removal(self) -> None:
        preview = KnowledgeRelationRevocationPreview(self.relation, persisted=True)

        result = KnowledgeRelationRevocation(
            preview,
            KnowledgeGraphEdge(
                "document:source", KnowledgeGraphRelation.RELATED_TO, "document:target"
            ),
        )

        self.assertIs(result.preview, preview)
        self.assertEqual(result.edge.relation, KnowledgeGraphRelation.RELATED_TO)

    def test_rejects_a_removal_result_that_does_not_match_the_preview(self) -> None:
        preview = KnowledgeRelationRevocationPreview(self.relation, persisted=False)

        with self.assertRaisesRegex(
            KnowledgeError, "Knowledge relation removal result does not match preview."
        ):
            KnowledgeRelationRevocation(
                preview,
                KnowledgeGraphEdge(
                    "document:target",
                    KnowledgeGraphRelation.RELATED_TO,
                    "document:source",
                ),
            )
