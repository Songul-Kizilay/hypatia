"""Unit tests for persistent user-authored comparison notes."""

from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import UTC, datetime

from core.Exceptions import ResearchError
from research.ResearchSourceComparisonNoteRecord import (
    ResearchSourceComparisonNoteRecord,
)


class ResearchSourceComparisonNoteRecordTests(unittest.TestCase):
    def setUp(self) -> None:
        self.record = ResearchSourceComparisonNoteRecord(
            note_id=" note-1 ",
            source_document_ids=(" document-1 ", "document-2"),
            evidence_ids=(" evidence-1 ", "evidence-2"),
            assessment_ids=(" assessment-1 ", "assessment-2"),
            text=" My comparison. ",
            recorded_at=datetime(2026, 8, 20, tzinfo=UTC),
        )

    def test_normalizes_authored_text_and_exact_ordered_references(self) -> None:
        self.assertEqual(self.record.note_id, "note-1")
        self.assertEqual(
            self.record.source_document_ids,
            ("document-1", "document-2"),
        )
        self.assertEqual(self.record.evidence_ids, ("evidence-1", "evidence-2"))
        self.assertEqual(
            self.record.assessment_ids,
            ("assessment-1", "assessment-2"),
        )
        self.assertEqual(self.record.text, "My comparison.")

    def test_rejects_incomplete_duplicate_or_oversized_values(self) -> None:
        invalid_changes = (
            {"note_id": " "},
            {"source_document_ids": ("document-1",)},
            {"source_document_ids": ("document-1", "document-1")},
            {"evidence_ids": ()},
            {"assessment_ids": ("assessment-1", "assessment-1")},
            {"text": "x" * 4_001},
            {"recorded_at": datetime(2026, 8, 20)},
        )
        for changes in invalid_changes:
            with self.subTest(changes=changes):
                with self.assertRaises(ResearchError):
                    replace(self.record, **changes)


if __name__ == "__main__":
    unittest.main()
