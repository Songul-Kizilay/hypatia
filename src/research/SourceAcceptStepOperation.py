"""Explicitly authorized source acceptance for one research-plan step.

Acquires the one URL the step authorizes through the canonical
`ResearchSourceFetcher`, then runs the one canonical acceptance transaction
owned by `ResearchSourceAcceptanceService`. Neither the fetch pipeline nor the
acceptance transaction is reimplemented here, and no second content channel
exists: content flows through the canonical knowledge and source-content
architecture only.

Authorization is explicit. The URL comes only from the resolved step's
`authorized_source_url`, never from instruction text. For a reference mission,
the executor supplies the exact inspected predecessor preview under the
original digest-bound scope. That path reuses bytes instead of fetching again.
Manual steps without a preview retain their canonical acquisition behavior.

Accepted means accepted into the run's canonical source set and nothing more.
No evidence, assessment, claim, trust, or conclusion follows from it.

A transaction that genuinely runs but does not accept the source is reported as
performed work that did not succeed, never as a successful acceptance.
"""

from __future__ import annotations

from core.Exceptions import KnowledgeError, ResearchError
from research.PlanSourceFetcher import fetch_plan_source
from research.ResearchPlanExecutionContext import ResearchPlanExecutionContext
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepOperationResult import ResearchPlanStepOperationResult
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSourceAcceptance import AcceptsResearchSource
from research.ResearchSourceFetcher import ResearchSourceFetcher

MAX_REPORTED_URL_CHARACTERS = 160

_ACCEPTANCE_BOUNDARY = (
    "Accepted into the run's source set only: not evidence, not assessed, "
    "not a verified claim, and not a trusted source."
)


class SourceAcceptStepOperation:
    """Fetch one authorized source and run the canonical acceptance."""

    def __init__(
        self,
        source_fetcher: ResearchSourceFetcher,
        acceptance_service: AcceptsResearchSource,
        research_run_manager: ResearchRunManager,
    ) -> None:
        self._source_fetcher = source_fetcher
        self._acceptance_service = acceptance_service
        self._research_run_manager = research_run_manager

    @property
    def operation_name(self) -> str:
        return "source_accept"

    def run(
        self,
        step: ResearchPlanStep,
        context: ResearchPlanExecutionContext,
    ) -> ResearchPlanStepOperationResult:
        """Acquire and accept the one authorized source, or report honestly."""
        url = step.authorized_source_url
        if not url:
            raise ResearchError(
                "Source acceptance requires an explicitly authorized source URL."
            )
        run_id = context.research_run_id
        if run_id is None:
            raise ResearchError("Source acceptance requires a bound research run.")
        run = self._research_run_manager.get(run_id)
        if run.status.terminal:
            raise ResearchError("Research run is closed and cannot accept sources.")

        self._raise_if_cancelled(context)
        try:
            preview = context.source_preview
            if preview is not None:
                if (
                    preview.execution_id != context.execution_id
                    or preview.run_id != run_id
                    or preview.requested_url != url
                    or context.target_binding is not None
                ):
                    raise ResearchError("Source acceptance preview binding differs.")
                source = preview.source
            else:
                source = fetch_plan_source(url, context, self._source_fetcher)
        except ResearchError:
            self._record_failure(run_id, "Research source acquisition failed.")
            raise
        self._raise_if_cancelled(context)

        try:
            result = self._acceptance_service.accept(source, run_id)
        except KnowledgeError as error:
            self._record_failure(run_id, "Research source indexing failed.")
            raise ResearchError("Research source indexing failed.") from error

        if not result.accepted:
            return ResearchPlanStepOperationResult(
                performed=True,
                succeeded=False,
                detail=(
                    f"Source acceptance transaction ran for "
                    f"{self._reported_url(url)} and did not accept the source: "
                    f"{result.failure_reason} No source was added to the run."
                ),
            )
        return ResearchPlanStepOperationResult(
            performed=True,
            detail=(
                f"Accepted {self._reported_url(url)} into run {run_id} as "
                f"document {result.document_id}. {_ACCEPTANCE_BOUNDARY}"
            ),
        )

    def _record_failure(self, run_id: str, reason: str) -> None:
        """Preserve the failure in the run audit without masking the error."""
        try:
            self._research_run_manager.record_failure(run_id, "source_load", reason)
        except ResearchError:
            return

    @staticmethod
    def _reported_url(url: str) -> str:
        """Bound the echoed URL so detail never grows with a hostile input."""
        if len(url) <= MAX_REPORTED_URL_CHARACTERS:
            return url
        return f"{url[:MAX_REPORTED_URL_CHARACTERS]}..."

    @staticmethod
    def _raise_if_cancelled(context: ResearchPlanExecutionContext) -> None:
        if context.cancelled:
            raise ResearchError("Source acceptance was cancelled.")
