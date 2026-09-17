"""Explicit authored claim creation for one research-plan step.

Records one claim through the existing `ResearchRunManager.record_claim` path.
No second claim implementation exists, and the manager keeps enforcing that
every cited evidence record belongs to the bound run, that evidence references
are unique and bounded, that the claim text is bounded, and that a superseded
claim is valid.

Epistemic state and confidence are authored, never inferred. Completing this
operation does not promote anything: a claim is recorded in exactly the state a
human declared. Nothing in the chain raises it — a fetched source is not
evidence, an accepted source is not a verified claim, and an assessment is not
claim truth.

Existing contradiction state is untouched; a claim never resolves or clears a
contradiction by being recorded.
"""

from __future__ import annotations

from core.Exceptions import ResearchError
from research.ResearchPlanExecutionContext import ResearchPlanExecutionContext
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepOperationResult import ResearchPlanStepOperationResult
from research.ResearchRunManager import ResearchRunManager

_CLAIM_BOUNDARY = (
    "Authored claim recorded in its declared state only: recording it verifies "
    "nothing and promotes nothing."
)


class ClaimCreationStepOperation:
    """Record one authored claim grounded in evidence from the bound run."""

    def __init__(self, research_run_manager: ResearchRunManager) -> None:
        self._research_run_manager = research_run_manager

    @property
    def operation_name(self) -> str:
        return "claim_creation"

    def run(
        self,
        step: ResearchPlanStep,
        context: ResearchPlanExecutionContext,
    ) -> ResearchPlanStepOperationResult:
        """Record the one authorized claim, or fail honestly."""
        authorization = step.claim_authorization
        if authorization is None:
            raise ResearchError(
                "Claim creation requires an explicit claim authorization."
            )
        run_id = context.research_run_id
        if run_id is None:
            raise ResearchError("Claim creation requires a bound research run.")
        run = self._research_run_manager.get(run_id)
        if run.status.terminal:
            raise ResearchError("Research run is closed and cannot record new claims.")
        self._raise_if_cancelled(context)

        updated = self._research_run_manager.record_claim(
            run_id,
            list(authorization.evidence_ids),
            authorization.text,
            authorization.epistemic_state,
            authorization.confidence,
            authorization.supersedes_claim_id,
        )
        recorded = updated.claims[-1]
        superseded = (
            f" superseding {recorded.supersedes_claim_id}"
            if recorded.supersedes_claim_id
            else ""
        )
        return ResearchPlanStepOperationResult(
            performed=True,
            detail=(
                f"Recorded claim {recorded.claim_id} in run {run_id}{superseded}: "
                f"authored state '{recorded.epistemic_state.value}', authored "
                f"confidence '{recorded.confidence.value}', citing "
                f"{len(recorded.evidence_ids)} evidence record(s) across "
                f"{len(recorded.source_document_ids)} source(s). {_CLAIM_BOUNDARY}"
            ),
        )

    @staticmethod
    def _raise_if_cancelled(context: ResearchPlanExecutionContext) -> None:
        if context.cancelled:
            raise ResearchError("Claim creation was cancelled.")
