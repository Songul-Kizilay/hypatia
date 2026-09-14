"""Derived mission outcome, keeping execution and goal satisfaction separate."""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.BackgroundTaskOutcome import BackgroundTaskOutcome, outcome_for
from research.ResearchAutonomyResult import AutonomyStopReason
from research.ResearchEvidenceCompletionEvaluation import (
    ResearchEvidenceCompletionEvaluation,
    evaluate_evidence_completion,
)
from research.ResearchRun import ResearchRun


@dataclass(frozen=True, slots=True)
class ResearchMissionOutcome:
    """Read-only summary of a bounded execution and its evidence readiness.

    ``execution_outcome`` can be complete while ``goal_satisfied`` is false.
    No current bounded evaluator declares a research question satisfied, so the
    latter is deliberately always false until a separately authorized,
    evidence-grounded goal-satisfaction contract exists.
    """

    execution_outcome: BackgroundTaskOutcome
    evidence_evaluation: ResearchEvidenceCompletionEvaluation
    goal_satisfied: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.execution_outcome, BackgroundTaskOutcome):
            raise ResearchError("Research mission execution outcome is invalid.")
        if not isinstance(
            self.evidence_evaluation, ResearchEvidenceCompletionEvaluation
        ):
            raise ResearchError("Research mission evidence evaluation is invalid.")
        if self.goal_satisfied:
            raise ResearchError(
                "Research mission goal satisfaction is not available in this runtime."
            )

    def summary(self) -> str:
        """State the distinction without interpreting evidence as truth."""
        return (
            f"Execution outcome: {self.execution_outcome.value}. "
            f"Evidence readiness: {self.evidence_evaluation.summary()}. "
            "Mission goal satisfaction: not declared."
        )


def mission_outcome_for(
    run: ResearchRun,
    stop_reason: AutonomyStopReason | str,
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
    return ResearchMissionOutcome(
        execution_outcome=outcome_for(normalized_stop),
        evidence_evaluation=evaluate_evidence_completion(run, normalized_stop),
    )
