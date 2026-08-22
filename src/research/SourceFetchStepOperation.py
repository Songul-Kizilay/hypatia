"""Acquisition-only source fetch for one research-plan step.

Reuses the canonical `ResearchSourceFetcher` pipeline, so every existing
protection stays in force: public-HTTPS only, credential rejection, port
restrictions, DNS and IP validation, public-address enforcement, redirect
validation, TLS and hostname validation, response-size bounds, content-type
bounds, and encoding bounds. No second HTTP path exists here.

The URL is never chosen by this operation. It comes only from the step's
explicit `authorized_source_url`. It is never inferred from instruction text,
never taken from a discovery result, and never guessed from ranking, so a
candidate can never become a fetch target by itself.

This operation is acquisition-only. It performs no acceptance: nothing is
indexed into knowledge, no accepted-source record is written, no content
snapshot is stored, and no evidence, assessment, or claim is created. Accepting
a source remains a separate explicit contract. Because nothing is persisted,
cancellation after bytes arrive leaves no partial research state behind.

Fetched content is untrusted data with no instruction authority, and it is never
sent to a language model here.
"""

from __future__ import annotations

from core.Exceptions import ResearchError
from research.ResearchPlanExecutionContext import ResearchPlanExecutionContext
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepOperationResult import ResearchPlanStepOperationResult
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSourceFetcher import ResearchSourceFetcher

MAX_REPORTED_URL_CHARACTERS = 200

_ACQUISITION_BOUNDARY = (
    "Acquisition only: untrusted content, not accepted, not indexed, not "
    "evidence, not assessed, not a verified claim."
)


class SourceFetchStepOperation:
    """Acquire exactly one explicitly authorized source without accepting it."""

    def __init__(
        self,
        source_fetcher: ResearchSourceFetcher,
        research_run_manager: ResearchRunManager,
    ) -> None:
        self._source_fetcher = source_fetcher
        self._research_run_manager = research_run_manager

    @property
    def operation_name(self) -> str:
        return "source_fetch"

    def run(
        self,
        step: ResearchPlanStep,
        context: ResearchPlanExecutionContext,
    ) -> ResearchPlanStepOperationResult:
        """Fetch the one authorized source, or fail honestly."""
        url = step.authorized_source_url
        if not url:
            raise ResearchError(
                "Source fetch requires an explicitly authorized source URL."
            )
        run_id = context.research_run_id
        if run_id is None:
            raise ResearchError("Source fetch requires a bound research run.")
        run = self._research_run_manager.get(run_id)
        if run.status.terminal:
            raise ResearchError("Research run is closed and cannot fetch sources.")

        self._raise_if_cancelled(context)
        try:
            source = self._source_fetcher.fetch(url)
        except ResearchError:
            self._record_failure(run_id)
            raise
        self._raise_if_cancelled(context)

        if not source.content.strip():
            self._record_failure(run_id)
            raise ResearchError("Fetched source content was empty.")

        summary = (
            f"Fetched authorized source {self._reported_url(url)} for run "
            f"{run.run_id}: {source.content_type}, "
            f"{len(source.content)} character(s)."
        )
        return ResearchPlanStepOperationResult(
            performed=True,
            detail=f"{summary} {_ACQUISITION_BOUNDARY}",
        )

    def _record_failure(self, run_id: str) -> None:
        """Preserve the failure in the run audit without masking the error."""
        try:
            self._research_run_manager.record_failure(
                run_id,
                "source_load",
                "Research source acquisition failed.",
            )
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
            raise ResearchError("Source fetch was cancelled.")
