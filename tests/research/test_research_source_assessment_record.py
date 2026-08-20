"""Contracts for user-authored persisted source assessments."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from core.Exceptions import ResearchError
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSourceAssessmentRecord import ResearchSourceAssessmentRecord
from research.ResearchSourceAssessmentWritePreview import (
    ResearchSourceAssessmentWritePreview,
)
from research.ResearchSourceRecord import ResearchSourceRecord


class ResearchSourceAssessmentRecordTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 20, 20, 0, tzinfo=UTC)
        self.source = ResearchSourceRecord(
            "document-1",
            "https://example.com/source",
            "Source",
            "text/plain",
            self.now,
            self.now,
        )
        self.evidence = ResearchEvidenceRecord(
            "evidence-1",
            "document-1",
            "chunk-1",
            0,
            "Evidence.",
            False,
            "a" * 64,
            "Relevant.",
            self.now,
        )

    def test_record_normalizes_explicit_evidence_and_text(self) -> None:
        record = ResearchSourceAssessmentRecord(
            " assessment-1 ",
            " document-1 ",
            (" evidence-1 ",),
            "  The source supports the claim.  ",
            self.now,
        )

        self.assertEqual(record.assessment_id, "assessment-1")
        self.assertEqual(record.source_document_id, "document-1")
        self.assertEqual(record.evidence_ids, ("evidence-1",))
        self.assertEqual(record.text, "The source supports the claim.")

    def test_record_requires_unique_explicit_evidence_and_bounded_text(self) -> None:
        for evidence_ids, text in (
            ((), "Assessment."),
            (("evidence-1", " evidence-1 "), "Assessment."),
            (("evidence-1",), "x" * 2_001),
        ):
            with self.subTest(evidence_ids=evidence_ids, text_length=len(text)):
                with self.assertRaises(ResearchError):
                    ResearchSourceAssessmentRecord(
                        "assessment-1",
                        "document-1",
                        evidence_ids,
                        text,
                        self.now,
                    )

    def test_record_normalizes_optional_supersession_and_rejects_self_link(
        self,
    ) -> None:
        record = ResearchSourceAssessmentRecord(
            "assessment-2",
            "document-1",
            ("evidence-1",),
            "Corrected assessment.",
            self.now,
            " assessment-1 ",
        )

        self.assertEqual(record.supersedes_assessment_id, "assessment-1")

        with self.assertRaisesRegex(ResearchError, "cannot supersede itself"):
            ResearchSourceAssessmentRecord(
                "assessment-1",
                "document-1",
                ("evidence-1",),
                "Invalid self correction.",
                self.now,
                "assessment-1",
            )

    def test_write_preview_rejects_cross_source_evidence(self) -> None:
        other = ResearchEvidenceRecord(
            "evidence-2",
            "document-2",
            "chunk-2",
            0,
            "Other.",
            False,
            "b" * 64,
            "Other.",
            self.now,
        )

        with self.assertRaisesRegex(ResearchError, "belong to its source"):
            ResearchSourceAssessmentWritePreview(
                "run-1",
                ResearchRunStatus.COLLECTING,
                self.source,
                (other,),
                "Assessment.",
                True,
                "Allowed.",
            )

    def test_write_preview_requires_superseded_assessment_from_same_source(
        self,
    ) -> None:
        other_assessment = ResearchSourceAssessmentRecord(
            "assessment-1",
            "document-2",
            ("evidence-2",),
            "Other assessment.",
            self.now,
        )

        with self.assertRaisesRegex(ResearchError, "belong to its source"):
            ResearchSourceAssessmentWritePreview(
                run_id="run-1",
                run_status=ResearchRunStatus.COLLECTING,
                source=self.source,
                evidence=(self.evidence,),
                text="Corrected assessment.",
                allowed=True,
                reason="Allowed.",
                supersedes_assessment=other_assessment,
            )


if __name__ == "__main__":
    unittest.main()
