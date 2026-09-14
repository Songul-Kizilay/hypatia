"""How well one candidate matched one query, with the reasons attached.

This is a derived annotation and nothing more. It is computed from the record a
provider already returned, it can be recomputed at any time from the same
inputs, and it is never evidence. Accepting a source, recording what it says,
and judging whether that holds are all unchanged by anything here: a high score
means the question's words are in the title, which is a reason to look, not a
reason to believe.

The score is deliberately scored over the weight that actually applied. A
candidate whose record carries no venue is measured on the components its record
can answer, so missing metadata reads as unknown rather than as a fault. What
this cannot do is compare across queries. 70 for one question and 70 for another
were computed over different denominators, and each means only that the
candidate matched its own question well.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchRelevanceCategory import ResearchRelevanceCategory
from research.ResearchRelevanceComponent import ResearchRelevanceComponent
from research.ResearchRelevanceReason import ResearchRelevanceReason
from research.ResearchRelevanceWeights import (
    DEFAULT_RELEVANCE_WEIGHTS,
    ResearchRelevanceWeights,
)

MAX_RELEVANCE_REASONS = 12


@dataclass(frozen=True, slots=True)
class ResearchSourceRelevance:
    """Hold one candidate's relevance score, band, parts, and reasons."""

    score: int
    category: ResearchRelevanceCategory
    components: tuple[ResearchRelevanceComponent, ...]
    reasons: tuple[ResearchRelevanceReason, ...]

    def __post_init__(self) -> None:
        if isinstance(self.score, bool) or not isinstance(self.score, int):
            raise ResearchError("A relevance score must be a whole number.")
        if not 0 <= self.score <= 100:
            raise ResearchError("A relevance score must be between 0 and 100.")
        if not isinstance(self.category, ResearchRelevanceCategory):
            raise ResearchError("A relevance category must be a known band.")
        if not isinstance(self.components, tuple) or not self.components:
            raise ResearchError("A relevance score must keep its components.")
        if not all(
            isinstance(component, ResearchRelevanceComponent)
            for component in self.components
        ):
            raise ResearchError("A relevance component is invalid.")
        names = [component.name for component in self.components]
        if len(names) != len(set(names)):
            raise ResearchError("A relevance component is measured twice.")
        if not isinstance(self.reasons, tuple):
            raise ResearchError("Relevance reasons must be an immutable tuple.")
        if len(self.reasons) > MAX_RELEVANCE_REASONS:
            raise ResearchError("A relevance score carries too many reasons.")
        if not all(
            isinstance(reason, ResearchRelevanceReason) for reason in self.reasons
        ):
            raise ResearchError("A relevance reason is not a known code.")
        if len(self.reasons) != len(set(self.reasons)):
            raise ResearchError("A relevance reason is repeated.")

    @classmethod
    def of(
        cls,
        components: tuple[ResearchRelevanceComponent, ...],
        reasons: tuple[ResearchRelevanceReason, ...],
        weights: ResearchRelevanceWeights = DEFAULT_RELEVANCE_WEIGHTS,
    ) -> ResearchSourceRelevance:
        """Score the applied components and place the result in a band."""
        if not isinstance(weights, ResearchRelevanceWeights):
            raise ResearchError("Relevance weights are invalid.")
        if not isinstance(components, tuple) or not components:
            raise ResearchError("A relevance score must keep its components.")
        available = sum(component.available_weight for component in components)
        earned = sum(component.contribution for component in components)
        # No applicable component means nothing could be measured, which is a
        # score of zero rather than a division by zero. It is also the honest
        # answer: nothing about this record could be compared to the question.
        score = 0 if available <= 0.0 else round(100.0 * earned / available)
        score = max(0, min(100, int(score)))
        if score >= weights.strong_score:
            category = ResearchRelevanceCategory.STRONG
        elif score >= weights.moderate_score:
            category = ResearchRelevanceCategory.MODERATE
        elif score >= weights.weak_score:
            category = ResearchRelevanceCategory.WEAK
        else:
            category = ResearchRelevanceCategory.UNRELATED
        return cls(
            score=score,
            category=category,
            components=components,
            reasons=reasons,
        )

    def component(self, name: str) -> ResearchRelevanceComponent | None:
        """Return one named component, or nothing when it was not measured."""
        for component in self.components:
            if component.name == name:
                return component
        return None


#: What a candidate carries when ranking could not run at all. It scores zero
#: because nothing was measured, and it says so in its category rather than
#: borrowing `unrelated`, which is a conclusion about the candidate.
UNRANKED_RELEVANCE = ResearchSourceRelevance(
    score=0,
    category=ResearchRelevanceCategory.UNMEASURED,
    components=(
        ResearchRelevanceComponent(
            name="title_coverage",
            value=0.0,
            weight=0.0,
            applicable=False,
        ),
    ),
    reasons=(),
)
