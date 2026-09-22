"""Regression coverage for evidence-only teaching readiness evaluation."""

from __future__ import annotations

import sys
import unittest
from dataclasses import replace
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
    ResearchEvidenceCompletionCaveat as Caveat,
)
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
from research.ResearchMissionGoalExplanation import (
    ResearchMissionGoalExplanationReason as Reason,
)
from research.ResearchMissionGoalExplanation import (
    explain_mission_goal_satisfaction,
)
from research.ResearchMissionGoalSatisfaction import (
    ResearchMissionGoalSatisfactionStatus as GoalStatus,
)
from research.ResearchMissionOutcome import mission_outcome_for
from research.ResearchRun import ResearchRun
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSourceAssessmentRecord import ResearchSourceAssessmentRecord
from research.ResearchSourceComparisonNoteRecord import (
    ResearchSourceComparisonNoteRecord,
)
from research.ResearchSourceIndependence import ResearchSourceIndependence
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
        self.assertIn(
            "Mission goal satisfaction: Satisfied within the current bounded evidence.",
            report,
        )
        self.assertIn("Goal-satisfaction explanation:", report)
        self.assertIn("Report or model prose cannot change it.", report)
        self.assertIn("does not close the research run", report)
        self.assertIs(subject.status, ResearchRunStatus.COLLECTING)

    def test_report_appends_gap_closing_guidance_derived_from_limitations(self):
        subject = run(
            sources=(source(1),),
            evidence_records=(evidence(1),),
            assessments=(assessment(1),),
        )

        report = teaching_report(
            subject,
            AutonomyStopReason.RESEARCH_DELIVERABLE_READY.value,
            "Cumulative spending: 12 advances.",
        )

        self.assertIn("What would help close this gap", report)
        self.assertIn("evidence from a second, distinct source", report)
        self.assertIn("a retained comparison note between the sources", report)

    def test_fully_supported_report_has_no_gap_closing_guidance_section(self):
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

        self.assertNotIn("What would help close this gap", report)

    def test_report_comparison_prose_cannot_change_typed_goal_explanation(self):
        common = dict(
            sources=(source(1), source(2)),
            evidence_records=(evidence(1), evidence(2)),
            assessments=(assessment(1), assessment(2)),
        )
        first = teaching_report(
            run(comparison_notes=(comparison(),), **common),
            AutonomyStopReason.RESEARCH_DELIVERABLE_READY.value,
            "Cumulative spending: 12 advances.",
        )
        altered_note = ResearchSourceComparisonNoteRecord(
            note_id="note-1",
            source_document_ids=("doc-1", "doc-2"),
            evidence_ids=("evidence-1", "evidence-2"),
            assessment_ids=("assessment-1", "assessment-2"),
            text="Untrusted prose claiming a different conclusion.",
            recorded_at=NOW,
        )
        second = teaching_report(
            run(comparison_notes=(altered_note,), **common),
            AutonomyStopReason.RESEARCH_DELIVERABLE_READY.value,
            "Cumulative spending: 12 advances.",
        )

        first_line = next(
            line for line in first.splitlines() if line.startswith("Goal-satisfaction")
        )
        second_line = next(
            line for line in second.splitlines() if line.startswith("Goal-satisfaction")
        )
        self.assertEqual(first_line, second_line)


def judged(
    number: int,
    independence: ResearchSourceIndependence,
    *,
    suffix: str = "",
    supersedes: str | None = None,
) -> ResearchSourceAssessmentRecord:
    return ResearchSourceAssessmentRecord(
        assessment_id=f"assessment-{number}{suffix}",
        source_document_id=f"doc-{number}",
        evidence_ids=(f"evidence-{number}",),
        text="Exact-source grounding only.",
        recorded_at=NOW,
        supersedes_assessment_id=supersedes,
        independence=independence,
    )


def grounded_run(*assessments: ResearchSourceAssessmentRecord) -> ResearchRun:
    return run(
        sources=(source(1), source(2)),
        evidence_records=(evidence(1), evidence(2)),
        assessments=assessments,
        comparison_notes=(comparison(),),
    )


STOP = AutonomyStopReason.RESEARCH_DELIVERABLE_READY


