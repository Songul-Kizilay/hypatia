"""Regression coverage for evidence-only teaching readiness evaluation."""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from research.ResearchAutonomyResult import AutonomyStopReason
from research.ResearchClaimConfidence import ResearchClaimConfidence
from research.ResearchClaimContradictionRecord import ResearchClaimContradictionRecord
from research.ResearchClaimRecord import ResearchClaimRecord
from research.ResearchEpistemicState import ResearchEpistemicState
from research.ResearchEvidenceCompletionEvaluation import (
    ResearchEvidenceCompletionLimitation as Limitation,
)
from research.ResearchEvidenceCompletionEvaluation import (
    ResearchEvidenceCompletionStatus as Status,
)
from research.ResearchEvidenceCompletionEvaluation import (
    evaluate_evidence_completion,
)
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchRun import ResearchRun
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSourceAssessmentRecord import ResearchSourceAssessmentRecord
from research.ResearchSourceComparisonNoteRecord import (
    ResearchSourceComparisonNoteRecord,
)
from research.ResearchSourceRecord import ResearchSourceRecord
from research.ResearchTeachingReport import teaching_report

NOW = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)


def source(number: int) -> ResearchSourceRecord:
    return ResearchSourceRecord(
        document_id=f"doc-{number}",
        url=f"https://example.test/{number}",
        title=f"Source {number}",
        content_type="text/plain",
        fetched_at=NOW,
        added_at=NOW,
    )


def evidence(number: int) -> ResearchEvidenceRecord:
    excerpt = f"Recorded excerpt {number}."
    return ResearchEvidenceRecord(
        evidence_id=f"evidence-{number}",
        source_document_id=f"doc-{number}",
        chunk_id=f"chunk-{number}",
        chunk_index=0,
        excerpt=excerpt,
        excerpt_truncated=False,
        chunk_sha256=sha256(excerpt.encode("utf-8")).hexdigest(),
        note="Grounded excerpt only.",
        recorded_at=NOW,
    )


def assessment(number: int) -> ResearchSourceAssessmentRecord:
    return ResearchSourceAssessmentRecord(
        assessment_id=f"assessment-{number}",
        source_document_id=f"doc-{number}",
        evidence_ids=(f"evidence-{number}",),
        text="Exact-source grounding only.",
        recorded_at=NOW,
    )


def comparison() -> ResearchSourceComparisonNoteRecord:
    return ResearchSourceComparisonNoteRecord(
        note_id="note-1",
        source_document_ids=("doc-1", "doc-2"),
        evidence_ids=("evidence-1", "evidence-2"),
        assessment_ids=("assessment-1", "assessment-2"),
        text="A tentative note, not truth.",
        recorded_at=NOW,
    )


def run(
    *,
    sources: tuple[ResearchSourceRecord, ...] = (),
    evidence_records: tuple[ResearchEvidenceRecord, ...] = (),
    assessments: tuple[ResearchSourceAssessmentRecord, ...] = (),
    comparison_notes: tuple[ResearchSourceComparisonNoteRecord, ...] = (),
    claims: tuple[ResearchClaimRecord, ...] = (),
    contradictions: tuple[ResearchClaimContradictionRecord, ...] = (),
) -> ResearchRun:
    return ResearchRun(
        run_id="run-1",
        question="What do the recorded sources support?",
        status=ResearchRunStatus.COLLECTING,
        sources=sources,
        failures=(),
        created_at=NOW,
        updated_at=NOW,
        evidence=evidence_records,
        assessments=assessments,
        comparison_notes=comparison_notes,
        claims=claims,
        claim_contradictions=contradictions,
    )


