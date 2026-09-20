"""Read-only answer to whether a bounded mission is ready for user conclusion."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from core.Exceptions import ResearchError
from research.BackgroundTaskOutcome import BackgroundTaskOutcome
from research.ResearchEvidenceCompletionEvaluation import (
    ResearchEvidenceCompletionStatus,
)
from research.ResearchMissionGoalSatisfaction import (
    ResearchMissionGoalSatisfactionStatus,
)
from research.ResearchMissionRecoveryCheckpoint import ResearchMissionRecoveryCheckpoint


class ResearchMissionCompletionReadinessStatus(StrEnum):
    """Finite, non-mutating classes of remaining mission work."""

    READY = "ready"
    NOT_READY_EVIDENCE = "not_ready_evidence"
    NOT_READY_CONFLICT = "not_ready_conflict"
    NOT_READY_BOUNDARY = "not_ready_boundary"
    NOT_READY_BUDGET = "not_ready_budget"
    NOT_READY_EXECUTION = "not_ready_execution"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class ResearchMissionCompletionReadiness:
    """A derived conclusion-readiness value, never a lifecycle transition."""

    status: ResearchMissionCompletionReadinessStatus
    goal_status: ResearchMissionGoalSatisfactionStatus
    execution_outcome: BackgroundTaskOutcome
    contradiction_outcome: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.status, ResearchMissionCompletionReadinessStatus):
            raise ResearchError("Research mission completion readiness is invalid.")
        if not isinstance(self.goal_status, ResearchMissionGoalSatisfactionStatus):
            raise ResearchError("Research mission readiness goal status is invalid.")
        if not isinstance(self.execution_outcome, BackgroundTaskOutcome):
            raise ResearchError(
                "Research mission readiness execution outcome is invalid."
            )
        if self.contradiction_outcome not in {
            "",
            "unresolved",
            "structurally_clarified",
        }:
            raise ResearchError(
                "Research mission readiness contradiction state is invalid."
            )
        if (
            self.status is ResearchMissionCompletionReadinessStatus.READY
            and self.goal_status is not ResearchMissionGoalSatisfactionStatus.SATISFIED
        ):
            raise ResearchError("Ready mission conclusion lacks satisfied goal state.")

    @property
    def ready(self) -> bool:
        """Whether the bounded mission is ready for the user to conclude."""
        return self.status is ResearchMissionCompletionReadinessStatus.READY

    def summary(self) -> str:
        """Use status wording that never asserts universal truth or closure."""
        labels = {
            ResearchMissionCompletionReadinessStatus.READY: (
                "Ready for bounded user conclusion"
            ),
            ResearchMissionCompletionReadinessStatus.NOT_READY_EVIDENCE: (
                "Not ready: canonical evidence remains incomplete"
            ),
            ResearchMissionCompletionReadinessStatus.NOT_READY_CONFLICT: (
                "Not ready: a canonical conflict remains unresolved"
            ),
            ResearchMissionCompletionReadinessStatus.NOT_READY_BOUNDARY: (
                "Not ready: an existing authority or execution boundary stopped work"
            ),
            ResearchMissionCompletionReadinessStatus.NOT_READY_BUDGET: (
                "Not ready: cumulative approved budget was exhausted"
            ),
            ResearchMissionCompletionReadinessStatus.NOT_READY_EXECUTION: (
                "Not ready: execution did not reach a bounded conclusion"
            ),
            ResearchMissionCompletionReadinessStatus.FAILED: (
                "Not ready: execution failed"
            ),
            ResearchMissionCompletionReadinessStatus.CANCELLED: (
                "Not ready: execution was cancelled"
            ),
        }
        return labels[self.status]


def evaluate_mission_completion_readiness(
    goal_status: ResearchMissionGoalSatisfactionStatus,
    evidence_status: ResearchEvidenceCompletionStatus,
    execution_outcome: BackgroundTaskOutcome,
    checkpoint: ResearchMissionRecoveryCheckpoint | None = None,
) -> ResearchMissionCompletionReadiness:
    """Classify conclusion readiness from existing typed canonical state only."""
    if not isinstance(goal_status, ResearchMissionGoalSatisfactionStatus):
        raise ResearchError("Research mission readiness goal status is invalid.")
    if not isinstance(evidence_status, ResearchEvidenceCompletionStatus):
        raise ResearchError("Research mission readiness evidence status is invalid.")
    if not isinstance(execution_outcome, BackgroundTaskOutcome):
        raise ResearchError("Research mission readiness execution outcome is invalid.")
    if checkpoint is not None and not isinstance(
        checkpoint, ResearchMissionRecoveryCheckpoint
    ):
        raise ResearchError("Research mission readiness checkpoint is invalid.")

    contradiction_outcome = checkpoint.contradiction_outcome if checkpoint else ""
    # Structural clarification is not a verified resolution, and a legacy
    # checkpoint may record the conflict only in its semantic relation.
    pending_conflict = bool(
        checkpoint is not None
        and (
            checkpoint.contradiction_initial_relation == "possible_conflict"
            or checkpoint.semantic_relation == "possible_conflict"
        )
    )
    if goal_status is ResearchMissionGoalSatisfactionStatus.SATISFIED:
        status = ResearchMissionCompletionReadinessStatus.READY
    elif goal_status is ResearchMissionGoalSatisfactionStatus.CANCELLED:
        status = ResearchMissionCompletionReadinessStatus.CANCELLED
    elif goal_status is ResearchMissionGoalSatisfactionStatus.FAILED:
        status = ResearchMissionCompletionReadinessStatus.FAILED
    elif goal_status is ResearchMissionGoalSatisfactionStatus.BLOCKED:
        status = ResearchMissionCompletionReadinessStatus.NOT_READY_BOUNDARY
    elif goal_status is ResearchMissionGoalSatisfactionStatus.BUDGET_LIMITED:
        status = ResearchMissionCompletionReadinessStatus.NOT_READY_BUDGET
    elif (
        pending_conflict
        or contradiction_outcome == "unresolved"
        or evidence_status is ResearchEvidenceCompletionStatus.CONFLICTING
    ):
        status = ResearchMissionCompletionReadinessStatus.NOT_READY_CONFLICT
    elif execution_outcome is BackgroundTaskOutcome.INTERRUPTED:
        status = ResearchMissionCompletionReadinessStatus.NOT_READY_EXECUTION
    else:
        status = ResearchMissionCompletionReadinessStatus.NOT_READY_EVIDENCE

    return ResearchMissionCompletionReadiness(
        status=status,
        goal_status=goal_status,
        execution_outcome=execution_outcome,
        contradiction_outcome=contradiction_outcome,
    )
