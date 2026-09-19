"""Deterministic, injection-safe rendering for persisted research exports."""

from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from research.ResearchClaimConfidence import ResearchClaimConfidence
from research.ResearchClaimContradictionRecord import (
    ResearchClaimContradictionRecord,
)
from research.ResearchClaimRecord import ResearchClaimRecord
from research.ResearchComparisonReviewRecord import (
    ResearchComparisonReviewDecision,
    ResearchComparisonReviewRecord,
)
from research.ResearchEpistemicState import ResearchEpistemicState
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
from research.ResearchSourceIndependence import ResearchSourceIndependence
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
        self.assertIn("- **Observation ID:** unrecorded", first)
        self.assertIn("- **Document/content version ID:** document-1", first)
        # Sources built without a recorded observation say so, not guess one.
        self.assertIn(
            "- **Observed content SHA-256:** unrecorded (accepted before content "
            "versioning)",
            first,
        )
        versioned = render_research_run_markdown(
            replace(
                run,
                sources=(
                    replace(run.sources[0], content_sha256="c" * 64),
                    *run.sources[1:],
                ),
            )
        )
        self.assertIn(f"- **Observed content SHA-256:** `{'c' * 64}`", versioned)
        observed = render_research_run_markdown(
            replace(
                run,
                sources=(
                    replace(run.sources[0], observation_id="obs-1"),
                    *run.sources[1:],
                ),
            )
        )
        self.assertIn("- **Observation ID:** obs-1", observed)
        self.assertIn("- **Information trust:** low", first)
        self.assertIn("- **Information trust:** high", first)
        self.assertIn("## Evidence-linked Claims", first)
        self.assertIn("- **Epistemic state:** hypothesis", first)
        self.assertIn("- **Epistemic state:** contradicted", first)
        self.assertIn("- **Authored confidence:** high", first)
        self.assertIn("- **Supersedes:** claim-1", first)
        self.assertIn("## User-reviewed Claim Contradictions", first)
        self.assertIn("- **Contradiction ID:** contradiction-1", first)
        self.assertIn("- **Claim IDs:** claim-1, claim-2", first)
        self.assertIn(r"> \# contradiction note", first)
        self.assertIn("- **Note ID:** note-1", first)
        self.assertIn("> \\# comparison heading", first)
        self.assertNotIn("<script>", first)
        self.assertNotIn("![remote]", first)
        self.assertNotIn("\u202e", first)
        self.assertIn(r"\<script\>alert\</script\>", first)
        self.assertIn(r"\!\[remote\](https://tracker.example/pixel)", first)
        self.assertIn("- **Comparison reviews:** 2", first)
        self.assertIn("## Operator Comparison Reviews", first)
        self.assertIn("not model output or a factual-truth decision", first)
        self.assertIn("- **Review ID:** review-1", first)
        self.assertIn("- **Decision:** supported", first)
        self.assertIn("- **Decision:** not_supported", first)
        self.assertIn("- **Supersedes:** review-1", first)
        self.assertIn("- **Evidence IDs:** evidence-2, evidence-1", first)
        self.assertIn(r"> \# withdrawn after rereading", first)
        self.assertLess(
            first.index("- **Review ID:** review-1"),
            first.index("- **Review ID:** review-2"),
        )
        review_one = first[first.index("- **Review ID:** review-1") :]
        self.assertTrue(
            review_one.split("\n", 2)[1].endswith("superseded"), review_one[:200]
        )
        self.assertIn("- **Independence:** likely_duplicate", first)
        self.assertIn("- **Usefulness:** unknown", first)
        self.assertIn("- **Applicability:** unknown", first)
        self.assertIn("- **Publication status:** unknown", first)
        self.assertIn("tentative; not a verified result", first)
        self.assertNotIn("User comparison note", first)
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
        self.assertIn("_No comparison reviews recorded._", markdown)
        self.assertNotIn("factual-truth decision", markdown)
        self.assertIn("_No claims recorded._", markdown)
        self.assertIn("_No claim contradictions recorded._", markdown)
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
            independence=ResearchSourceIndependence.LIKELY_DUPLICATE,
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
        claims = (
            ResearchClaimRecord(
                claim_id="claim-1",
                text="The finding may affect the target.",
                epistemic_state=ResearchEpistemicState.HYPOTHESIS,
                confidence=ResearchClaimConfidence.LOW,
                source_document_ids=("document-1",),
                evidence_ids=("evidence-1",),
                recorded_at=started + timedelta(minutes=8),
            ),
            ResearchClaimRecord(
                claim_id="claim-2",
                text="The persisted evidence contradicts the original claim.",
                epistemic_state=ResearchEpistemicState.CONTRADICTED,
                confidence=ResearchClaimConfidence.HIGH,
                source_document_ids=("document-2",),
                evidence_ids=("evidence-2",),
                recorded_at=started + timedelta(minutes=9),
                supersedes_claim_id="claim-1",
            ),
        )
        contradiction = ResearchClaimContradictionRecord(
            contradiction_id="contradiction-1",
            claim_ids=("claim-1", "claim-2"),
            evidence_ids=("evidence-1", "evidence-2"),
            note="# contradiction note",
            recorded_at=started + timedelta(minutes=10),
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
            comparison_reviews=(
                ResearchComparisonReviewRecord(
                    review_id="review-1",
                    note_id="note-1",
                    evidence_ids=("evidence-2", "evidence-1"),
                    decision=ResearchComparisonReviewDecision.SUPPORTED,
                    note="Both excerpts address the question.",
                    recorded_at=started + timedelta(minutes=9),
                ),
                ResearchComparisonReviewRecord(
                    review_id="review-2",
                    note_id="note-1",
                    evidence_ids=("evidence-2", "evidence-1"),
                    decision=ResearchComparisonReviewDecision.NOT_SUPPORTED,
                    note="# withdrawn after rereading",
                    recorded_at=started + timedelta(minutes=10),
                    supersedes_review_id="review-1",
                ),
            ),
            claims=claims,
            claim_contradictions=(contradiction,),
        )


if __name__ == "__main__":
    unittest.main()
