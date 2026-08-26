"""One measured part of a relevance score, kept separate from the total.

The total is the useful number and the parts are the honest ones. A candidate
can reach the same score by matching every word of a vague question or by
matching the one identifier that mattered, and those are not the same result.
Keeping the parts means a person can see which happened.

A component can also be inapplicable, which is different from scoring zero.
Recency is inapplicable when nobody asked for recent work; a venue match is
inapplicable when the record carries no venue. Scoring those as zero would
punish a candidate for a question that was never asked and for metadata the
provider never returned, so an inapplicable component contributes nothing and
takes its weight out of the total rather than dragging the score down.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError

MAX_COMPONENT_NAME_LENGTH = 40


@dataclass(frozen=True, slots=True)
class ResearchRelevanceComponent:
    """Hold one component's measured value, its weight, and whether it applied."""

    name: str
    value: float
    weight: float
    applicable: bool

    def __post_init__(self) -> None:
        if (
            not isinstance(self.name, str)
            or not self.name.strip()
            or len(self.name) > MAX_COMPONENT_NAME_LENGTH
        ):
            raise ResearchError("A relevance component needs a name.")
        for name in ("value", "weight"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ResearchError("A relevance component must be numeric.")
            object.__setattr__(self, name, float(value))
        if not 0.0 <= self.value <= 1.0:
            raise ResearchError("A relevance component value must be a fraction.")
        if self.weight < 0.0:
            raise ResearchError("A relevance component weight must not be negative.")
        if not isinstance(self.applicable, bool):
            raise ResearchError("A relevance component must state whether it applied.")
        if not self.applicable and self.value != 0.0:
            raise ResearchError("An inapplicable component cannot contribute a value.")

    @property
    def contribution(self) -> float:
        """Return the weighted amount this component added to the score."""
        return self.value * self.weight if self.applicable else 0.0

    @property
    def available_weight(self) -> float:
        """Return the weight this component put into the total it is scored over."""
        return self.weight if self.applicable else 0.0
