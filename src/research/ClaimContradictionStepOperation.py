"""Explicit confirmed claim-contradiction recording for one plan step.

Records one contradiction through the existing
`ResearchRunManager.record_claim_contradiction` path. No second contradiction
implementation exists, and the manager keeps enforcing exactly two distinct
current claims from the bound run, rejecting duplicates of an existing
relationship.

A proposal is not a contradiction. Any suggestion, including a language-model
one, stays a proposal until a human authorizes it here; nothing persists
automatically.

Recording a contradiction never rewrites either claim's text, epistemic state,
or confidence, and never decides which claim is true. It records that two
authored claims conflict and leaves the resolution to a human.
"""

from __future__ import annotations

from core.Exceptions import ResearchError
from research.ResearchPlanExecutionContext import ResearchPlanExecutionContext
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepOperationResult import ResearchPlanStepOperationResult
from research.ResearchRunManager import ResearchRunManager

_CONTRADICTION_BOUNDARY = (
    "Recorded conflict only: neither claim was edited, neither was decided "
    "true, and no claim state changed."
)


class ClaimContradictionStepOperation:
    """Record one authored contradiction between two current claims."""

    def __init__(self, research_run_manager: ResearchRunManager) -> None:
        self._research_run_manager = research_run_manager

    @property
    def operation_name(self) -> str:
        return "claim_contradiction"

    def run(
        self,
        step: ResearchPlanStep,
        context: ResearchPlanExecutionContext,
    ) -> ResearchPlanStepOperationResult:
        """Record the one authorized contradiction, or fail honestly."""
        authorization = step.contradiction_authorization
        if authorization is None:
            raise ResearchError(
                "Claim contradiction requires an explicit authorization."
            )
        run_id = context.research_run_id
        if run_id is None:
            raise ResearchError("Claim contradiction requires a bound research run.")
        run = self._research_run_manager.get(run_id)
        if run.status.terminal:
            raise ResearchError(
                "Research run is closed and cannot record new contradictions."
            )
        self._raise_if_cancelled(context)

        updated = self._research_run_manager.record_claim_contradiction(
            run_id,
            list(authorization.claim_ids),
            authorization.note,
        )
        recorded = updated.claim_contradictions[-1]
        return ResearchPlanStepOperationResult(
            performed=True,
            detail=(
                f"Recorded contradiction {recorded.contradiction_id} in run "
                f"{run_id} between claims {recorded.claim_ids[0]} and "
                f"{recorded.claim_ids[1]}, citing "
                f"{len(recorded.evidence_ids)} evidence record(s). "
                f"{_CONTRADICTION_BOUNDARY}"
            ),
        )

    @staticmethod
    def _raise_if_cancelled(context: ResearchPlanExecutionContext) -> None:
        if context.cancelled:
            raise ResearchError("Claim contradiction recording was cancelled.")
