"""Bounded categories of knowledge gap a completed research run can expose.

Every kind here is derivable from what the system already recorded. None of
them is a guess about the world: a gap says something about the *state of our
own evidence*, never about whether a claim is true.

The ordering below is the ranking order. A contradiction outranks an unresolved
claim because holding two incompatible beliefs is worse than holding one
uncertain belief, and both outrank a merely thin source record.
"""

from __future__ import annotations

from enum import StrEnum


class ResearchKnowledgeGapKind(StrEnum):
    """Name one bounded reason the recorded evidence is incomplete."""

    CONTRADICTED_CLAIM = "contradicted_claim"
    UNRESOLVED_CLAIM = "unresolved_claim"
    SINGLE_SOURCE_CLAIM = "single_source_claim"
    UNSUPPORTED_QUESTION = "unsupported_question"
    LOW_TRUST_SOURCE = "low_trust_source"
    UNASSESSED_SOURCE = "unassessed_source"
    UNUSED_SOURCE = "unused_source"

    @property
    def severity(self) -> int:
        """Return the ranking weight, higher meaning more epistemically urgent."""
        return _SEVERITIES[self]

    @property
    def subject_required(self) -> bool:
        """Return whether this kind must name a claim or source it is about."""
        return self is not ResearchKnowledgeGapKind.UNSUPPORTED_QUESTION


_SEVERITIES: dict[ResearchKnowledgeGapKind, int] = {
    ResearchKnowledgeGapKind.CONTRADICTED_CLAIM: 70,
    ResearchKnowledgeGapKind.UNRESOLVED_CLAIM: 60,
    ResearchKnowledgeGapKind.SINGLE_SOURCE_CLAIM: 50,
    ResearchKnowledgeGapKind.UNSUPPORTED_QUESTION: 40,
    ResearchKnowledgeGapKind.LOW_TRUST_SOURCE: 30,
    ResearchKnowledgeGapKind.UNASSESSED_SOURCE: 20,
    ResearchKnowledgeGapKind.UNUSED_SOURCE: 10,
}


def severity_for(kind: ResearchKnowledgeGapKind) -> int:
    """Return the declared severity, refusing an unclassified kind."""
    if kind not in _SEVERITIES:
        raise ValueError(f"Knowledge gap kind {kind} declares no severity.")
    return _SEVERITIES[kind]
