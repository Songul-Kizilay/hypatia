"""A tentative agreement is not a supported comparison.

Characterization (v0.3.366): only bounded semantic learning missions reach goal
satisfaction (the teaching report is rendered only on the learning path). The
single agreement value is ``semantic_relation == "possible_agreement"`` with no
contradiction state. It became satisfied and ready whenever execution completed
and evidence was "sufficiently supported" (two accepted, evidence-bearing,
assessed sources and one retained note), with unassessed trust, unknown
independence and no claims; operator independence judgements, note prose and
claims never changed that. The data model has no verified or supported agreement
state: a comparison candidate carries only a tentative relation, notes carry no
verification flag and claims are not linked to comparisons. So no agreement case
is kept satisfied. A checkpoint without any recorded relation but with retained
notes also fails safe; a run evaluated without a mission checkpoint keeps its
evidence-only behaviour.
"""

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

from research.BackgroundTaskOutcome import BackgroundTaskOutcome
from research.ResearchAutonomyResult import AutonomyStopReason
from research.ResearchClaimConfidence import ResearchClaimConfidence
from research.ResearchClaimRecord import ResearchClaimRecord
from research.ResearchEpistemicState import ResearchEpistemicState
from research.ResearchEvidenceCompletionEvaluation import (
    ResearchEvidenceCompletionCaveat,
    ResearchEvidenceCompletionEvaluation,
    ResearchEvidenceCompletionStatus,
)
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchInformationTrust import ResearchInformationTrust
from research.ResearchMissionCompletionReadiness import (
    ResearchMissionCompletionReadinessStatus as Readiness,
)
from research.ResearchMissionCompletionReadiness import (
    evaluate_mission_completion_readiness,
)
from research.ResearchMissionGoalExplanation import (
    ResearchMissionGoalExplanationReason as Reason,
)
from research.ResearchMissionGoalExplanation import explain_mission_goal_satisfaction
from research.ResearchMissionGoalSatisfaction import (
    ResearchMissionGoalSatisfactionStatus as GoalStatus,
)
from research.ResearchMissionGoalSatisfaction import evaluate_mission_goal_satisfaction
from research.ResearchMissionOutcome import ResearchMissionOutcome, mission_outcome_for
from research.ResearchMissionRecoveryCheckpoint import ResearchMissionRecoveryCheckpoint
from research.ResearchRun import ResearchRun
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSourceAssessmentRecord import ResearchSourceAssessmentRecord
from research.ResearchSourceComparisonNoteRecord import (
    ResearchSourceComparisonNoteRecord,
)
from research.ResearchSourceIndependence import ResearchSourceIndependence
from research.ResearchSourceRecord import ResearchSourceRecord

NOW = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)
STOP = AutonomyStopReason.RESEARCH_DELIVERABLE_READY
SUPPORTED = ResearchEvidenceCompletionStatus.SUFFICIENTLY_SUPPORTED


def agreement_checkpoint(**changes: object) -> ResearchMissionRecoveryCheckpoint:
    values: dict[str, object] = {
        "discovery_id": "discovery-1",
        "acquired_urls": ("https://example.test/1", "https://example.test/2"),
        "body_hashes": ("1" * 64, "2" * 64),
        "inspected_bytes": 600,
        "evidence_ids": ("evidence-1", "evidence-2"),
        "assessment_ids": ("assessment-1", "assessment-2"),
        "semantic_note_id": "note-1",
        "semantic_input_fingerprint": "a" * 64,
        "semantic_relation": "possible_agreement",
    }
    values.update(changes)
    return ResearchMissionRecoveryCheckpoint(**values)  # type: ignore[arg-type]