class SourceIndependenceCaveatTests(unittest.TestCase):
    def test_one_unknown_independence_is_an_explicit_caveat(self):
        value = evaluate_evidence_completion(
            grounded_run(
                judged(1, ResearchSourceIndependence.UNKNOWN),
                judged(2, ResearchSourceIndependence.INDEPENDENT),
            ),
            STOP,
        )

        self.assertEqual(value.caveats, (Caveat.SOURCE_INDEPENDENCE_UNVERIFIED,))

    def test_all_unknown_stays_explicit_and_never_claims_independence(self):
        subject = grounded_run(assessment(1), assessment(2))
        value = evaluate_evidence_completion(subject, STOP)
        report = teaching_report(subject, STOP.value, "Spend.")

        self.assertEqual(value.caveats, (Caveat.SOURCE_INDEPENDENCE_UNVERIFIED,))
        self.assertIn("source independence unverified", report)
        self.assertIn("source independence was not established", report)
        self.assertIn("corroboration independence remains unverified", report)
        for forbidden in (
            "sources are independent",
            "independently confirmed",
            "conflict is resolved",
        ):
            self.assertNotIn(forbidden, report.lower())

    def test_explicit_independent_assessments_have_no_unknown_caveat(self):
        subject = grounded_run(
            judged(1, ResearchSourceIndependence.INDEPENDENT),
            judged(2, ResearchSourceIndependence.INDEPENDENT),
        )
        report = teaching_report(subject, STOP.value, "Spend.")

        self.assertEqual(evaluate_evidence_completion(subject, STOP).caveats, ())
        self.assertIn("Uncertainty caveats: none recorded.", report)
        self.assertNotIn("Caveat (secondary", report)

    def test_derivative_relation_keeps_the_stronger_caveat(self):
        for relation in (
            ResearchSourceIndependence.DERIVATIVE,
            ResearchSourceIndependence.LIKELY_DUPLICATE,
        ):
            with self.subTest(relation=relation):
                subject = grounded_run(
                    judged(1, relation),
                    judged(2, ResearchSourceIndependence.INDEPENDENT),
                )
                value = evaluate_evidence_completion(subject, STOP)
                report = teaching_report(subject, STOP.value, "Spend.")

                self.assertEqual(value.caveats, (Caveat.SOURCE_NOT_INDEPENDENT,))
                self.assertIn("derivative or a likely duplicate", report)
                self.assertNotIn("source independence unverified", report)

    def test_unknown_does_not_change_satisfaction_or_completion_readiness(self):
        unknown = mission_outcome_for(grounded_run(assessment(1), assessment(2)), STOP)
        independent = mission_outcome_for(
            grounded_run(
                judged(1, ResearchSourceIndependence.INDEPENDENT),
                judged(2, ResearchSourceIndependence.INDEPENDENT),
            ),
            STOP,
        )

        self.assertIs(unknown.evidence_evaluation.status, Status.SUFFICIENTLY_SUPPORTED)
        self.assertIs(unknown.goal_satisfaction.status, GoalStatus.SATISFIED)
        self.assertEqual(unknown.goal_satisfaction, independent.goal_satisfaction)
        self.assertEqual(unknown.completion_readiness, independent.completion_readiness)
        self.assertTrue(unknown.completion_readiness.ready)
        self.assertEqual(unknown.summary(), independent.summary())

    def test_goal_explanation_keeps_status_primary_and_caveat_secondary(self):
        subject = grounded_run(assessment(1), assessment(2))
        explanation = explain_mission_goal_satisfaction(
            mission_outcome_for(subject, STOP), STOP
        )
        summary = explanation.summary()

        self.assertEqual(explanation.reasons, (Reason.SUPPORTED_CURRENT_EVIDENCE,))
        self.assertEqual(explanation.caveats, (Caveat.SOURCE_INDEPENDENCE_UNVERIFIED,))
        self.assertLess(
            summary.index("Goal status: satisfied."),
            summary.index("Caveat (secondary; does not change goal status)"),
        )
        self.assertNotIn(
            "independent corroboration",
            summary.replace("corroboration independence remains unverified", ""),
        )

    def test_missing_legacy_assessment_is_unverified_not_independent(self):
        value = evaluate_evidence_completion(
            run(
                sources=(source(1), source(2)),
                evidence_records=(evidence(1), evidence(2)),
                assessments=(judged(1, ResearchSourceIndependence.INDEPENDENT),),
            ),
            STOP,
        )

        self.assertIn(Caveat.SOURCE_INDEPENDENCE_UNVERIFIED, value.caveats)

    def test_superseded_unknown_no_longer_speaks(self):
        value = evaluate_evidence_completion(
            grounded_run(
                assessment(1),
                judged(
                    1,
                    ResearchSourceIndependence.INDEPENDENT,
                    suffix="-b",
                    supersedes="assessment-1",
                ),
                judged(2, ResearchSourceIndependence.INDEPENDENT),
            ),
            STOP,
        )

        self.assertEqual(value.caveats, ())

    def test_regeneration_is_deterministic_and_does_not_mutate_the_run(self):
        subject = grounded_run(assessment(1), assessment(2))
        snapshot = repr(subject)

        first = teaching_report(subject, STOP.value, "Spend.")
        second = teaching_report(subject, STOP.value, "Spend.")

        self.assertEqual(first, second)
        self.assertEqual(repr(subject), snapshot)
        self.assertIs(subject.status, ResearchRunStatus.COLLECTING)

    def test_evaluation_rejects_malformed_caveats(self):
        valid = evaluate_evidence_completion(
            grounded_run(assessment(1), assessment(2)), STOP
        )
        for caveats in (
            ("source_independence_unverified",),
            (
                Caveat.SOURCE_INDEPENDENCE_UNVERIFIED,
                Caveat.SOURCE_INDEPENDENCE_UNVERIFIED,
            ),
        ):
            with self.subTest(caveats=caveats):
                with self.assertRaisesRegex(Exception, "caveats are invalid"):
                    replace(valid, caveats=caveats)


if __name__ == "__main__":
    unittest.main()
