"""Bounded source discovery for one research-plan step.

Reuses the existing `ResearchSourceDiscoveryProvider` abstraction and the
`ResearchRunManager` discovery audit path. No second discovery engine exists.

One step performs exactly one bounded provider query with no retry, no
crawling, and no link following. Cancellation is checked before the query and
again before the audit record is written.

Which provider is contacted comes from the approved step, not from how this
operation was wired. That matters because the provider decides the network
target: an approval to search scholarly literature must not be spendable on a
different host, so the provider travels inside the plan digest and a step naming
a provider nobody registered fails rather than falling back to whichever one
happens to be available.

Discovery deliberately proves very little:

- a candidate source is not an accepted source
- discovered metadata is not evidence
- a discovered source is not a trusted source
- discovery succeeding is not a research conclusion

Candidates are persisted only as an unaccepted, provenance-preserving audit
record. Nothing is accepted, fetched, turned into evidence, or turned into a
claim here.
"""

from __future__ import annotations

from core.Exceptions import ResearchError
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchPlanExecutionContext import ResearchPlanExecutionContext
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepOperationResult import ResearchPlanStepOperationResult
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSourceCandidate import ResearchSourceCandidate
from research.ResearchSourceDiscoveryProvider import ResearchSourceDiscoveryProvider

DEFAULT_DISCOVERY_CANDIDATE_LIMIT = 5
MAX_DISCOVERY_CANDIDATE_LIMIT = 10

_TRUST_BOUNDARY = (
    "Candidates are unaccepted metadata: not accepted sources, not evidence, "
    "not trusted, and not a conclusion."
)


class SourceDiscoveryStepOperation:
    """Run one bounded discovery query and record its unaccepted candidates."""

    def __init__(
        self,
        discovery_provider: ResearchSourceDiscoveryProvider,
        research_run_manager: ResearchRunManager,
        *,
        candidate_limit: int = DEFAULT_DISCOVERY_CANDIDATE_LIMIT,
        providers: (
            dict[ResearchDiscoveryProviderName, ResearchSourceDiscoveryProvider] | None
        ) = None,
    ) -> None:
        if (
            isinstance(candidate_limit, bool)
            or not isinstance(candidate_limit, int)
            or not 1 <= candidate_limit <= MAX_DISCOVERY_CANDIDATE_LIMIT
        ):
            raise ResearchError("Research discovery candidate limit is invalid.")
        if providers is not None and not all(
            isinstance(name, ResearchDiscoveryProviderName) for name in providers
        ):
            raise ResearchError("A registered discovery provider name is invalid.")
        self._discovery_provider = discovery_provider
        self._providers = dict(providers or {})
        self._research_run_manager = research_run_manager
        self._candidate_limit = candidate_limit

    def _provider_for(
        self,
        step: ResearchPlanStep,
    ) -> ResearchSourceDiscoveryProvider:
        """Return the provider this exact step was approved to contact.

        A step that names none keeps the provider this operation was wired with,
        which is what every plan approved before providers were nameable meant.
        A step that names one this build cannot reach fails: quietly substituting
        another would spend an approval on a host the operator never saw.
        """
        chosen = step.discovery_provider
        if chosen is None:
            return self._discovery_provider
        provider = self._providers.get(chosen)
        if provider is None:
            raise ResearchError(
                f"Source discovery provider '{chosen.value}' is not available."
            )
        return provider

    @property
    def operation_name(self) -> str:
        return "source_discovery"

    def run(
        self,
        step: ResearchPlanStep,
        context: ResearchPlanExecutionContext,
    ) -> ResearchPlanStepOperationResult:
        """Perform one bounded discovery query, or fail honestly."""
        provider = self._provider_for(step)
        run_id = context.research_run_id
        if run_id is None:
            raise ResearchError("Source discovery requires a bound research run.")
        run = self._research_run_manager.get(run_id)
        if run.status.terminal:
            raise ResearchError(
                "Research run is closed and cannot discover new sources."
            )
        self._raise_if_cancelled(context)

        try:
            candidates = provider.discover(
                run.question,
                limit=self._candidate_limit,
            )
            self._validate(candidates)
        except ResearchError:
            self._record_failure(run_id, provider.provider_name)
            raise

        self._raise_if_cancelled(context)
        updated = self._research_run_manager.add_discovery(
            run_id,
            run.question,
            provider.provider_name,
            candidates,
        )
        provider_name = provider.provider_name
        summary = (
            f"Source discovery via '{provider_name}' returned "
            f"{len(candidates)} candidate(s) for run {updated.run_id}."
        )
        if not candidates:
            summary = f"{summary} No candidates matched this question."
        return ResearchPlanStepOperationResult(
            performed=True,
            detail=f"{summary} {_TRUST_BOUNDARY}",
        )

    def _validate(self, candidates: object) -> None:
        """Reject any provider result that breaks the bounded contract."""
        if (
            not isinstance(candidates, list)
            or len(candidates) > self._candidate_limit
            or not all(
                isinstance(candidate, ResearchSourceCandidate)
                for candidate in candidates
            )
        ):
            raise ResearchError(
                "Research source discovery provider returned invalid candidates."
            )

    def _record_failure(self, run_id: str, provider: str) -> None:
        """Preserve the failure in the run audit without masking the error."""
        try:
            self._research_run_manager.record_failure(
                run_id,
                "source_discovery",
                "Research source discovery failed.",
                provider=provider,
            )
        except ResearchError:
            return

    @staticmethod
    def _raise_if_cancelled(context: ResearchPlanExecutionContext) -> None:
        if context.cancelled:
            raise ResearchError("Source discovery was cancelled.")
