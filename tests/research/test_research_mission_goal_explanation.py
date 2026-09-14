"""Deterministic coverage for typed mission goal explanations."""

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
from research.ResearchAutonomyResult import AutonomyStopReason
from research.ResearchEvidenceCompletionEvaluation import (
    ResearchEvidenceCompletionEvaluation,
)
from research.ResearchEvidenceCompletionEvaluation import (
    ResearchEvidenceCompletionLimitation as Limitation,
)
from research.ResearchEvidenceCompletionEvaluation import (
    ResearchEvidenceCompletionStatus as EvidenceStatus,
)
from research.ResearchMissionCompletionReadiness import (
    evaluate_mission_completion_readiness,
)
from research.ResearchMissionGoalExplanation import (
    ResearchMissionGoalExplanationReason as Reason,
)
from research.ResearchMissionGoalExplanation import (
    explain_mission_goal_satisfaction,
)
from research.ResearchMissionGoalSatisfaction import (
    ResearchMissionGoalSatisfaction,
)
from research.ResearchMissionGoalSatisfaction import (
    ResearchMissionGoalSatisfactionStatus as GoalStatus,
)
from research.ResearchMissionOutcome import ResearchMissionOutcome
from research.ResearchMissionRecoveryCheckpoint import ResearchMissionRecoveryCheckpoint


def evaluation(
    status: EvidenceStatus,
    limitations: tuple[Limitation, ...] = (),
) -> ResearchEvidenceCompletionEvaluation:
    return ResearchEvidenceCompletionEvaluation(
        status=status,
        supports_bounded_teaching=status
        in {EvidenceStatus.SUFFICIENTLY_SUPPORTED, EvidenceStatus.CONFLICTING},
        source_count=2,
        evidence_count=2,
        evidence_source_count=2,
        assessed_source_count=2,
        comparison_note_count=1,
        recorded_claim_contradiction_count=0,
        limitations=limitations,
    )


