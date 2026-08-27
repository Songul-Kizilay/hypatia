"""Find genuinely aligned provider observations in persisted research runs.

A run qualifies only when both Crossref and NVD have a discovery whose recorded
query exactly equals the run's canonical question.  Merely finding both provider
names somewhere in a run is not enough to claim a same-question comparison.
"""

from __future__ import annotations

from collections.abc import Iterable

from core.Exceptions import ResearchError
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchPairedProviderQualityComparison import (
    ResearchPairedProviderQualityComparison,
)
from research.ResearchPairedProviderQualityReport import (
    MAX_REPORTED_PAIRED_QUESTIONS,
    ResearchPairedProviderQualityReport,
)
from research.ResearchProviderQualityEvaluator import ResearchProviderQualityEvaluator
from research.ResearchQueryCategory import category_of
from research.ResearchRun import ResearchRun

_PROVIDERS = (
    ResearchDiscoveryProviderName.CROSSREF.value,
    ResearchDiscoveryProviderName.NVD.value,
)


class ResearchPairedProviderQualityEvaluator:
    """Describe paired observations and leave every provider decision untouched."""

    def __init__(
        self, quality_evaluator: ResearchProviderQualityEvaluator | None = None
    ) -> None:
        self._quality_evaluator = (
            quality_evaluator or ResearchProviderQualityEvaluator()
        )

    def evaluate(
        self, runs: Iterable[ResearchRun]
    ) -> ResearchPairedProviderQualityReport:
        materialised = list(runs)
        if not all(isinstance(run, ResearchRun) for run in materialised):
            raise ResearchError("Paired provider quality evaluation requires runs.")

        eligible = [run for run in materialised if _is_same_question_pair(run)]
        eligible.sort(key=lambda run: (run.created_at, run.run_id))
        comparisons = tuple(
            self._comparison(run) for run in eligible[:MAX_REPORTED_PAIRED_QUESTIONS]
        )
        return ResearchPairedProviderQualityReport(
            comparisons=comparisons,
            eligible_pair_count=len(eligible),
        )

    def _comparison(self, run: ResearchRun) -> ResearchPairedProviderQualityComparison:
        category = category_of(run.question)
        quality = self._quality_evaluator.evaluate([run])
        by_provider = {
            profile.provider: profile
            for profile in quality.profiles
            if profile.category is category
        }
        sides = tuple(by_provider[provider] for provider in _PROVIDERS)
        return ResearchPairedProviderQualityComparison(
            run_id=run.run_id,
            question=run.question,
            category=category,
            sides=sides,
            ambiguous_attribution_count=quality.ambiguous_attribution_count,
            unattributed_assessed_count=quality.unattributed_assessed_count,
        )


def _is_same_question_pair(run: ResearchRun) -> bool:
    providers = {
        discovery.provider
        for discovery in run.discoveries
        if discovery.query == run.question
    }
    return all(provider in providers for provider in _PROVIDERS)
