"""Completion-readiness must remain distinct from lifecycle and truth."""

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
    ResearchEvidenceCompletionStatus as EvidenceStatus,
)
from research.ResearchMissionCompletionReadiness import (
    ResearchMissionCompletionReadinessStatus as Status,
)
from research.ResearchMissionCompletionReadiness import (
    evaluate_mission_completion_readiness,
)
from research.ResearchMissionGoalSatisfaction import (
    ResearchMissionGoalSatisfactionStatus as GoalStatus,
)
from research.ResearchMissionRecoveryCheckpoint import ResearchMissionRecoveryCheckpoint


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


class ResearchMissionCompletionReadinessTests(unittest.TestCase):
    def test_ready_requires_existing_satisfied_goal_state(self):
        value = evaluate_mission_completion_readiness(
            GoalStatus.SATISFIED,
            EvidenceStatus.SUFFICIENTLY_SUPPORTED,
            BackgroundTaskOutcome.COMPLETED,
        )

        self.assertIs(value.status, Status.READY)
        self.assertTrue(value.ready)
        self.assertIn("bounded user conclusion", value.summary())

    def test_partial_and_unresolved_outcomes_are_not_ready(self):
        partial = evaluate_mission_completion_readiness(
            GoalStatus.PARTIALLY_SATISFIED,
            EvidenceStatus.PARTIALLY_SUPPORTED,
            BackgroundTaskOutcome.COMPLETED,
        )
        conflict = evaluate_mission_completion_readiness(
            GoalStatus.UNRESOLVED,
            EvidenceStatus.SUFFICIENTLY_SUPPORTED,
            BackgroundTaskOutcome.COMPLETED,
            unresolved_checkpoint(),
        )

        self.assertIs(partial.status, Status.NOT_READY_EVIDENCE)
        self.assertFalse(partial.ready)
        self.assertIs(conflict.status, Status.NOT_READY_CONFLICT)
        self.assertFalse(conflict.ready)

    def test_boundary_budget_execution_failure_and_cancellation_stay_distinct(self):
        cases = (
            (
                GoalStatus.BLOCKED,
                EvidenceStatus.INCOMPLETE,
                BackgroundTaskOutcome.BLOCKED,
                Status.NOT_READY_BOUNDARY,
            ),
            (
                GoalStatus.BUDGET_LIMITED,
                EvidenceStatus.BUDGET_LIMITED,
                BackgroundTaskOutcome.RETRYABLE_BUDGET_EXHAUSTED,
                Status.NOT_READY_BUDGET,
            ),
            (
                GoalStatus.UNRESOLVED,
                EvidenceStatus.INCOMPLETE,
                BackgroundTaskOutcome.INTERRUPTED,
                Status.NOT_READY_EXECUTION,
            ),
            (
                GoalStatus.FAILED,
                EvidenceStatus.INCOMPLETE,
                BackgroundTaskOutcome.FAILED,
                Status.FAILED,
            ),
            (
                GoalStatus.CANCELLED,
                EvidenceStatus.INCOMPLETE,
                BackgroundTaskOutcome.CANCELLED,
                Status.CANCELLED,
            ),
        )

        for goal, evidence, execution, expected in cases:
            with self.subTest(expected=expected):
                value = evaluate_mission_completion_readiness(
                    goal,
                    evidence,
                    execution,
                )
                self.assertIs(value.status, expected)
                self.assertFalse(value.ready)

    def test_unchanged_canonical_state_is_deterministic_and_non_mutating(self):
        checkpoint = unresolved_checkpoint()
        before = evaluate_mission_completion_readiness(
            GoalStatus.UNRESOLVED,
            EvidenceStatus.SUFFICIENTLY_SUPPORTED,
            BackgroundTaskOutcome.COMPLETED,
            checkpoint,
        )
        after = evaluate_mission_completion_readiness(
            GoalStatus.UNRESOLVED,
            EvidenceStatus.SUFFICIENTLY_SUPPORTED,
            BackgroundTaskOutcome.COMPLETED,
            checkpoint,
        )

        self.assertEqual(before, after)
        self.assertEqual(checkpoint.contradiction_outcome, "unresolved")


if __name__ == "__main__":
    unittest.main()
