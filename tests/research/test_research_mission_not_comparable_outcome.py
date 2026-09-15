"""A not-comparable judgement is an unresolved comparison gap, not a comparison."""

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
STOP = AutonomyStopReason.RESEARCH_DELIVERABLE_READY


def not_comparable_checkpoint() -> ResearchMissionRecoveryCheckpoint:
    return ResearchMissionRecoveryCheckpoint(
        discovery_id="discovery-1",
        acquired_urls=(
            "https://first.example/reference",
            "https://second.example/reference",
        ),
        body_hashes=("1" * 64, "2" * 64),
        inspected_bytes=600,
        evidence_ids=("evidence-1", "evidence-2"),
        assessment_ids=("assessment-1", "assessment-2"),
        semantic_note_id="note-initial",
        semantic_input_fingerprint="a" * 64,
        semantic_relation="not_comparable",
    )


def conflict_followup_checkpoint(relation: str) -> ResearchMissionRecoveryCheckpoint:
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
        contradiction_followup_source_document_id="document-3",
        contradiction_followup_assessment_id="assessment-3",
        contradiction_followup_input_fingerprint="b" * 64,
        contradiction_followup_relation=relation,
        contradiction_outcome="unresolved",
    )


def evaluation(sources: int = 2) -> ResearchEvidenceCompletionEvaluation:
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
    checkpoint: ResearchMissionRecoveryCheckpoint, sources: int = 2
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


class NotComparableOutcomeTests(unittest.TestCase):
    def test_not_comparable_is_unresolved_and_not_ready(self):
        checkpoint = not_comparable_checkpoint()
        value = outcome_for(checkpoint)

        self.assertIs(value.goal_satisfaction.status, GoalStatus.UNRESOLVED)
        self.assertIs(value.completion_readiness.status, Readiness.NOT_READY_EVIDENCE)
        self.assertFalse(value.completion_readiness.ready)
        explanation = explain_mission_goal_satisfaction(value, STOP, checkpoint)
        self.assertEqual(explanation.reasons, (Reason.SOURCES_NOT_COMPARABLE,))
        summary = explanation.summary()
        self.assertIn("Goal status: unresolved.", summary)
        self.assertIn("judged not comparable", summary)
        self.assertIn("no supported comparison was established", summary)
        self.assertNotIn("supports the bounded teaching deliverable", summary)

    def test_checkpoint_from_before_gap_fields_still_never_becomes_satisfied(self):
        document = _encode_mission_checkpoint(not_comparable_checkpoint())
        assert document is not None
        legacy = {
            key: item
            for key, item in document.items()
            if not key.startswith(("contradiction_", "evidence_gap_"))
        }
        decoded = _decode_mission_checkpoint(legacy)
        assert decoded is not None

        self.assertEqual(decoded.semantic_relation, "not_comparable")
        self.assertIs(
            outcome_for(decoded).goal_satisfaction.status, GoalStatus.UNRESOLVED
        )

    def test_agreement_without_follow_up_is_still_satisfied(self):
        checkpoint = replace(
            not_comparable_checkpoint(), semantic_relation="possible_agreement"
        )

        self.assertIs(
            outcome_for(checkpoint).goal_satisfaction.status, GoalStatus.SATISFIED
        )

    def test_conflict_follow_up_relation_is_named_in_the_explanation(self):
        cases = (
            (
                "not_comparable",
                Reason.CONTRADICTION_FOLLOWUP_NOT_COMPARABLE,
                "not comparable",
            ),
            (
                "possible_conflict",
                Reason.CONTRADICTION_FOLLOWUP_CONFLICT,
                "tentative conflict",
            ),
            (
                "no_supported_comparison",
                Reason.CONTRADICTION_FOLLOWUP_NO_SUPPORT,
                "no supported comparison",
            ),
        )
        for relation, reason, wording in cases:
            with self.subTest(relation=relation):
                checkpoint = conflict_followup_checkpoint(relation)
                value = outcome_for(checkpoint, sources=3)

                self.assertIs(value.goal_satisfaction.status, GoalStatus.UNRESOLVED)
                self.assertIs(
                    value.completion_readiness.status, Readiness.NOT_READY_CONFLICT
                )
                explanation = explain_mission_goal_satisfaction(value, STOP, checkpoint)
                self.assertEqual(
                    explanation.reasons,
                    (Reason.UNRESOLVED_TENTATIVE_CONTRADICTION, reason),
                )
                summary = explanation.summary()
                self.assertIn(wording, summary)
                self.assertNotIn("resolved the", summary)


if __name__ == "__main__":
    unittest.main()
