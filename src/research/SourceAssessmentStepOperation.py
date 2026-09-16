"""Explicit authored source assessment for one research-plan step.

Records one assessment through the existing
`ResearchRunManager.record_source_assessment` path. No second assessment
implementation exists, and the manager keeps enforcing that the document is an
accepted source on the run, that referenced evidence belongs to it, and that a
superseded assessment is valid.

Manual assessment text and labels remain authored. An explicitly scoped mission
may derive a grounding-only assessment with trust left UNASSESSED; successful
fetching or acceptance never promotes trust. No model runs in this operation.

Information trust describes confidence in what a source says. It never grants
the source's text instruction authority, and it is neither evidence nor claim
verification nor a statement that the source is correct.
"""

from __future__ import annotations

from core.Exceptions import ResearchError
from research.ResearchPlanExecutionContext import ResearchPlanExecutionContext
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepOperationResult import ResearchPlanStepOperationResult
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSourceAssessmentRecord import identical_unjudged_assessment

_ASSESSMENT_BOUNDARY = (
    "Authored assessment only: not evidence, not claim verification, not proof "
    "the source is correct, and never instruction authority."
)


class SourceAssessmentStepOperation:
    """Record one authored assessment for an already-accepted source."""

    def __init__(self, research_run_manager: ResearchRunManager) -> None:
        self._research_run_manager = research_run_manager

    @property
    def operation_name(self) -> str:
        return "source_assessment"

    def run(
        self,
        step: ResearchPlanStep,
        context: ResearchPlanExecutionContext,
    ) -> ResearchPlanStepOperationResult:
        """Record the one authorized assessment, or fail honestly."""
        authorization = step.assessment_authorization
        if authorization is None:
            raise ResearchError(
                "Source assessment requires an explicit assessment authorization."
            )
        run_id = context.research_run_id
        if run_id is None:
            raise ResearchError("Source assessment requires a bound research run.")
        run = self._research_run_manager.get(run_id)
        if run.status.terminal:
            raise ResearchError(
                "Research run is closed and cannot record new assessments."
            )
        self._raise_if_cancelled(context)
        if authorization.supersedes_assessment_id is None:
            # A superseding write is already refused once its target has been
            # superseded.  A first assessment has no such guard, so an attempt
            # that saved it, died before the step was recorded and was ruled not
            # performed would add an identical second current assessment.
            existing = identical_unjudged_assessment(
                run.assessments,
                authorization.document_id,
                authorization.evidence_ids,
                authorization.text,
                authorization.information_trust,
            )
            if existing is not None:
                raise ResearchError(
                    "This exact assessment is already recorded as "
                    f"{existing.assessment_id} in this run; it was not recorded again."
                )

        updated = self._research_run_manager.record_source_assessment(
            run_id,
            authorization.document_id,
            list(authorization.evidence_ids),
            authorization.text,
            authorization.supersedes_assessment_id,
            authorization.information_trust,
        )
        recorded = updated.assessments[-1]
        superseded = (
            f" superseding {recorded.supersedes_assessment_id}"
            if recorded.supersedes_assessment_id
            else ""
        )
        return ResearchPlanStepOperationResult(
            performed=True,
            assessment_id=recorded.assessment_id,
            detail=(
                f"Recorded assessment {recorded.assessment_id} for document "
                f"{recorded.source_document_id} in run {run_id}{superseded}: "
                f"authored trust '{recorded.information_trust.value}' over "
                f"{len(recorded.evidence_ids)} evidence reference(s). "
                f"{_ASSESSMENT_BOUNDARY}"
            ),
        )

    @staticmethod
    def _raise_if_cancelled(context: ResearchPlanExecutionContext) -> None:
        if context.cancelled:
            raise ResearchError("Source assessment was cancelled.")
