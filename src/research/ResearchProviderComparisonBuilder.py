"""Read one run's two discovery records back as a side-by-side comparison.

Nothing is stored to make this possible. The run already holds one discovery
record per provider, each naming its provider and its candidates, so the report
is a projection of state that exists rather than a second record of it.

What this deliberately does not claim is intent. A run holding a Crossref
discovery and an NVD discovery for its question looks the same whether the
operator approved one two-step comparison plan or ran the two searches weeks
apart, because nothing in the canonical record distinguishes them. Rather than
invent a marker that only one code path would set — which would silently relabel
every existing run as unintentional and mean nothing about the data either way —
this describes what the run contains and leaves the word "deliberate" out of it.

Ranking stays inside each side. The common ranker runs twice, once per provider,
and the two lists are never merged: a single order across providers would decide
the comparison the report exists to leave open.
"""

from __future__ import annotations

from core.Exceptions import ResearchError
from research.RankedResearchSourceDiscovery import ranked_candidates
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchProviderComparisonReport import ResearchProviderComparisonReport
from research.ResearchProviderComparisonSide import (
    MAX_COMPARISON_SIDE_CANDIDATES,
    ResearchProviderComparisonSide,
)
from research.ResearchQueryCategory import category_of
from research.ResearchRun import ResearchRun
from research.ResearchSourceAssessmentRecord import ResearchSourceAssessmentRecord
from research.ResearchSourceDiscoveryRecord import ResearchSourceDiscoveryRecord
from research.SourceIdentity import identity_of

DISCOVERY_FAILURE_STAGE = "source_discovery"


class ResearchProviderComparisonBuilder:
    """Project one run's discoveries as two independently ranked sides."""

    def build(
        self,
        run: ResearchRun,
        providers: tuple[ResearchDiscoveryProviderName, ...] = (
            ResearchDiscoveryProviderName.CROSSREF,
            ResearchDiscoveryProviderName.NVD,
        ),
    ) -> ResearchProviderComparisonReport:
        """Return both sides of this run's question, preferring neither."""
        if not isinstance(run, ResearchRun):
            raise ResearchError("A provider comparison requires a research run.")
        if not isinstance(providers, tuple) or not providers:
            raise ResearchError("A provider comparison requires named providers.")

        accepted = {
            identity_of(source.url): source.document_id for source in run.sources
        }
        assessed = _assessed_documents(run)
        latest = _latest_discovery_by_provider(run)

        return ResearchProviderComparisonReport(
            run_id=run.run_id,
            question=run.question,
            category=category_of(run.question),
            sides=tuple(
                _side(provider.value, latest.get(provider.value), accepted, assessed)
                for provider in providers
            ),
            failed_discovery_count=sum(
                1
                for failure in run.failures
                if failure.stage == DISCOVERY_FAILURE_STAGE
            ),
        )


def _latest_discovery_by_provider(
    run: ResearchRun,
) -> dict[str, ResearchSourceDiscoveryRecord]:
    """Return each provider's most recent discovery in this run.

    The most recent, because re-asking a provider replaces what it last said
    rather than adding a second column. Older discoveries stay in the run and
    stay auditable; they simply are not this comparison.
    """
    latest: dict[str, ResearchSourceDiscoveryRecord] = {}
    for discovery in run.discoveries:
        latest[discovery.provider] = discovery
    return latest


def _assessed_documents(run: ResearchRun) -> set[str]:
    """Return the documents carrying a standing assessment."""
    superseded = {
        assessment.supersedes_assessment_id
        for assessment in run.assessments
        if assessment.supersedes_assessment_id
    }
    return {
        assessment.source_document_id
        for assessment in run.assessments
        if assessment.assessment_id not in superseded
        and isinstance(assessment, ResearchSourceAssessmentRecord)
    }


def _side(
    provider: str,
    discovery: ResearchSourceDiscoveryRecord | None,
    accepted: dict[str, str],
    assessed: set[str],
) -> ResearchProviderComparisonSide:
    if discovery is None:
        return ResearchProviderComparisonSide(provider=provider)
    ranked = ranked_candidates(discovery)[:MAX_COMPARISON_SIDE_CANDIDATES]
    documents = [
        accepted[identity]
        for entry in ranked
        if (identity := identity_of(entry.candidate.url)) in accepted
    ]
    return ResearchProviderComparisonSide(
        provider=provider,
        discovery_id=discovery.discovery_id,
        ranked=ranked,
        accepted_count=len(documents),
        assessed_count=sum(1 for document in documents if document in assessed),
    )