def outcome(
    *,
    execution: BackgroundTaskOutcome = BackgroundTaskOutcome.COMPLETED,
    evidence_status: EvidenceStatus = EvidenceStatus.SUFFICIENTLY_SUPPORTED,
    goal_status: GoalStatus = GoalStatus.SATISFIED,
    limitations: tuple[Limitation, ...] = (),
    contradiction_outcome: str = "",
) -> ResearchMissionOutcome:
    readiness = evaluation(evidence_status, limitations)
    satisfaction = ResearchMissionGoalSatisfaction(
        status=goal_status,
        evidence_status=evidence_status,
        execution_outcome=execution,
        contradiction_outcome=contradiction_outcome,
    )
    return ResearchMissionOutcome(
        execution,
        readiness,
        satisfaction,
        evaluate_mission_completion_readiness(
            goal_status,
            evidence_status,
            execution,
        ),
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


class ResearchMissionGoalExplanationTests(unittest.TestCase):
    def test_satisfied_mission_renders_only_bounded_coverage(self):
        value = explain_mission_goal_satisfaction(
            outcome(), AutonomyStopReason.RESEARCH_DELIVERABLE_READY
        )

        self.assertEqual(value.reasons, (Reason.SUPPORTED_CURRENT_EVIDENCE,))
        self.assertIn("Goal status: satisfied.", value.summary())
        self.assertIn("2 accepted source(s)", value.summary())
        self.assertIn("not factual completeness", value.summary())
        self.assertIn("bounded teaching deliverable", value.summary())

    def test_partial_mission_surfaces_remaining_evidence_gap(self):
        value = explain_mission_goal_satisfaction(
            outcome(
                evidence_status=EvidenceStatus.PARTIALLY_SUPPORTED,
                goal_status=GoalStatus.PARTIALLY_SATISFIED,
                limitations=(Limitation.MISSING_CORROBORATION,),
            ),
            AutonomyStopReason.RESEARCH_DELIVERABLE_READY,
        )

        self.assertEqual(value.reasons, (Reason.MISSING_CORROBORATION,))

    def test_unresolved_contradiction_is_explicit_without_declaring_truth(self):
        subject = outcome(
            goal_status=GoalStatus.UNRESOLVED,
            contradiction_outcome="unresolved",
        )
        value = explain_mission_goal_satisfaction(
            subject,
            AutonomyStopReason.RESEARCH_DELIVERABLE_READY,
            unresolved_checkpoint(),
        )

        self.assertIn(Reason.UNRESOLVED_TENTATIVE_CONTRADICTION, value.reasons)
        self.assertNotIn("true", value.summary().lower())

    def test_budget_scope_authority_failure_and_cancellation_remain_distinct(self):
        cases = (
            (
                outcome(
                    execution=BackgroundTaskOutcome.RETRYABLE_BUDGET_EXHAUSTED,
                    evidence_status=EvidenceStatus.BUDGET_LIMITED,
                    goal_status=GoalStatus.BUDGET_LIMITED,
                ),
                AutonomyStopReason.NETWORK_BUDGET_EXHAUSTED,
                Reason.CUMULATIVE_BUDGET_EXHAUSTED,
            ),
            (
                outcome(
                    execution=BackgroundTaskOutcome.BLOCKED,
                    goal_status=GoalStatus.BLOCKED,
                ),
                AutonomyStopReason.STEP_BLOCKED,
                Reason.SCOPE_OR_AUTHORITY_BLOCKED,
            ),
            (
                outcome(
                    execution=BackgroundTaskOutcome.FAILED,
                    goal_status=GoalStatus.FAILED,
                ),
                AutonomyStopReason.STEP_FAILED,
                Reason.EXECUTION_FAILED,
            ),
            (
                outcome(
                    execution=BackgroundTaskOutcome.CANCELLED,
                    goal_status=GoalStatus.CANCELLED,
                ),
                AutonomyStopReason.CANCELLED,
                Reason.EXECUTION_CANCELLED,
            ),
        )

        for subject, stop, expected in cases:
            with self.subTest(stop=stop):
                expected_status = subject.goal_satisfaction.status.value.replace(
                    "_", " "
                )
                self.assertIn(
                    expected,
                    explain_mission_goal_satisfaction(subject, stop).reasons,
                )
                self.assertIn(
                    f"Goal status: {expected_status}.",
                    explain_mission_goal_satisfaction(subject, stop).summary(),
                )

    def test_rejects_inconsistent_canonical_state_instead_of_guessing(self):
        subject = outcome()
        inconsistent = ResearchMissionGoalSatisfaction(
            status=GoalStatus.SATISFIED,
            evidence_status=EvidenceStatus.SUFFICIENTLY_SUPPORTED,
            execution_outcome=BackgroundTaskOutcome.COMPLETED,
            contradiction_outcome="",
        )
        malformed = ResearchMissionOutcome(
            subject.execution_outcome,
            subject.evidence_evaluation,
            inconsistent,
            evaluate_mission_completion_readiness(
                GoalStatus.SATISFIED,
                EvidenceStatus.SUFFICIENTLY_SUPPORTED,
                BackgroundTaskOutcome.COMPLETED,
            ),
        )

        checkpoint = unresolved_checkpoint()
        with self.assertRaisesRegex(Exception, "contradiction state mismatches"):
            explain_mission_goal_satisfaction(
                malformed,
                AutonomyStopReason.RESEARCH_DELIVERABLE_READY,
                checkpoint,
            )

    def test_unchanged_state_renders_the_same_explanation_after_restart(self):
        checkpoint = unresolved_checkpoint()
        subject = outcome(
            goal_status=GoalStatus.UNRESOLVED,
            contradiction_outcome="unresolved",
        )

        before = explain_mission_goal_satisfaction(
            subject,
            AutonomyStopReason.RESEARCH_DELIVERABLE_READY,
            checkpoint,
        )
        after = explain_mission_goal_satisfaction(
            subject,
            AutonomyStopReason.RESEARCH_DELIVERABLE_READY,
            checkpoint,
        )

        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
