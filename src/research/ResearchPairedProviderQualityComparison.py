"""One same-question provider pair, described from recorded human assessments.

This is a derived view of one research run.  It keeps both provider funnels
separate and carries the question that made them comparable.  It deliberately
contains no winner, score, recommendation, or routing decision.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchProviderQualityProfile import ResearchProviderQualityProfile
from research.ResearchQueryCategory import ResearchQueryCategory


@dataclass(frozen=True, slots=True)
class ResearchPairedProviderQualityComparison:
    """Describe two providers observed on one run's exact same question."""

    run_id: str
    question: str
    category: ResearchQueryCategory
    sides: tuple[ResearchProviderQualityProfile, ...]
    ambiguous_attribution_count: int = 0
    unattributed_assessed_count: int = 0

    def __post_init__(self) -> None:
        for name in ("run_id", "question"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ResearchError(f"A paired provider quality view needs a {name}.")
        if not isinstance(self.category, ResearchQueryCategory):
            raise ResearchError("A paired provider quality view needs a category.")
        if not isinstance(self.sides, tuple) or len(self.sides) != 2:
            raise ResearchError(
                "A paired provider quality view needs exactly two sides."
            )
        if not all(
            isinstance(side, ResearchProviderQualityProfile) for side in self.sides
        ):
            raise ResearchError("A paired provider quality side is invalid.")
        providers = [side.provider for side in self.sides]
        if len(set(providers)) != 2:
            raise ResearchError("A paired provider quality side is repeated.")
        if any(side.category is not self.category for side in self.sides):
            raise ResearchError("Paired provider quality categories must agree.")
        for name in ("ambiguous_attribution_count", "unattributed_assessed_count"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ResearchError(f"Paired provider quality {name} must be whole.")

    @property
    def assessed_count(self) -> int:
        return sum(side.assessed_count for side in self.sides)

    def lines(self) -> tuple[str, ...]:
        rendered = [
            f"Run: {self.run_id}",
            f"Question: {self.question}",
            f"Question category: {self.category.label}",
            "",
        ]
        for side in self.sides:
            rendered.extend(side.lines())
            rendered.append("")
        if self.ambiguous_attribution_count:
            rendered.append(
                "Sources returned by both providers: "
                f"{self.ambiguous_attribution_count} — excluded from both sides."
            )
        if self.unattributed_assessed_count:
            rendered.append(
                "Assessed sources returned by neither provider: "
                f"{self.unattributed_assessed_count} — excluded from both sides."
            )
        return tuple(rendered)
