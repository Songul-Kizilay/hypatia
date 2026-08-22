"""Read-only accepted-source listing for one research-plan step.

Reads accepted sources from the canonical `ResearchRunManager` state. It makes
no network request, no LLM call, and no persistence mutation.

Listing is deliberately weak evidence of nothing. A completed listing proves
only that the accepted-source set was read. It does not mean any source content
was read, does not assess trustworthiness, and establishes no evidence or claim.
Those remain the responsibility of the existing research evidence pipeline.
"""

from __future__ import annotations

from core.Exceptions import ResearchError
from research.ResearchPlanExecutionContext import ResearchPlanExecutionContext
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepOperationResult import ResearchPlanStepOperationResult
from research.ResearchRunManager import ResearchRunManager

MAX_REPORTED_ACCEPTED_SOURCES = 3


class AcceptedSourceListingStepOperation:
    """List the accepted sources of the bound research run."""

    def __init__(self, research_run_manager: ResearchRunManager) -> None:
        self._research_run_manager = research_run_manager

    @property
    def operation_name(self) -> str:
        return "accepted_source_listing"

    def run(
        self,
        step: ResearchPlanStep,
        context: ResearchPlanExecutionContext,
    ) -> ResearchPlanStepOperationResult:
        """List accepted sources for the bound run, or fail safely."""
        del step
        run_id = context.research_run_id
        if run_id is None:
            raise ResearchError(
                "Accepted-source listing requires a bound research run."
            )
        run = self._research_run_manager.get(run_id)
        sources = run.sources
        reported = sources[:MAX_REPORTED_ACCEPTED_SOURCES]
        summary = f"Listed {len(sources)} accepted source(s) for run {run.run_id}."
        if reported:
            listed = ", ".join(source.document_id for source in reported)
            remaining = len(sources) - len(reported)
            suffix = f" (+{remaining} more)" if remaining > 0 else ""
            summary = f"{summary} Document IDs: {listed}{suffix}."
        else:
            summary = f"{summary} This run has no accepted sources yet."
        summary = (
            f"{summary} Listing only; no source content was read and no "
            "evidence was established."
        )
        return ResearchPlanStepOperationResult(performed=True, detail=summary)
