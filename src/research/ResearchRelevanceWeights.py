"""The one place the ranking's numbers live.

Weights scattered through a scoring function are weights nobody can audit. They
also cannot be compared against each other, so the moment two of them disagree
the only way to find out which one won is to run the code.

So they are gathered here as one bounded, validated object with explicit
defaults. Two properties matter more than the particular values. First, the
model does not choose them: there is no path from generated text to this object,
and nothing reads them from a prompt, a response, or a remote setting. Second,
they are ordinary numbers rather than learned ones — the ranking is arithmetic
over words that are either present or absent, so the same query against the same
results produces the same order on any machine, with no model available and no
network reachable.

The relative sizes encode one judgement, stated plainly: matching a technical
identifier is worth more per term than matching a common word, because a title
containing `CVE-2026-12345` is about that vulnerability while a title containing
`analysis` is about nothing in particular.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError

MAX_COMPONENT_WEIGHT = 100.0


@dataclass(frozen=True, slots=True)
class ResearchRelevanceWeights:
    """Hold the fixed contribution of each relevance component."""

    title_coverage: float = 55.0
    phrase_adjacency: float = 15.0
    venue_terms: float = 5.0
    recency: float = 10.0
    #: How much more a matched identifier counts than a matched common word
    #: when measuring how much of the question a title covers. Without this,
    #: a title matching three vague words ties with a title matching the one
    #: identifier the question was actually about, and the tie is then broken
    #: by provider order — which is the outcome ranking exists to prevent.
    technical_term_specificity: float = 6.0
    strong_score: int = 65
    moderate_score: int = 35
    weak_score: int = 12

    def __post_init__(self) -> None:
        for name in (
            "title_coverage",
            "phrase_adjacency",
            "venue_terms",
            "recency",
            "technical_term_specificity",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ResearchError("A relevance weight must be a number.")
            if not 0.0 <= float(value) <= MAX_COMPONENT_WEIGHT:
                raise ResearchError("A relevance weight is out of range.")
            object.__setattr__(self, name, float(value))
        if self.title_coverage <= 0.0:
            raise ResearchError("Title coverage must carry weight.")
        if self.technical_term_specificity < 1.0:
            raise ResearchError("An identifier cannot count for less than a word.")
        for name in ("strong_score", "moderate_score", "weak_score"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ResearchError("A relevance threshold must be a whole number.")
            if not 0 <= value <= 100:
                raise ResearchError("A relevance threshold is out of range.")
        if not self.strong_score > self.moderate_score > self.weak_score:
            raise ResearchError("Relevance thresholds must descend.")

    def weight_of(self, component: str) -> float:
        """Return the weight of one named component."""
        if not isinstance(component, str) or not hasattr(self, component):
            raise ResearchError("Unknown relevance component.")
        weight = getattr(self, component)
        if not isinstance(weight, float):
            raise ResearchError("Unknown relevance component.")
        return weight


DEFAULT_RELEVANCE_WEIGHTS = ResearchRelevanceWeights()
