"""Structural clarification of a tentative conflict is not a verified resolution.

Characterization (v0.3.365): only bounded semantic learning missions record
contradiction state. ``semantic_relation == contradiction_initial_relation ==
"possible_conflict"`` with ``contradiction_followup_relation ==
"possible_agreement"`` produced ``structurally_clarified``, which previously
satisfied the goal and marked the mission ready although every comparison was a
tentative model relation, assessments were unassessed and no claim existed. No
mission scope declares an objective that "which side the follow-up aligns with"
completes, so no clarified case keeps a satisfied goal.
"""

from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from research.BackgroundTaskOutcome import BackgroundTaskOutcome
from research.ResearchAutonomyResult import AutonomyStopReason
from research.ResearchEvidenceCompletionEvaluation import (
    ResearchEvidenceCompletionEvaluation,
    ResearchEvidenceCompletionStatus,
)
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
from research.ResearchMissionOutcome import ResearchMissionOutcome
from research.ResearchMissionRecoveryCheckpoint import ResearchMissionRecoveryCheckpoint
from research.ResearchPlanExecutionCodec import (
    _decode_mission_checkpoint,
    _encode_mission_checkpoint,
)

SUPPORTED = ResearchEvidenceCompletionStatus.SUFFICIENTLY_SUPPORTED
STOP = AutonomyStopReason.EXECUTION_TERMINAL


def clarified(followup_source: str = "document-3") -> ResearchMissionRecoveryCheckpoint:
    return ResearchMissionRecoveryCheckpoint(
        semantic_note_id="note-1",
        semantic_input_fingerprint="a" * 64,
        semantic_relation="possible_conflict",
        contradiction_initial_note_id="note-1",
        contradiction_initial_evidence_ids=("evidence-1", "evidence-2"),
        contradiction_initial_source_document_ids=("document-1", "document-2"),
        contradiction_initial_assessment_ids=("assessment-1", "assessment-2"),
        contradiction_initial_input_fingerprint="a" * 64,
        contradiction_initial_relation="possible_conflict",
        contradiction_followup_note_id="note-2",
        contradiction_followup_evidence_id="evidence-3",
        contradiction_followup_source_document_id=followup_source,
        contradiction_followup_assessment_id="assessment-3",
        contradiction_followup_input_fingerprint="b" * 64,
        contradiction_followup_relation="possible_agreement",
        contradiction_outcome="structurally_clarified",
    )


def evaluation(sources: int = 3) -> ResearchEvidenceCompletionEvaluation:
    return ResearchEvidenceCompletionEvaluation(
        status=SUPPORTED,
        supports_bounded_teaching=True,
        source_count=sources,
        evidence_count=sources,
        evidence_source_count=sources,
        assessed_source_count=sources,
        comparison_note_count=sources - 1,
        recorded_claim_contradiction_count=0,
        limitations=(),
    )


def outcome_for(
    checkpoint: ResearchMissionRecoveryCheckpoint | None, sources: int = 3
) -> ResearchMissionOutcome:
    completed = BackgroundTaskOutcome.COMPLETED
    satisfaction = evaluate_mission_goal_satisfaction(
        completed, evaluation(sources), checkpoint
    )
    return ResearchMissionOutcome(
        completed,
        evaluation(sources),
        satisfaction,
        evaluate_mission_completion_readiness(
            satisfaction.status, SUPPORTED, completed, checkpoint
        ),
    )


class ClarifiedConflictOutcomeTests(unittest.TestCase):
    def test_follow_up_agreement_with_either_side_is_unresolved_not_ready(self):
        # The checkpoint records no side and no verified relation; whichever
        # side a tentative agreement aligns with, the original dispute stands.
        for label, followup_source in (
            ("side A", "document-3"),
            ("side B", "document-4"),
        ):
            with self.subTest(side=label):
                checkpoint = clarified(followup_source)
                value = outcome_for(checkpoint)

                self.assertIs(value.goal_satisfaction.status, GoalStatus.UNRESOLVED)
                self.assertIs(
                    value.completion_readiness.status, Readiness.NOT_READY_CONFLICT
                )
                self.assertFalse(value.completion_readiness.ready)
                self.assertEqual(
                    checkpoint.contradiction_followup_relation, "possible_agreement"
                )

    def test_explanation_states_structure_only_and_no_verified_resolution(self):
        checkpoint = clarified()
        explanation = explain_mission_goal_satisfaction(
            outcome_for(checkpoint), STOP, checkpoint
        )

        self.assertEqual(
            explanation.reasons, (Reason.TENTATIVE_CONFLICT_STRUCTURALLY_CLARIFIED,)
        )
        summary = explanation.summary()
        self.assertIn("Goal status: unresolved.", summary)
        self.assertIn("clarifies the conflict structure", summary)
        self.assertIn(
            "does not establish a verified resolution of the original disputed "
            "comparison or claim",
            summary,
        )
        self.assertIn("tentatively agreed", summary)
        self.assertNotIn("supports the bounded teaching deliverable", summary)

    def test_legacy_checkpoint_with_conflict_only_in_semantic_relation_fails_safe(self):
        document = _encode_mission_checkpoint(clarified())
        assert document is not None
        legacy_document = {
            key: item
            for key, item in document.items()
            if not key.startswith(("contradiction_", "evidence_gap_"))
        }
        legacy = _decode_mission_checkpoint(legacy_document)
        assert legacy is not None

        value = outcome_for(legacy, sources=2)

        self.assertEqual(legacy.semantic_relation, "possible_conflict")
        self.assertIs(value.goal_satisfaction.status, GoalStatus.UNRESOLVED)
        self.assertFalse(value.completion_readiness.ready)
        explanation = explain_mission_goal_satisfaction(value, STOP, legacy)
        self.assertEqual(
            explanation.reasons, (Reason.UNRESOLVED_TENTATIVE_CONTRADICTION,)
        )

    def test_genuine_agreement_and_existing_gaps_keep_their_outcomes(self):
        agreement = replace(
            _decode_mission_checkpoint(
                {
                    key: item
                    for key, item in (
                        _encode_mission_checkpoint(clarified()) or {}
                    ).items()
                    if not key.startswith(("contradiction_", "evidence_gap_"))
                }
            )
            or clarified(),
            semantic_relation="possible_agreement",
        )
        self.assertIs(
            outcome_for(agreement, sources=2).goal_satisfaction.status,
            GoalStatus.SATISFIED,
        )
        self.assertTrue(outcome_for(agreement, sources=2).completion_readiness.ready)
        for relation in ("not_comparable", "no_supported_comparison"):
            with self.subTest(relation=relation):
                gap = replace(agreement, semantic_relation=relation)
                value = outcome_for(gap, sources=2)
                self.assertIs(value.goal_satisfaction.status, GoalStatus.UNRESOLVED)
                self.assertFalse(value.completion_readiness.ready)

    def test_no_checkpoint_keeps_evidence_only_behaviour(self):
        self.assertIs(
            outcome_for(None, sources=2).goal_satisfaction.status,
            GoalStatus.SATISFIED,
        )


if __name__ == "__main__":
    unittest.main()
