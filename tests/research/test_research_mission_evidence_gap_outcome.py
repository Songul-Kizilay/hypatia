"""The empty-proposal follow-up is a typed comparison gap, not success or failure."""

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

from core.Exceptions import ResearchError
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


def gap_checkpoint(**changes: object) -> ResearchMissionRecoveryCheckpoint:
    values: dict[str, object] = {
        "discovery_id": "discovery-1",
        "acquired_urls": (
            "https://first.example/reference",
            "https://second.example/reference",
            "https://third.example/reference",
        ),
        "body_hashes": ("1" * 64, "2" * 64, "3" * 64),
        "inspected_bytes": 900,
        "evidence_ids": ("evidence-1", "evidence-2", "evidence-3"),
        "assessment_ids": ("assessment-1", "assessment-2", "assessment-3"),
        "semantic_note_id": "note-initial",
        "semantic_input_fingerprint": "a" * 64,
        "semantic_relation": "no_supported_comparison",
        "evidence_gap_followup_note_id": "note-followup",
        "evidence_gap_followup_input_fingerprint": "b" * 64,
        "evidence_gap_followup_relation": "no_supported_comparison",
        "evidence_gap_outcome": "no_supported_comparison",
    }
    values.update(changes)
    return ResearchMissionRecoveryCheckpoint(**values)  # type: ignore[arg-type]


def evaluation() -> ResearchEvidenceCompletionEvaluation:
    return ResearchEvidenceCompletionEvaluation(
        status=SUPPORTED,
        supports_bounded_teaching=True,
        source_count=3,
        evidence_count=3,
        evidence_source_count=3,
        assessed_source_count=3,
        comparison_note_count=2,
        recorded_claim_contradiction_count=0,
        limitations=(),
    )


def outcome_for(
    checkpoint: ResearchMissionRecoveryCheckpoint,
) -> ResearchMissionOutcome:
    completed = BackgroundTaskOutcome.COMPLETED
    satisfaction = evaluate_mission_goal_satisfaction(
        completed, evaluation(), checkpoint
    )
    return ResearchMissionOutcome(
        completed,
        evaluation(),
        satisfaction,
        evaluate_mission_completion_readiness(
            satisfaction.status, SUPPORTED, completed, checkpoint
        ),
    )


class EvidenceGapCheckpointTests(unittest.TestCase):
    def test_typed_no_supported_comparison_outcome_is_valid(self):
        value = gap_checkpoint()

        self.assertEqual(value.evidence_gap_outcome, "no_supported_comparison")
        self.assertEqual(value.contradiction_outcome, "")

    def test_followup_relation_is_recorded_without_claiming_initial_support(self):
        value = gap_checkpoint(
            evidence_gap_followup_relation="possible_agreement",
            evidence_gap_outcome="followup_comparison_recorded",
        )

        self.assertEqual(value.evidence_gap_outcome, "followup_comparison_recorded")

    def test_inconsistent_gap_state_is_rejected(self):
        for changes in (
            {"evidence_gap_outcome": "resolved"},
            {"evidence_gap_outcome": "followup_comparison_recorded"},
            {"evidence_gap_followup_note_id": ""},
            {"evidence_gap_followup_input_fingerprint": "not-a-fingerprint"},
            {"semantic_relation": "possible_agreement"},
            {"evidence_gap_followup_note_id": "note-initial"},
        ):
            with self.subTest(changes=changes):
                with self.assertRaises(ResearchError):
                    gap_checkpoint(**changes)

    def test_gap_outcome_cannot_coexist_with_a_contradiction_investigation(self):
        with self.assertRaises(ResearchError):
            gap_checkpoint(
                semantic_relation="possible_conflict",
                contradiction_initial_note_id="note-initial",
                contradiction_initial_evidence_ids=("evidence-1", "evidence-2"),
                contradiction_initial_source_document_ids=("document-1", "document-2"),
                contradiction_initial_assessment_ids=("assessment-1", "assessment-2"),
                contradiction_initial_input_fingerprint="a" * 64,
                contradiction_initial_relation="possible_conflict",
            )

    def test_codec_round_trips_the_outcome_and_reads_legacy_documents(self):
        value = gap_checkpoint()
        document = _encode_mission_checkpoint(value)
        assert document is not None

        self.assertEqual(_decode_mission_checkpoint(document), value)
        legacy = {
            key: item
            for key, item in document.items()
            if not key.startswith("evidence_gap_")
        }
        decoded = _decode_mission_checkpoint(legacy)
        assert decoded is not None
        self.assertEqual(decoded.evidence_gap_outcome, "")
        self.assertEqual(decoded.semantic_relation, "no_supported_comparison")


