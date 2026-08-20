"""Contracts for immutable accepted-source assessment previews."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from core.Exceptions import ResearchError
from knowledge.Chunk import Chunk
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSource import ResearchSource
from research.ResearchSourceAssessmentPreview import ResearchSourceAssessmentPreview
from research.ResearchSourceAssessmentRecord import ResearchSourceAssessmentRecord
from research.ResearchSourceRecord import ResearchSourceRecord


class ResearchSourceAssessmentPreviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 20, tzinfo=UTC)
        source = ResearchSource(
            "https://example.com/paper",
            "Paper",
            "Evidence.",
            "text/plain",
            self.now,
        )
        self.source = ResearchSourceRecord.from_source(source, "document-1", self.now)
        self.evidence = ResearchEvidenceRecord.from_chunk(
            "evidence-1",
            Chunk("document-1", 0, "Evidence.", chunk_id="chunk-1"),
            "Supports manual review.",
            self.now,
        )

    def test_preview_preserves_only_source_bound_evidence(self) -> None:
        preview = ResearchSourceAssessmentPreview(
            " run-1 ",
            ResearchRunStatus.COLLECTING,
            self.source,
            (self.evidence,),
            True,
            " Ready for manual review. ",
        )

        self.assertEqual(preview.run_id, "run-1")
        self.assertEqual(preview.evidence, (self.evidence,))
        self.assertTrue(preview.has_recorded_evidence)
        self.assertEqual(preview.reason, "Ready for manual review.")

    def test_preview_rejects_inconsistent_or_cross_source_evidence(self) -> None:
        other = ResearchEvidenceRecord.from_chunk(
            "evidence-2",
            Chunk("document-2", 0, "Other.", chunk_id="chunk-2"),
            "Other source.",
            self.now,
        )
        with self.assertRaisesRegex(ResearchError, "must belong"):
            ResearchSourceAssessmentPreview(
                "run-1",
                ResearchRunStatus.COLLECTING,
                self.source,
                (other,),
                True,
                "Invalid.",
            )
        with self.assertRaisesRegex(ResearchError, "inconsistent"):
            ResearchSourceAssessmentPreview(
                "run-1",
                ResearchRunStatus.COLLECTING,
                self.source,
                (self.evidence,),
                False,
                "Invalid.",
            )

    def test_preview_rejects_assessment_that_cites_undisplayed_evidence(self) -> None:
        assessment = ResearchSourceAssessmentRecord(
            "assessment-1",
            self.source.document_id,
            ("evidence-missing",),
            "Assessment.",
            self.now,
        )

        with self.assertRaisesRegex(ResearchError, "displayed evidence"):
            ResearchSourceAssessmentPreview(
                run_id="run-1",
                run_status=ResearchRunStatus.COLLECTING,
                source=self.source,
                evidence=(),
                has_recorded_evidence=False,
                reason="No evidence is available.",
                assessments=(assessment,),
            )


if __name__ == "__main__":
    unittest.main()
