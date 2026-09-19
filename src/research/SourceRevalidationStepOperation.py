"""One explicit re-fetch of one bound source observation.

This operation deliberately composes the existing safe HTTPS fetch pipeline and
the canonical source-acceptance transaction.  The run manager commits the new
normal observation, its revalidation provenance and its hash-derived relation
together.  It never consults temporal history to decide whether to run and never
makes a model call.

Authority is the approved step alone: an old observation is not permission to
fetch again, and a revalidation is not a freshness conclusion.  A durable
revalidation already recorded for the bound prior observation is never fetched
again; ``recorded_result`` lets a restarted execution recognise its own
committed result without any external call.
"""

from __future__ import annotations

from core.Exceptions import KnowledgeError, ResearchError
from research.PlanSourceFetcher import fetch_plan_source
from research.ResearchPlanExecutionContext import ResearchPlanExecutionContext
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepCapability import ResearchPlanStepCapability as Cap
from research.ResearchPlanStepOperationResult import (
    MAX_RESEARCH_STEP_OPERATION_DETAIL_CHARACTERS,
    ResearchPlanStepOperationResult,
)
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSourceAcceptance import AcceptsResearchSource
from research.ResearchSourceFetcher import ResearchSourceFetcher
from research.SourceRevalidationStepBinding import SourceRevalidationStepBinding


