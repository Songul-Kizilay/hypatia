"""Same-question provider observations, aligned without declaring a winner."""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchPairedProviderQualityComparison import (
    ResearchPairedProviderQualityComparison,
)

MAX_REPORTED_PAIRED_QUESTIONS = 40

PAIRED_SELECTION_BIAS_NOTICE = (
    "The question is aligned, but the sources are still ones the operator chose "
    "to accept and assess. These observations are descriptive, not a controlled "
    "provider benchmark."
)

PAIRED_NO_POLICY_NOTICE = (
    "No provider was judged better, no provider was selected, no default or "
    "ranking changed, and no reputation was updated."
)


@dataclass(frozen=True, slots=True)
class ResearchPairedProviderQualityReport:
    """Report runs where both providers answered the same canonical question."""

    comparisons: tuple[ResearchPairedProviderQualityComparison, ...] = ()
    eligible_pair_count: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.comparisons, tuple):
            raise ResearchError("Paired provider quality comparisons must be a tuple.")
        if len(self.comparisons) > MAX_REPORTED_PAIRED_QUESTIONS:
            raise ResearchError("Too many paired provider quality comparisons.")
        if not all(
            isinstance(item, ResearchPairedProviderQualityComparison)
            for item in self.comparisons
        ):
            raise ResearchError("A paired provider quality comparison is invalid.")
        run_ids = [item.run_id for item in self.comparisons]
        if len(run_ids) != len(set(run_ids)):
            raise ResearchError("A paired provider quality run is reported twice.")
        if (
            isinstance(self.eligible_pair_count, bool)
            or not isinstance(self.eligible_pair_count, int)
            or self.eligible_pair_count < len(self.comparisons)
        ):
            raise ResearchError("Paired provider quality count is invalid.")

    @property
    def assessed_count(self) -> int:
        return sum(item.assessed_count for item in self.comparisons)

    def counts(self) -> dict[str, int]:
        return {
            "eligible_pair_count": self.eligible_pair_count,
            "reported_pair_count": len(self.comparisons),
            "assessed_sample_count": self.assessed_count,
        }

    def lines(self) -> tuple[str, ...]:
        if not self.comparisons:
            return (
                "No same-question Crossref and NVD pair has been recorded yet.",
                "",
                "No comparison is not a finding about either provider.",
                "",
                PAIRED_NO_POLICY_NOTICE,
            )
        rendered: list[str] = []
        for number, comparison in enumerate(self.comparisons, start=1):
            rendered.append(f"Paired question {number}")
            rendered.extend(comparison.lines())
            rendered.append("")
        omitted = self.eligible_pair_count - len(self.comparisons)
        if omitted:
            rendered.append(
                "Additional paired questions omitted from this bounded view: "
                f"{omitted}."
            )
            rendered.append("")
        rendered.extend((PAIRED_SELECTION_BIAS_NOTICE, "", PAIRED_NO_POLICY_NOTICE))
        return tuple(rendered)