def run(
    *,
    trust: ResearchInformationTrust = ResearchInformationTrust.UNASSESSED,
    independence: ResearchSourceIndependence = ResearchSourceIndependence.UNKNOWN,
    claims: tuple[ResearchClaimRecord, ...] = (),
) -> ResearchRun:
    sources = tuple(
        ResearchSourceRecord(
            document_id=f"doc-{number}",
            url=f"https://example.test/{number}",
            title=f"Source {number}",
            content_type="text/plain",
            fetched_at=NOW,
            added_at=NOW,
        )
        for number in (1, 2)
    )
    evidence = tuple(
        ResearchEvidenceRecord(
            evidence_id=f"evidence-{number}",
            source_document_id=f"doc-{number}",
            chunk_id=f"chunk-{number}",
            chunk_index=0,
            excerpt=f"Recorded excerpt {number}.",
            excerpt_truncated=False,
            chunk_sha256=sha256(f"Recorded excerpt {number}.".encode()).hexdigest(),
            note="Grounded excerpt only.",
            recorded_at=NOW,
        )
        for number in (1, 2)
    )
    assessments = tuple(
        ResearchSourceAssessmentRecord(
            assessment_id=f"assessment-{number}",
            source_document_id=f"doc-{number}",
            evidence_ids=(f"evidence-{number}",),
            text="Exact-source grounding only.",
            recorded_at=NOW,
            information_trust=trust,
            independence=independence,
        )
        for number in (1, 2)
    )
    note = ResearchSourceComparisonNoteRecord(
        note_id="note-1",
        source_document_ids=("doc-1", "doc-2"),
        evidence_ids=("evidence-1", "evidence-2"),
        assessment_ids=("assessment-1", "assessment-2"),
        text="Mission semantic research note; Tentative relation: possible_agreement.",
        recorded_at=NOW,
    )
    return ResearchRun(
        run_id="run-1",
        question="What do the recorded sources support?",
        status=ResearchRunStatus.COLLECTING,
        sources=sources,
        failures=(),
        created_at=NOW,
        updated_at=NOW,
        evidence=evidence,
        assessments=assessments,
        comparison_notes=(note,),
        claims=claims,
    )


def evaluation(
    caveats: tuple[ResearchEvidenceCompletionCaveat, ...] = (),
) -> ResearchEvidenceCompletionEvaluation:
    return ResearchEvidenceCompletionEvaluation(
        status=SUPPORTED,
        supports_bounded_teaching=True,
        source_count=2,
        evidence_count=2,
        evidence_source_count=2,
        assessed_source_count=2,
        comparison_note_count=1,
        recorded_claim_contradiction_count=0,
        limitations=(),
        caveats=caveats,
    )


def outcome_for(
    checkpoint: ResearchMissionRecoveryCheckpoint | None,
    caveats: tuple[ResearchEvidenceCompletionCaveat, ...] = (),
) -> ResearchMissionOutcome:
    completed = BackgroundTaskOutcome.COMPLETED
    satisfaction = evaluate_mission_goal_satisfaction(
        completed, evaluation(caveats), checkpoint
    )
    return ResearchMissionOutcome(
        completed,
        evaluation(caveats),
        satisfaction,
        evaluate_mission_completion_readiness(
            satisfaction.status, SUPPORTED, completed, checkpoint
        ),
    )