class ResearchEvidenceCompletionEvaluationTests(unittest.TestCase):
    def test_two_grounded_sources_and_note_support_a_bounded_teaching_answer(self):
        value = evaluate_evidence_completion(
            run(
                sources=(source(1), source(2)),
                evidence_records=(evidence(1), evidence(2)),
                assessments=(assessment(1), assessment(2)),
                comparison_notes=(comparison(),),
            ),
            AutonomyStopReason.RESEARCH_DELIVERABLE_READY,
        )

        self.assertIs(value.status, Status.SUFFICIENTLY_SUPPORTED)
        self.assertTrue(value.supports_bounded_teaching)
        self.assertEqual(value.limitations, ())

    def test_empty_evidence_is_materially_unresolved_without_inventing_support(self):
        value = evaluate_evidence_completion(run(), AutonomyStopReason.NO_PENDING_STEP)

        self.assertIs(value.status, Status.MATERIALLY_UNRESOLVED)
        self.assertFalse(value.supports_bounded_teaching)
        self.assertIn(Limitation.MISSING_EVIDENCE, value.limitations)
        self.assertIn(Limitation.SOURCE_LIMITED, value.limitations)

    def test_one_evidence_source_is_source_limited_and_missing_corroboration(self):
        value = evaluate_evidence_completion(
            run(
                sources=(source(1),),
                evidence_records=(evidence(1),),
                assessments=(assessment(1),),
            ),
            AutonomyStopReason.RESEARCH_DELIVERABLE_READY,
        )

        self.assertIs(value.status, Status.SOURCE_LIMITED)
        self.assertIn(Limitation.MISSING_CORROBORATION, value.limitations)
        self.assertIn(Limitation.COMPARISON_UNAVAILABLE, value.limitations)

    def test_budget_limit_takes_precedence_over_evidence_readiness(self):
        value = evaluate_evidence_completion(
            run(
                sources=(source(1), source(2)),
                evidence_records=(evidence(1), evidence(2)),
                assessments=(assessment(1), assessment(2)),
                comparison_notes=(comparison(),),
            ),
            AutonomyStopReason.LLM_BUDGET_EXHAUSTED,
        )

        self.assertIs(value.status, Status.BUDGET_LIMITED)
        self.assertFalse(value.supports_bounded_teaching)
        self.assertIn(Limitation.BUDGET_LIMITED, value.limitations)

    def test_recorded_claim_contradiction_is_not_parsed_from_model_note_prose(self):
        claims = (
            ResearchClaimRecord(
                "claim-1",
                "First bounded claim.",
                ResearchEpistemicState.UNKNOWN,
                ResearchClaimConfidence.UNASSESSED,
                ("doc-1",),
                ("evidence-1",),
                NOW,
            ),
            ResearchClaimRecord(
                "claim-2",
                "Second bounded claim.",
                ResearchEpistemicState.UNKNOWN,
                ResearchClaimConfidence.UNASSESSED,
                ("doc-2",),
                ("evidence-2",),
                NOW,
            ),
        )
        contradiction = ResearchClaimContradictionRecord(
            "contradiction-1",
            ("claim-1", "claim-2"),
            ("evidence-1", "evidence-2"),
            "Recorded contradiction remains unresolved.",
            NOW,
        )
        value = evaluate_evidence_completion(
            run(
                sources=(source(1), source(2)),
                evidence_records=(evidence(1), evidence(2)),
                assessments=(assessment(1), assessment(2)),
                comparison_notes=(comparison(),),
                claims=claims,
                contradictions=(contradiction,),
            ),
            AutonomyStopReason.RESEARCH_DELIVERABLE_READY,
        )

        self.assertIs(value.status, Status.CONFLICTING)
        self.assertTrue(value.supports_bounded_teaching)
        self.assertIn(Limitation.RECORDED_CONFLICT, value.limitations)

    def test_report_exposes_evaluation_without_closing_or_promoting_the_run(self):
        subject = run(
            sources=(source(1), source(2)),
            evidence_records=(evidence(1), evidence(2)),
            assessments=(assessment(1), assessment(2)),
            comparison_notes=(comparison(),),
        )

        report = teaching_report(
            subject,
            AutonomyStopReason.RESEARCH_DELIVERABLE_READY.value,
            "Cumulative spending: 12 advances.",
        )

        self.assertIn("Evidence-only completion evaluation:", report)
        self.assertIn("Sufficiently supported for a bounded teaching answer.", report)
        self.assertIn("does not close the research run", report)
        self.assertIs(subject.status, ResearchRunStatus.COLLECTING)


if __name__ == "__main__":
    unittest.main()
