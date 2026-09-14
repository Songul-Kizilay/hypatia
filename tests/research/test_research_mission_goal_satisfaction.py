"""Evidence-only tests for the bounded mission goal-satisfaction projection."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from research.BackgroundTaskOutcome import BackgroundTaskOutcome
from research.ResearchEvidenceCompletionEvaluation import (
    ResearchEvidenceCompletionEvaluation,
    ResearchEvidenceCompletionStatus,
)
from research.ResearchMissionGoalSatisfaction import (
    ResearchMissionGoalSatisfactionStatus as Status,
)
from research.ResearchMissionGoalSatisfaction import evaluate_mission_goal_satisfaction
from research.ResearchMissionRecoveryCheckpoint import ResearchMissionRecoveryCheckpoint


def evaluation(
    status: ResearchEvidenceCompletionStatus,
) -> ResearchEvidenceCompletionEvaluation:
    return ResearchEvidenceCompletionEvaluation(
        status=status,
        supports_bounded_teaching=status
        in {
            ResearchEvidenceCompletionStatus.SUFFICIENTLY_SUPPORTED,
            ResearchEvidenceCompletionStatus.CONFLICTING,
        },
        source_count=2,
        evidence_count=2,
        evidence_source_count=2,
        assessed_source_count=2,
        comparison_note_count=1,
        recorded_claim_contradiction_count=0,
        limitations=(),
    )


def unresolved_checkpoint() -> ResearchMissionRecoveryCheckpoint:
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
        contradiction_followup_relation="possible_conflict",
        contradiction_outcome="unresolved",
    )


def pending_conflict_checkpoint() -> ResearchMissionRecoveryCheckpoint:
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
    )


class ResearchMissionGoalSatisfactionTests(unittest.TestCase):
    def test_completed_sufficient_evidence_is_satisfied_within_bounded_scope(self):
        value = evaluate_mission_goal_satisfaction(
            BackgroundTaskOutcome.COMPLETED,
            evaluation(ResearchEvidenceCompletionStatus.SUFFICIENTLY_SUPPORTED),
        )

        self.assertIs(value.status, Status.SATISFIED)
        self.assertTrue(value.satisfied)
        self.assertIn("current bounded evidence", value.summary())

    def test_useful_but_incomplete_evidence_is_only_partially_satisfied(self):
        value = evaluate_mission_goal_satisfaction(
            BackgroundTaskOutcome.COMPLETED,
            evaluation(ResearchEvidenceCompletionStatus.PARTIALLY_SUPPORTED),
        )

        self.assertIs(value.status, Status.PARTIALLY_SATISFIED)
        self.assertFalse(value.satisfied)

    def test_durable_unresolved_followup_outcome_prevents_full_satisfaction(self):
        value = evaluate_mission_goal_satisfaction(
            BackgroundTaskOutcome.COMPLETED,
            evaluation(ResearchEvidenceCompletionStatus.SUFFICIENTLY_SUPPORTED),
            unresolved_checkpoint(),
        )

        self.assertIs(value.status, Status.UNRESOLVED)
        self.assertFalse(value.satisfied)

    def test_pending_tentative_conflict_prevents_full_satisfaction(self):
        value = evaluate_mission_goal_satisfaction(
            BackgroundTaskOutcome.COMPLETED,
            evaluation(ResearchEvidenceCompletionStatus.SUFFICIENTLY_SUPPORTED),
            pending_conflict_checkpoint(),
        )

        self.assertIs(value.status, Status.UNRESOLVED)
        self.assertFalse(value.satisfied)

    def test_execution_outcomes_keep_budget_block_failure_and_cancellation_distinct(
        self,
    ):
        ready = evaluation(ResearchEvidenceCompletionStatus.SUFFICIENTLY_SUPPORTED)
        cases = (
            (BackgroundTaskOutcome.RETRYABLE_BUDGET_EXHAUSTED, Status.BUDGET_LIMITED),
            (BackgroundTaskOutcome.BLOCKED, Status.BLOCKED),
            (BackgroundTaskOutcome.FAILED, Status.FAILED),
            (BackgroundTaskOutcome.CANCELLED, Status.CANCELLED),
            (BackgroundTaskOutcome.INTERRUPTED, Status.UNRESOLVED),
        )

        for execution_outcome, expected in cases:
            with self.subTest(execution_outcome=execution_outcome):
                self.assertIs(
                    evaluate_mission_goal_satisfaction(
                        execution_outcome,
                        ready,
                    ).status,
                    expected,
                )

    def test_evaluation_does_not_mutate_canonical_inputs(self):
        ready = evaluation(ResearchEvidenceCompletionStatus.SUFFICIENTLY_SUPPORTED)
        checkpoint = unresolved_checkpoint()

        evaluate_mission_goal_satisfaction(
            BackgroundTaskOutcome.COMPLETED,
            ready,
            checkpoint,
        )

        self.assertIs(
            ready.status,
            ResearchEvidenceCompletionStatus.SUFFICIENTLY_SUPPORTED,
        )
        self.assertEqual(checkpoint.contradiction_outcome, "unresolved")
        self.assertEqual(checkpoint.contradiction_followup_note_id, "note-2")


if __name__ == "__main__":
    unittest.main()
