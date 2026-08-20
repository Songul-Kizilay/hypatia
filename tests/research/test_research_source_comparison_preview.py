"""Contracts for immutable manual multi-source comparison previews."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from core.Exceptions import ResearchError
from knowledge.Chunk import Chunk
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSource import ResearchSource
from research.ResearchSourceAssessmentRecord import ResearchSourceAssessmentRecord
from research.ResearchSourceComparisonItem import (
    MAX_COMPARISON_ASSESSMENTS_PER_SOURCE,
    MAX_COMPARISON_EVIDENCE_PER_SOURCE,
    ResearchSourceComparisonItem,
)
from research.ResearchSourceComparisonPreview import ResearchSourceComparisonPreview
from research.ResearchSourceRecord import ResearchSourceRecord


class ResearchSourceComparisonPreviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 20, tzinfo=UTC)

    def _item(self, number: int) -> ResearchSourceComparisonItem:
        document_id = f"document-{number}"
        source = ResearchSourceRecord.from_source(
            ResearchSource(
                f"https://example.com/{number}",
                f"Source {number}",
                f"Evidence {number}.",
                "text/plain",
                self.now,
            ),
            document_id,
            self.now,
        )
        evidence = ResearchEvidenceRecord.from_chunk(
            f"evidence-{number}",
            Chunk(
                document_id,
                0,
                f"Evidence {number}.",
                chunk_id=f"chunk-{number}",
            ),
            f"Note {number}.",
            self.now,
        )
        assessment = ResearchSourceAssessmentRecord(
            f"assessment-{number}",
            document_id,
            (evidence.evidence_id,),
            f"Assessment {number}.",
            self.now,
        )
        return ResearchSourceComparisonItem(source, (evidence,), (assessment,))

    def test_preview_preserves_explicit_source_order_and_material(self) -> None:
        second = self._item(2)
        first = self._item(1)

        preview = ResearchSourceComparisonPreview(
            " run-1 ",
            " Compare evidence. ",
            ResearchRunStatus.COLLECTING,
            (second, first),
            " Manual review only. ",
        )

        self.assertEqual(preview.run_id, "run-1")
        self.assertEqual(preview.question, "Compare evidence.")
        self.assertEqual(preview.sources, (second, first))
        self.assertEqual(preview.reason, "Manual review only.")

    def test_preview_rejects_wrong_count_or_duplicate_sources(self) -> None:
        first = self._item(1)
        with self.assertRaisesRegex(ResearchError, "2 to 5"):
            ResearchSourceComparisonPreview(
                "run-1",
                "Question",
                ResearchRunStatus.COLLECTING,
                (first,),
                "Invalid.",
            )
        with self.assertRaisesRegex(ResearchError, "duplicate"):
            ResearchSourceComparisonPreview(
                "run-1",
                "Question",
                ResearchRunStatus.COLLECTING,
                (first, first),
                "Invalid.",
            )

    def test_item_rejects_cross_source_material(self) -> None:
        first = self._item(1)
        second = self._item(2)
        with self.assertRaisesRegex(ResearchError, "evidence must belong"):
            ResearchSourceComparisonItem(
                first.source,
                second.evidence,
                first.current_assessments,
            )
        with self.assertRaisesRegex(ResearchError, "assessments must belong"):
            ResearchSourceComparisonItem(
                first.source,
                first.evidence,
                second.current_assessments,
            )

    def test_item_reports_omissions_and_enforces_display_bounds(self) -> None:
        first = self._item(1)
        item = ResearchSourceComparisonItem(
            first.source,
            first.evidence,
            first.current_assessments,
            omitted_evidence_count=3,
            omitted_current_assessment_count=2,
        )

        self.assertEqual(item.total_evidence_count, 4)
        self.assertEqual(item.total_current_assessment_count, 3)

        with self.assertRaisesRegex(ResearchError, "cannot be negative"):
            ResearchSourceComparisonItem(
                first.source,
                first.evidence,
                first.current_assessments,
                omitted_evidence_count=-1,
            )
        with self.assertRaisesRegex(ResearchError, "too many evidence"):
            ResearchSourceComparisonItem(
                first.source,
                first.evidence * (MAX_COMPARISON_EVIDENCE_PER_SOURCE + 1),
                first.current_assessments,
            )
        with self.assertRaisesRegex(ResearchError, "too many current"):
            ResearchSourceComparisonItem(
                first.source,
                first.evidence,
                first.current_assessments * (MAX_COMPARISON_ASSESSMENTS_PER_SOURCE + 1),
            )


if __name__ == "__main__":
    unittest.main()
