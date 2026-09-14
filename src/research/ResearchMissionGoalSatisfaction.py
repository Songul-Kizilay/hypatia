"""Evidence-grounded satisfaction of one bounded research mission.

This is a read-only projection over canonical execution and evidence state.  It
answers whether the *bounded mission deliverable* is supported by what was
recorded; it does not establish universal truth, close a run, or create work.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from core.Exceptions import ResearchError
from research.BackgroundTaskOutcome import BackgroundTaskOutcome
from research.ResearchEvidenceCompletionEvaluation import (
    ResearchEvidenceCompletionEvaluation,
    ResearchEvidenceCompletionStatus,
)
from research.ResearchMissionRecoveryCheckpoint import ResearchMissionRecoveryCheckpoint


class ResearchMissionGoalSatisfactionStatus(StrEnum):
    """Bounded, evidence-only states distinct from execution lifecycle."""

    SATISFIED = "satisfied"
    PARTIALLY_SATISFIED = "partially_satisfied"
    UNRESOLVED = "unresolved"
    BLOCKED = "blocked"
    BUDGET_LIMITED = "budget_limited"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class ResearchMissionGoalSatisfaction:
    """A non-authoritative assessment of the bounded mission deliverable."""

    status: ResearchMissionGoalSatisfactionStatus
    evidence_status: ResearchEvidenceCompletionStatus
    execution_outcome: BackgroundTaskOutcome
    contradiction_outcome: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.status, ResearchMissionGoalSatisfactionStatus):
            raise ResearchError("Research mission goal satisfaction is invalid.")
        if not isinstance(self.evidence_status, ResearchEvidenceCompletionStatus):
            raise ResearchError("Research mission goal evidence status is invalid.")
        if not isinstance(self.execution_outcome, BackgroundTaskOutcome):
            raise ResearchError("Research mission goal execution outcome is invalid.")
        if self.contradiction_outcome not in {
            "",
            "unresolved",
            "structurally_clarified",
        }:
            raise ResearchError("Research mission contradiction outcome is invalid.")
        if self.status is ResearchMissionGoalSatisfactionStatus.SATISFIED and (
            self.execution_outcome is not BackgroundTaskOutcome.COMPLETED
            or self.evidence_status
            is not ResearchEvidenceCompletionStatus.SUFFICIENTLY_SUPPORTED
            or self.contradiction_outcome == "unresolved"
        ):
            raise ResearchError("Satisfied mission goal is inconsistent.")

    @property
    def satisfied(self) -> bool:
        """Whether the bounded mission deliverable is currently supported."""
        return self.status is ResearchMissionGoalSatisfactionStatus.SATISFIED

    def summary(self) -> str:
        """Use scoped language rather than presenting evidence as universal truth."""
        labels = {
            ResearchMissionGoalSatisfactionStatus.SATISFIED: (
                "Satisfied within the current bounded evidence"
            ),
            ResearchMissionGoalSatisfactionStatus.PARTIALLY_SATISFIED: (
                "Partially satisfied within the current bounded evidence"
            ),
            ResearchMissionGoalSatisfactionStatus.UNRESOLVED: "Unresolved",
            ResearchMissionGoalSatisfactionStatus.BLOCKED: "Blocked",
            ResearchMissionGoalSatisfactionStatus.BUDGET_LIMITED: "Budget-limited",
            ResearchMissionGoalSatisfactionStatus.FAILED: "Failed",
            ResearchMissionGoalSatisfactionStatus.CANCELLED: "Cancelled",
        }
        return labels[self.status]


def evaluate_mission_goal_satisfaction(
    execution_outcome: BackgroundTaskOutcome,
    evidence_evaluation: ResearchEvidenceCompletionEvaluation,
    checkpoint: ResearchMissionRecoveryCheckpoint | None = None,
) -> ResearchMissionGoalSatisfaction:
    """Derive bounded satisfaction without mutating canonical research state.

    A completed execution and a report-ready evidence set are both necessary
    but not by themselves sufficient.  A durable unresolved semantic conflict
    remains explicit.  No model prose, claim text, or new follow-up decision is
    interpreted here.
    """
    if not isinstance(execution_outcome, BackgroundTaskOutcome):
        raise ResearchError("Research mission goal execution outcome is invalid.")
    if not isinstance(evidence_evaluation, ResearchEvidenceCompletionEvaluation):
        raise ResearchError("Research mission goal evidence evaluation is invalid.")
    if checkpoint is not None and not isinstance(
        checkpoint, ResearchMissionRecoveryCheckpoint
    ):
        raise ResearchError("Research mission goal checkpoint is invalid.")

    contradiction_outcome = checkpoint.contradiction_outcome if checkpoint else ""
    tentative_conflict_without_outcome = bool(
        checkpoint is not None
        and checkpoint.contradiction_initial_relation == "possible_conflict"
        and not contradiction_outcome
    )
    if execution_outcome is BackgroundTaskOutcome.CANCELLED:
        status = ResearchMissionGoalSatisfactionStatus.CANCELLED
    elif execution_outcome is BackgroundTaskOutcome.FAILED:
        status = ResearchMissionGoalSatisfactionStatus.FAILED
    elif execution_outcome is BackgroundTaskOutcome.RETRYABLE_BUDGET_EXHAUSTED:
        status = ResearchMissionGoalSatisfactionStatus.BUDGET_LIMITED
    elif execution_outcome is BackgroundTaskOutcome.BLOCKED:
        status = ResearchMissionGoalSatisfactionStatus.BLOCKED
    elif execution_outcome is BackgroundTaskOutcome.INTERRUPTED:
        status = ResearchMissionGoalSatisfactionStatus.UNRESOLVED
    elif evidence_evaluation.status is ResearchEvidenceCompletionStatus.BUDGET_LIMITED:
        status = ResearchMissionGoalSatisfactionStatus.BUDGET_LIMITED
    elif (
        tentative_conflict_without_outcome
        or contradiction_outcome == "unresolved"
        or (
            evidence_evaluation.status
            in {
                ResearchEvidenceCompletionStatus.MATERIALLY_UNRESOLVED,
                ResearchEvidenceCompletionStatus.CONFLICTING,
                ResearchEvidenceCompletionStatus.INCOMPLETE,
            }
        )
    ):
        status = ResearchMissionGoalSatisfactionStatus.UNRESOLVED
    elif (
        execution_outcome is BackgroundTaskOutcome.COMPLETED
        and evidence_evaluation.status
        is ResearchEvidenceCompletionStatus.SUFFICIENTLY_SUPPORTED
    ):
        status = ResearchMissionGoalSatisfactionStatus.SATISFIED
    else:
        status = ResearchMissionGoalSatisfactionStatus.PARTIALLY_SATISFIED

    return ResearchMissionGoalSatisfaction(
        status=status,
        evidence_status=evidence_evaluation.status,
        execution_outcome=execution_outcome,
        contradiction_outcome=contradiction_outcome,
    )
