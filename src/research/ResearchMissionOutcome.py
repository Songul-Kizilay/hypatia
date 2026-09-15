"""Derived mission outcome, keeping execution and goal satisfaction separate."""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.BackgroundTaskOutcome import BackgroundTaskOutcome, outcome_for
from research.ResearchAutonomyResult import AutonomyStopReason
from research.ResearchComparisonReviewRecord import (
    ResearchComparisonReviewDecision,
    ResearchComparisonReviewRecord,
    current_comparison_review,
)
from research.ResearchEvidenceCompletionEvaluation import (
    ResearchEvidenceCompletionEvaluation,
    evaluate_evidence_completion,
)
from research.ResearchMissionCompletionReadiness import (
    ResearchMissionCompletionReadiness,
    evaluate_mission_completion_readiness,
)
from research.ResearchMissionGoalSatisfaction import (
    ResearchMissionGoalSatisfaction,
    evaluate_mission_goal_satisfaction,
)
from research.ResearchMissionRecoveryCheckpoint import ResearchMissionRecoveryCheckpoint
from research.ResearchRun import ResearchRun


@dataclass(frozen=True, slots=True)
class ResearchMissionOutcome:
    """Read-only summary of a bounded execution and its evidence readiness.

    ``execution_outcome`` can be complete while the bounded mission goal is
    still unresolved.  ``goal_satisfaction`` is an evidence-only assessment,
    not a lifecycle transition or universal truth claim.
    """

    execution_outcome: BackgroundTaskOutcome
    evidence_evaluation: ResearchEvidenceCompletionEvaluation
    goal_satisfaction: ResearchMissionGoalSatisfaction
    completion_readiness: ResearchMissionCompletionReadiness

    def __post_init__(self) -> None:
        if not isinstance(self.execution_outcome, BackgroundTaskOutcome):
            raise ResearchError("Research mission execution outcome is invalid.")
        if not isinstance(
            self.evidence_evaluation, ResearchEvidenceCompletionEvaluation
        ):
            raise ResearchError("Research mission evidence evaluation is invalid.")
        if not isinstance(self.goal_satisfaction, ResearchMissionGoalSatisfaction):
            raise ResearchError("Research mission goal satisfaction is invalid.")
        if not isinstance(
            self.completion_readiness, ResearchMissionCompletionReadiness
        ):
            raise ResearchError("Research mission completion readiness is invalid.")

    @property
    def goal_satisfied(self) -> bool:
        """Keep the boolean convenience view, scoped to the bounded mission."""
        return self.goal_satisfaction.satisfied

    def summary(self) -> str:
        """State the distinction without interpreting evidence as truth."""
        return (
            f"Execution outcome: {self.execution_outcome.value}. "
            f"Evidence readiness: {self.evidence_evaluation.summary()}. "
            f"Mission goal satisfaction: {self.goal_satisfaction.summary()}. "
            f"Mission completion readiness: {self.completion_readiness.summary()}."
        )


def mission_comparison_review(
    run: ResearchRun,
    checkpoint: ResearchMissionRecoveryCheckpoint | None,
) -> ResearchComparisonReviewRecord | None:
    """Return the current operator review of the mission's retained comparison.

    The note is named by the durable checkpoint, and the review must still
    cite that note's exact evidence.  Nothing is read from note prose.
    """
    if checkpoint is None or not checkpoint.semantic_note_id:
        return None
    note = next(
        (
            value
            for value in run.comparison_notes
            if value.note_id == checkpoint.semantic_note_id
        ),
        None,
    )
    review = current_comparison_review(
        run.comparison_reviews, checkpoint.semantic_note_id
    )
    if note is None or review is None or review.evidence_ids != note.evidence_ids:
        return None
    return review


def supporting_comparison_review(
    run: ResearchRun,
    checkpoint: ResearchMissionRecoveryCheckpoint | None,
) -> ResearchComparisonReviewRecord | None:
    """Return the review that explicitly supports a tentative agreement, if any."""
    if (
        checkpoint is None
        or checkpoint.semantic_relation != "possible_agreement"
        or checkpoint.contradiction_initial_relation
    ):
        return None
    review = mission_comparison_review(run, checkpoint)
    if (
        review is None
        or review.decision is not ResearchComparisonReviewDecision.SUPPORTED
    ):
        return None
    return review


def mission_outcome_for(
    run: ResearchRun,
    stop_reason: AutonomyStopReason | str,
    checkpoint: ResearchMissionRecoveryCheckpoint | None = None,
) -> ResearchMissionOutcome:
    """Project existing canonical facts into one non-mutating mission outcome."""
    if not isinstance(run, ResearchRun):
        raise ResearchError("Research mission outcome requires a research run.")
    if isinstance(stop_reason, AutonomyStopReason):
        normalized_stop = stop_reason
    elif isinstance(stop_reason, str) and stop_reason.strip():
        try:
            normalized_stop = AutonomyStopReason(stop_reason.strip())
        except ValueError as error:
            raise ResearchError(
                "Research mission outcome stop reason is invalid."
            ) from error
    else:
        raise ResearchError("Research mission outcome stop reason is invalid.")
    execution_outcome = outcome_for(normalized_stop)
    evidence_evaluation = evaluate_evidence_completion(run, normalized_stop)
    support = supporting_comparison_review(run, checkpoint)
    goal_satisfaction = evaluate_mission_goal_satisfaction(
        execution_outcome,
        evidence_evaluation,
        checkpoint,
        supported_by_review_id=support.review_id if support else "",
    )
    return ResearchMissionOutcome(
        execution_outcome=execution_outcome,
        evidence_evaluation=evidence_evaluation,
        goal_satisfaction=goal_satisfaction,
        completion_readiness=evaluate_mission_completion_readiness(
            goal_satisfaction.status,
            evidence_evaluation.status,
            execution_outcome,
            checkpoint,
        ),
    )
