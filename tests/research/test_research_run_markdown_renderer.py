"""Deterministic, injection-safe rendering for persisted research exports."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchFailureRecord import ResearchFailureRecord
from research.ResearchInformationTrust import ResearchInformationTrust
from research.ResearchRun import ResearchRun
from research.ResearchRunMarkdownRenderer import render_research_run_markdown
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSourceAssessmentRecord import ResearchSourceAssessmentRecord
from research.ResearchSourceComparisonNoteRecord import (
    ResearchSourceComparisonNoteRecord,
)
from research.ResearchSourceRecord import ResearchSourceRecord


class ResearchRunMarkdownRendererTests(unittest.TestCase):
    def test_renders_persisted_audit_material_in_stable_source_order(self) -> None:
        run = self._completed_run()

        first = render_research_run_markdown(run)
        second = render_research_run_markdown(run)

        self.assertEqual(first, second)
        self.assertTrue(first.startswith("# Hypatia Research Export\n"))
        self.assertIn("- **Status:** completed", first)
        self.assertIn("> \\# user heading\n> second line", first)
        self.assertNotIn("\n# user heading\n", first)
        self.assertIn("### Source 1: Source \\[One\\]", first)
        self.assertLess(first.index("Source 1"), first.index("Source 2"))
        self.assertIn("- **Evidence ID:** evidence-1", first)
        self.assertIn("- **Audit state:** superseded", first)
        self.assertIn("- **Audit state:** current", first)
        self.assertIn("- **Supersedes:** assessment-1", first)
        self.assertIn(r"- **Data taint:** external\_untrusted\_data", first)
        self.assertIn("- **Instruction authority:** none", first)
        self.assertIn("- **Information trust:** low", first)
        self.assertIn("- **Information trust:** high", first)
        self.assertIn("- **Note ID:** note-1", first)
        self.assertIn("> \\# comparison heading", first)
        self.assertNotIn("<script>", first)
        self.assertNotIn("![remote]", first)
        self.assertNotIn("\u202e", first)
        self.assertIn(r"\<script\>alert\</script\>", first)
        self.assertIn(r"\!\[remote\](https://tracker.example/pixel)", first)
        self.assertIn("## Recorded Failures", first)
        self.assertIn("No network, provider, or LLM was used.", first)

    def test_renders_empty_terminal_run_without_inventing_material(self) -> None:
        now = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)
        run = ResearchRun(
            run_id="cancelled-run",
            question="No sources selected",
            status=ResearchRunStatus.CANCELLED,
            sources=(),
            failures=(),
            created_at=now,
            updated_at=now,
        )

        markdown = render_research_run_markdown(run)

        self.assertIn("_No accepted sources._", markdown)
        self.assertIn("_No comparison notes recorded._", markdown)
        self.assertIn("_No failures recorded._", markdown)

    @staticmethod
    def _completed_run() -> ResearchRun:
        started = datetime(2026, 8, 21, 10, 0, tzinfo=UTC)
        source_one = ResearchSourceRecord(
            document_id="document-1",
            url="https://example.com/one",
            title="Source [One]",
            content_type="text/plain",
            fetched_at=started,
            added_at=started + timedelta(minutes=1),
        )
        source_two = ResearchSourceRecord(
            document_id="document-2",
            url="https://example.com/two",
            title="Source Two",
            content_type="text/plain",
            fetched_at=started,
            added_at=started + timedelta(minutes=2),
        )
        evidence_one = ResearchEvidenceRecord(
            evidence_id="evidence-1",
            source_document_id="document-1",
            chunk_id="chunk-1",
            chunk_index=0,
            excerpt=(
                "<script>alert</script>\n"
                "![remote](https://tracker.example/pixel)\u202e"
            ),
            excerpt_truncated=False,
            chunk_sha256="a" * 64,
            note="# note heading\nnext",
            recorded_at=started + timedelta(minutes=3),
        )
        evidence_two = ResearchEvidenceRecord(
            evidence_id="evidence-2",
            source_document_id="document-2",
            chunk_id="chunk-2",
            chunk_index=1,
            excerpt="Second excerpt",
            excerpt_truncated=True,
            chunk_sha256="b" * 64,
            note="Second note",
            recorded_at=started + timedelta(minutes=4),
        )
        assessment_one = ResearchSourceAssessmentRecord(
            assessment_id="assessment-1",
            source_document_id="document-1",
            evidence_ids=("evidence-1",),
            text="Original assessment",
            recorded_at=started + timedelta(minutes=5),
            information_trust=ResearchInformationTrust.MEDIUM,
        )
        assessment_correction = ResearchSourceAssessmentRecord(
            assessment_id="assessment-1b",
            source_document_id="document-1",
            evidence_ids=("evidence-1",),
            text="Corrected assessment",
            recorded_at=started + timedelta(minutes=6),
            supersedes_assessment_id="assessment-1",
            information_trust=ResearchInformationTrust.LOW,
        )
        assessment_two = ResearchSourceAssessmentRecord(
            assessment_id="assessment-2",
            source_document_id="document-2",
            evidence_ids=("evidence-2",),
            text="Second assessment",
            recorded_at=started + timedelta(minutes=7),
            information_trust=ResearchInformationTrust.HIGH,
        )
        note = ResearchSourceComparisonNoteRecord(
            note_id="note-1",
            source_document_ids=("document-2", "document-1"),
            evidence_ids=("evidence-2", "evidence-1"),
            assessment_ids=("assessment-2", "assessment-1b"),
            text="# comparison heading",
            recorded_at=started + timedelta(minutes=8),
        )
        failure = ResearchFailureRecord(
            stage="fetch",
            reason="Safe failure reason",
            occurred_at=started + timedelta(minutes=9),
        )
        return ResearchRun(
            run_id="run-1",
            question="# user heading\nsecond line",
            status=ResearchRunStatus.COMPLETED,
            sources=(source_one, source_two),
            failures=(failure,),
            created_at=started,
            updated_at=started + timedelta(minutes=10),
            evidence=(evidence_one, evidence_two),
            assessments=(assessment_one, assessment_correction, assessment_two),
            comparison_notes=(note,),
        )


if __name__ == "__main__":
    unittest.main()