class TentativeAgreementOutcomeTests(unittest.TestCase):
    def test_two_source_tentative_agreement_is_unresolved_and_not_ready(self):
        checkpoint = agreement_checkpoint()
        value = outcome_for(checkpoint)

        self.assertIs(value.goal_satisfaction.status, GoalStatus.UNRESOLVED)
        self.assertIs(value.completion_readiness.status, Readiness.NOT_READY_EVIDENCE)
        self.assertFalse(value.completion_readiness.ready)
        explanation = explain_mission_goal_satisfaction(value, STOP, checkpoint)
        self.assertEqual(explanation.reasons, (Reason.TENTATIVE_AGREEMENT_UNSUPPORTED,))
        summary = explanation.summary()
        self.assertIn("Goal status: unresolved.", summary)
        self.assertIn("The selected sources tentatively agree", summary)
        self.assertIn("does not establish a sufficiently supported comparison", summary)
        self.assertNotIn("supports the bounded teaching deliverable", summary)

    def test_independence_trust_and_claims_do_not_upgrade_tentative_agreement(self):
        checkpoint = agreement_checkpoint()
        claim = ResearchClaimRecord(
            "claim-1",
            "Operator-recorded claim about the sources.",
            ResearchEpistemicState.FACT,
            ResearchClaimConfidence.HIGH,
            ("doc-1", "doc-2"),
            ("evidence-1", "evidence-2"),
            NOW,
        )
        variants = (
            ("unknown independence", run()),
            (
                "independent sources",
                run(independence=ResearchSourceIndependence.INDEPENDENT),
            ),
            ("high trust", run(trust=ResearchInformationTrust.HIGH)),
            ("claims present", run(claims=(claim,))),
        )
        for label, subject in variants:
            with self.subTest(case=label):
                value = mission_outcome_for(subject, STOP, checkpoint)

                self.assertIs(value.evidence_evaluation.status, SUPPORTED)
                self.assertIs(value.goal_satisfaction.status, GoalStatus.UNRESOLVED)
                self.assertFalse(value.completion_readiness.ready)
        self.assertEqual(
            mission_outcome_for(run(), STOP, checkpoint).evidence_evaluation.caveats,
            (ResearchEvidenceCompletionCaveat.SOURCE_INDEPENDENCE_UNVERIFIED,),
        )

    def test_checkpoint_without_any_relation_but_with_notes_fails_safe(self):
        legacy = agreement_checkpoint(
            semantic_note_id="",
            semantic_input_fingerprint="",
            semantic_relation="",
        )
        value = outcome_for(legacy)

        self.assertIs(value.goal_satisfaction.status, GoalStatus.UNRESOLVED)
        self.assertFalse(value.completion_readiness.ready)
        self.assertEqual(
            explain_mission_goal_satisfaction(value, STOP, legacy).reasons,
            (Reason.COMPARISON_RELATION_UNRECORDED,),
        )

    def test_evaluation_without_a_mission_checkpoint_keeps_evidence_only_rule(self):
        value = outcome_for(None)

        self.assertIs(value.goal_satisfaction.status, GoalStatus.SATISFIED)
        self.assertTrue(value.completion_readiness.ready)

    def test_other_relations_keep_their_unresolved_outcomes(self):
        conflict = agreement_checkpoint(
            semantic_relation="possible_conflict",
            contradiction_initial_note_id="note-1",
            contradiction_initial_evidence_ids=("evidence-1", "evidence-2"),
            contradiction_initial_source_document_ids=("doc-1", "doc-2"),
            contradiction_initial_assessment_ids=("assessment-1", "assessment-2"),
            contradiction_initial_input_fingerprint="a" * 64,
            contradiction_initial_relation="possible_conflict",
        )
        clarified = replace(
            conflict,
            contradiction_followup_note_id="note-2",
            contradiction_followup_evidence_id="evidence-3",
            contradiction_followup_source_document_id="doc-3",
            contradiction_followup_assessment_id="assessment-3",
            contradiction_followup_input_fingerprint="b" * 64,
            contradiction_followup_relation="possible_agreement",
            contradiction_outcome="structurally_clarified",
        )
        cases = (
            ("possible_conflict", conflict, Readiness.NOT_READY_CONFLICT),
            ("structurally_clarified", clarified, Readiness.NOT_READY_CONFLICT),
            (
                "not_comparable",
                agreement_checkpoint(semantic_relation="not_comparable"),
                Readiness.NOT_READY_EVIDENCE,
            ),
            (
                "no_supported_comparison",
                agreement_checkpoint(semantic_relation="no_supported_comparison"),
                Readiness.NOT_READY_EVIDENCE,
            ),
        )
        for label, checkpoint, readiness in cases:
            with self.subTest(relation=label):
                value = outcome_for(checkpoint)
                self.assertIs(value.goal_satisfaction.status, GoalStatus.UNRESOLVED)
                self.assertIs(value.completion_readiness.status, readiness)


if __name__ == "__main__":
    unittest.main()
