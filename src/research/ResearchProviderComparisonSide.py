"""One provider's half of a comparison, kept whole rather than made symmetrical.

The two providers return different things. A Crossref candidate is a paper with a
venue and a year; an NVD candidate is a vulnerability with a status, weaknesses
and severity metrics scored by several parties. Forcing those into matching
columns would mean either dropping what makes each one useful or inventing empty
fields on the other side, and an empty `CVE` column beside a scholarly paper
reads like a missing value rather than an inapplicable one.

So each side carries its own candidates in their own shape, ranked by the common
ranker **within this side only**. There is no global rank across the two. A
combined ordering would put one provider's result at number one, and a number one
across providers is a verdict about providers wearing the clothes of a sort
order.

A side that has not run yet says so. It is not an empty result set: nobody has
asked, and rendering "0 candidates" for a step nobody advanced would report a
finding where there is only a pending press. A provider-attributed failure is a
third state: attempted but without a discovery result.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.RankedResearchSourceCandidate import RankedResearchSourceCandidate

MAX_COMPARISON_SIDE_CANDIDATES = 10


@dataclass(frozen=True, slots=True)
class ResearchProviderComparisonSide:
    """Report what one provider produced, in that provider's own terms."""

    provider: str
    discovery_id: str = ""
    ranked: tuple[RankedResearchSourceCandidate, ...] = ()
    accepted_count: int = 0
    assessed_count: int = 0
    failed: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.provider, str) or not self.provider.strip():
            raise ResearchError("A comparison side needs a provider.")
        if not isinstance(self.discovery_id, str):
            raise ResearchError("A comparison side discovery ID must be text.")
        if not isinstance(self.ranked, tuple):
            raise ResearchError("A comparison side needs an immutable candidate tuple.")
        if len(self.ranked) > MAX_COMPARISON_SIDE_CANDIDATES:
            raise ResearchError("A comparison side carries too many candidates.")
        if not all(
            isinstance(entry, RankedResearchSourceCandidate) for entry in self.ranked
        ):
            raise ResearchError("A comparison side candidate is invalid.")
        for name in ("accepted_count", "assessed_count"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ResearchError(f"A comparison side {name} must be whole.")
        if self.assessed_count > self.accepted_count:
            raise ResearchError("More sources were assessed than accepted.")
        if not isinstance(self.failed, bool):
            raise ResearchError("A comparison side failure flag must be boolean.")
        # A side with candidates but no discovery would be results from nowhere.
        if self.ranked and not self.discovery_id.strip():
            raise ResearchError("A comparison side must name its discovery.")
        if self.failed and self.discovery_id.strip():
            raise ResearchError("A comparison side cannot be complete and failed.")
        object.__setattr__(self, "provider", self.provider.strip())
        object.__setattr__(self, "discovery_id", self.discovery_id.strip())

    @property
    def completed(self) -> bool:
        """Say whether this provider was actually asked yet."""
        return bool(self.discovery_id)

    @property
    def candidate_count(self) -> int:
        """Return how many candidates this provider returned."""
        return len(self.ranked)

    def lines(self) -> tuple[str, ...]:
        """Render this side, provenance intact, without a cross-provider rank."""
        if not self.completed:
            if self.failed:
                return (
                    f"{self.provider}: failed — this provider was attempted but "
                    "did not produce a discovery record.",
                )
            return (
                f"{self.provider}: pending — this step has not been advanced yet, "
                "which is not the same as returning nothing.",
            )
        rendered = [
            f"{self.provider}: complete (discovery {self.discovery_id})",
            f"  candidates: {self.candidate_count}",
            f"  accepted: {self.accepted_count}",
            f"  assessed: {self.assessed_count}",
        ]
        if not self.ranked:
            rendered.append("  This provider returned no candidates for the question.")
        for entry in self.ranked:
            reasons = ", ".join(reason.value for reason in entry.relevance.reasons)
            rendered.append(
                f"  #{entry.relevance_rank} within {self.provider} "
                f"(provider rank {entry.provider_rank}) "
                f"[{entry.relevance.category.value} {entry.relevance.score}] "
                f"{entry.candidate.title}"
            )
            rendered.append(f"      {entry.candidate.url}")
            record = entry.candidate.vulnerability
            if record is not None:
                rendered.extend(f"      {line}" for line in record.lines())
            elif entry.candidate.container or entry.candidate.published_year:
                rendered.append(
                    f"      {entry.candidate.container or 'venue unknown'}"
                    f" · {entry.candidate.published_year or 'year unknown'}"
                )
            if reasons:
                rendered.append(f"      relevance reasons: {reasons}")
        return tuple(rendered)
