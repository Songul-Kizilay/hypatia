"""Explicit research-run closure for one plan step.

Closes the bound run through the existing
`ResearchRunManager.transition_status` path, which keeps deciding whether the
transition is allowed. This operation defines no completion rule of its own.

Reaching the last execution step never closes a run. Execution completing, the
run completing, evidence being sufficient, claims being verified, and
uncertainty being resolved are five different things, and only the second is
what this operation can achieve.

Closing a run resolves nothing. Unresolved contradictions, claims still held as
hypothesis, speculation, or unknown, and recorded failures all survive into the
final state and are reported alongside it.
"""

from __future__ import annotations

from core.Exceptions import ResearchError
from research.ResearchEpistemicState import ResearchEpistemicState
from research.ResearchPlanExecutionContext import ResearchPlanExecutionContext
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepOperationResult import ResearchPlanStepOperationResult
from research.ResearchRunManager import ResearchRunManager

_UNRESOLVED_STATES = frozenset(
    {
        ResearchEpistemicState.HYPOTHESIS,
        ResearchEpistemicState.SPECULATION,
        ResearchEpistemicState.UNKNOWN,
        ResearchEpistemicState.CONTRADICTED,
    }
)

_COMPLETION_BOUNDARY = (
    "Closing the run resolves nothing: it verifies no claim, settles no "
    "contradiction, and asserts no certainty."
)


class ResearchRunCompletionStepOperation:
    """Close the bound run under the existing lifecycle rules."""

    def __init__(self, research_run_manager: ResearchRunManager) -> None:
        self._research_run_manager = research_run_manager

    @property
    def operation_name(self) -> str:
        return "research_run_completion"

    def run(
        self,
        step: ResearchPlanStep,
        context: ResearchPlanExecutionContext,
    ) -> ResearchPlanStepOperationResult:
        """Close the run if the domain allows it, or report honestly."""
        authorization = step.completion_authorization
        if authorization is None:
            raise ResearchError(
                "Research run completion requires an explicit authorization."
            )
        run_id = context.research_run_id
        if run_id is None:
            raise ResearchError(
                "Research run completion requires a bound research run."
            )
        self._raise_if_cancelled(context)

        preview = self._research_run_manager.preview_status_transition(
            run_id,
            authorization.target_status,
        )
        if not preview.allowed:
            return ResearchPlanStepOperationResult(
                performed=True,
                succeeded=False,
                detail=(
                    f"Run {run_id} was not closed as "
                    f"'{authorization.target_status.value}': {preview.reason} "
                    "The run remains open."
                ),
            )

        updated = self._research_run_manager.transition_status(
            run_id,
            authorization.target_status,
        )
        unresolved_claims = sum(
            1 for claim in updated.claims if claim.epistemic_state in _UNRESOLVED_STATES
        )
        return ResearchPlanStepOperationResult(
            performed=True,
            detail=(
                f"Run {run_id} closed as '{updated.status.value}' with "
                f"{len(updated.sources)} source(s), {len(updated.evidence)} "
                f"evidence record(s), {len(updated.claims)} claim(s). "
                f"Retained: {unresolved_claims} unresolved claim(s), "
                f"{len(updated.claim_contradictions)} contradiction(s), "
                f"{len(updated.failures)} failure(s). {_COMPLETION_BOUNDARY}"
            ),
        )

    @staticmethod
    def _raise_if_cancelled(context: ResearchPlanExecutionContext) -> None:
        if context.cancelled:
            raise ResearchError("Research run completion was cancelled.")
