"""Tests for traceable research-source conversion."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from knowledge.Document import DocumentType
from research.ResearchSource import ResearchSource


class ResearchSourceTests(unittest.TestCase):
    def test_converts_to_a_stable_web_document_with_provenance(self) -> None:
        fetched_at = datetime(2026, 8, 20, 12, 30, tzinfo=UTC)
        source = ResearchSource(
            url="https://example.com/research",
            title="Example research",
            content="Evidence paragraph.",
            content_type="text/html",
            fetched_at=fetched_at,
        )

        first = source.to_document()
        second = source.to_document()

        self.assertEqual(first.document_id, second.document_id)
        self.assertEqual(first.document_type, DocumentType.WEB)
        self.assertEqual(first.source, source.url)
        self.assertEqual(first.created_at, fetched_at)
        self.assertEqual(first.metadata["acquisition"], "explicit_https")
        self.assertEqual(first.metadata["fetched_at"], "2026-08-20T12:30:00+00:00")


if __name__ == "__main__":
    unittest.main()