class EvidenceGapGoalTests(unittest.TestCase):
    def test_no_supported_comparison_after_followup_is_unresolved_not_ready(self):
        value = outcome_for(gap_checkpoint())

        self.assertIs(value.goal_satisfaction.status, GoalStatus.UNRESOLVED)
        self.assertIs(value.completion_readiness.status, Readiness.NOT_READY_EVIDENCE)
        explanation = explain_mission_goal_satisfaction(
            value, AutonomyStopReason.NO_PENDING_STEP, gap_checkpoint()
        )
        self.assertEqual(
            explanation.reasons, (Reason.NO_SUPPORTED_COMPARISON_AFTER_FOLLOWUP,)
        )
        summary = explanation.summary()
        self.assertIn("Goal status: unresolved.", summary)
        self.assertIn("not an execution failure or missing evidence", summary)
        self.assertNotIn("satisfied", summary.lower())

    def test_legacy_or_pending_gap_never_becomes_satisfied(self):
        legacy = gap_checkpoint(
            evidence_gap_followup_note_id="",
            evidence_gap_followup_input_fingerprint="",
            evidence_gap_followup_relation="",
            evidence_gap_outcome="",
        )
        value = outcome_for(legacy)

        self.assertIs(value.goal_satisfaction.status, GoalStatus.UNRESOLVED)
        self.assertFalse(value.completion_readiness.ready)
        explanation = explain_mission_goal_satisfaction(
            value, AutonomyStopReason.NO_PENDING_STEP, legacy
        )
        self.assertEqual(explanation.reasons, (Reason.NO_SUPPORTED_COMPARISON,))

    def test_followup_comparison_does_not_retroactively_support_initial_pair(self):
        checkpoint = gap_checkpoint(
            evidence_gap_followup_relation="possible_agreement",
            evidence_gap_outcome="followup_comparison_recorded",
        )
        value = outcome_for(checkpoint)

        self.assertIs(value.goal_satisfaction.status, GoalStatus.UNRESOLVED)
        explanation = explain_mission_goal_satisfaction(
            value, AutonomyStopReason.NO_PENDING_STEP, checkpoint
        )
        self.assertEqual(
            explanation.reasons, (Reason.FOLLOWUP_COMPARISON_WITHOUT_INITIAL_SUPPORT,)
        )
        self.assertIs(value.completion_readiness.status, Readiness.NOT_READY_EVIDENCE)
        summary = explanation.summary()
        self.assertIn("Goal status: unresolved.", summary)
        self.assertIn(
            "does not establish the original comparison or resolve the original gap",
            summary,
        )
        self.assertNotIn("satisfied", summary.lower())

    def test_non_gap_checkpoints_are_unchanged(self):
        agreeing = replace(
            gap_checkpoint(
                evidence_gap_followup_note_id="",
                evidence_gap_followup_input_fingerprint="",
                evidence_gap_followup_relation="",
                evidence_gap_outcome="",
            ),
            semantic_relation="possible_agreement",
        )

        self.assertIs(
            outcome_for(agreeing).goal_satisfaction.status, GoalStatus.SATISFIED
        )


if __name__ == "__main__":
    unittest.main()