class SourceRevalidationStepOperation:
    """Fetch and accept exactly one already-approved source observation once."""

    operation_name = "source_revalidation"

    def __init__(
        self,
        source_fetcher: ResearchSourceFetcher,
        acceptance_service: AcceptsResearchSource,
        research_run_manager: ResearchRunManager,
    ) -> None:
        self._source_fetcher = source_fetcher
        self._acceptance_service = acceptance_service
        self._research_run_manager = research_run_manager

    def run(
        self,
        step: ResearchPlanStep,
        context: ResearchPlanExecutionContext,
    ) -> ResearchPlanStepOperationResult:
        """Perform one bound revalidation or decline before reaching a provider."""
        binding = step.source_revalidation_binding
        if (
            step.capability is not Cap.SOURCE_REVALIDATION
            or not isinstance(binding, SourceRevalidationStepBinding)
            or context.research_run_id is None
            or context.execution_id is None
            or context.target_binding is not None
            or context.cancelled
        ):
            return self._declined("Exact revalidation authority is unavailable.")
        try:
            binding.__post_init__()
            if binding.research_run_id != context.research_run_id:
                return self._declined("Revalidation run binding differs.")
            run = self._research_run_manager.get(context.research_run_id)
            if run.status.terminal or len(run.sources) >= binding.max_sources:
                return self._declined(
                    "Revalidation source capacity or run state does not permit work."
                )
            prior = next(
                (
                    source
                    for source in run.sources
                    if source.observation_id == binding.prior_observation_id
                ),
                None,
            )
            if (
                prior is None
                or prior.requested_url is None
                or prior.content_sha256 is None
                or prior.requested_url != binding.requested_url
            ):
                return self._declined(
                    "Revalidation prior observation is missing or changed."
                )
            if self._research_run_manager.recorded_revalidation(
                run.run_id, binding.prior_observation_id
            ) is not None or any(
                record.record.earlier_run_id == run.run_id
                and record.record.earlier_observation_id == prior.observation_id
                and record.record.later_run_id == run.run_id
                for record in self._research_run_manager.source_revalidations()
            ):
                return self._declined(
                    "Revalidation was already recorded for that source; it is "
                    "never fetched again."
                )
        except ResearchError:
            return self._declined("Revalidation canonical binding is unavailable.")
        try:
            source = fetch_plan_source(
                binding.requested_url, context, self._source_fetcher
            )
        except ResearchError:
            self._record_failure(context.research_run_id)
            raise
        if context.cancelled:
            raise ResearchError("Source revalidation was cancelled.")
        if not source.content.strip():
            self._record_failure(context.research_run_id)
            raise ResearchError("Revalidated source content was empty.")
        try:
            accepted = self._acceptance_service.accept(
                source,
                context.research_run_id,
                requested_url=binding.requested_url,
                revalidation_prior_observation_id=binding.prior_observation_id,
                revalidation_execution_id=context.execution_id,
            )
        except KnowledgeError as error:
            self._record_failure(context.research_run_id)
            raise ResearchError("Research source indexing failed.") from error
        if (
            not accepted.accepted
            or accepted.run is None
            or accepted.document_id is None
        ):
            return ResearchPlanStepOperationResult(
                performed=True,
                succeeded=False,
                detail=(
                    "Revalidation acceptance transaction ran and did not add a "
                    "new source observation."
                ),
            )
        recorded = self._research_run_manager.recorded_revalidation(
            binding.research_run_id, binding.prior_observation_id
        )
        if (
            recorded is None
            or recorded[0].document_id != accepted.document_id
            or recorded[0].revalidation_execution_id != context.execution_id
            or recorded[0].observation_id is None
        ):
            raise ResearchError("Revalidation acceptance did not retain its relation.")
        later, relation = recorded
        later_id = later.observation_id
        assert later_id is not None
        return ResearchPlanStepOperationResult(
            performed=True,
            detail=_detail(
                "Revalidated",
                binding.prior_observation_id,
                later_id,
                relation.outcome.value,
                "",
            ),
            source_observation_id=later_id,
            source_revalidation_id=relation.revalidation_id,
        )

    def recorded_result(
        self,
        step: ResearchPlanStep,
        context: ResearchPlanExecutionContext,
    ) -> ResearchPlanStepOperationResult | None:
        """Return this exact step's durably committed result, or nothing.

        Read-only and local: no fetch, no acceptance, no write.  A result is
        returned only when the run holds a revalidation of the bound prior
        observation that this same execution recorded, together with its
        relation; anything less is not provable and yields ``None``.
        """
        binding = step.source_revalidation_binding
        if (
            step.capability is not Cap.SOURCE_REVALIDATION
            or not isinstance(binding, SourceRevalidationStepBinding)
            or context.research_run_id is None
            or context.execution_id is None
            or binding.research_run_id != context.research_run_id
        ):
            return None
        try:
            recorded = self._research_run_manager.recorded_revalidation(
                binding.research_run_id, binding.prior_observation_id
            )
        except ResearchError:
            return None
        if recorded is None:
            return None
        later, relation = recorded
        if (
            later.revalidation_execution_id != context.execution_id
            or later.requested_url != binding.requested_url
            or later.observation_id is None
        ):
            return None
        return ResearchPlanStepOperationResult(
            performed=True,
            detail=_detail(
                "Recovered the durably recorded revalidation of",
                binding.prior_observation_id,
                later.observation_id,
                relation.outcome.value,
                " No second fetch was made.",
            ),
            source_observation_id=later.observation_id,
            source_revalidation_id=relation.revalidation_id,
        )

    def _record_failure(self, run_id: str) -> None:
        try:
            self._research_run_manager.record_failure(
                run_id, "source_load", "Research source revalidation failed."
            )
        except ResearchError:
            return

    @staticmethod
    def _declined(detail: str) -> ResearchPlanStepOperationResult:
        return ResearchPlanStepOperationResult(
            performed=False, succeeded=False, detail=detail
        )


def _detail(verb: str, prior_id: str, later_id: str, outcome: str, note: str) -> str:
    """Name both exact observations when they fit the bounded step detail."""
    tail = (
        f"; recorded {outcome}.{note} This is a content relation, not a source "
        "freshness conclusion."
    )
    detail = f"{verb} observation {prior_id} as {later_id}{tail}"
    if len(detail) <= MAX_RESEARCH_STEP_OPERATION_DETAIL_CHARACTERS:
        return detail
    # Exact IDs still travel in the result's identity fields.
    return f"{verb} the bound observation{tail}"
