"""Explicit authored source-comparison recording for one plan step.

Records one comparison note through the existing
`ResearchRunManager.record_source_comparison_note` path. No second comparison
implementation exists, and the manager keeps enforcing the 2-to-5 accepted
source bound, evidence and assessment ownership, and text bounds.

A comparison is a description, not a verdict. This operation selects no winner,
ranks nothing, promotes no source's trust, and verifies no claim. Any judgement
lives in the authored text a human wrote.
"""

from __future__ import annotations

from core.Exceptions import ResearchError
from research.ResearchPlanExecutionContext import ResearchPlanExecutionContext
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepOperationResult import ResearchPlanStepOperationResult
from research.ResearchRunManager import ResearchRunManager

_COMPARISON_BOUNDARY = (
    "Authored comparison only: no winner selected, no ranking produced, no "
    "trust promoted, and no claim verified."
)


class SourceComparisonStepOperation:
    """Record one authored comparison across explicitly named sources."""

    def __init__(self, research_run_manager: ResearchRunManager) -> None:
        self._research_run_manager = research_run_manager

    @property
    def operation_name(self) -> str:
        return "source_comparison"

    def run(
        self,
        step: ResearchPlanStep,
        context: ResearchPlanExecutionContext,
    ) -> ResearchPlanStepOperationResult:
        """Record the one authorized comparison note, or fail honestly."""
        authorization = step.comparison_authorization
        if authorization is None:
            raise ResearchError("Source comparison requires an explicit authorization.")
        run_id = context.research_run_id
        if run_id is None:
            raise ResearchError("Source comparison requires a bound research run.")
        run = self._research_run_manager.get(run_id)
        if run.status.terminal:
            raise ResearchError(
                "Research run is closed and cannot record new comparisons."
            )
        self._raise_if_cancelled(context)

        updated = self._research_run_manager.record_source_comparison_note(
            run_id,
            list(authorization.document_ids),
            list(authorization.evidence_ids),
            list(authorization.assessment_ids),
            authorization.text,
        )
        recorded = updated.comparison_notes[-1]
        return ResearchPlanStepOperationResult(
            performed=True,
            detail=(
                f"Recorded comparison note {recorded.note_id} in run {run_id} "
                f"across {len(recorded.source_document_ids)} source(s), citing "
                f"{len(recorded.evidence_ids)} evidence record(s) and "
                f"{len(recorded.assessment_ids)} assessment(s). "
                f"{_COMPARISON_BOUNDARY}"
            ),
        )

    @staticmethod
    def _raise_if_cancelled(context: ResearchPlanExecutionContext) -> None:
        if context.cancelled:
            raise ResearchError("Source comparison recording was cancelled.")
