"""Bounded categories of knowledge gap a completed research run can expose.

Every kind here is derivable from what the system already recorded. None of
them is a guess about the world: a gap says something about the *state of our
own evidence*, never about whether a claim is true.

The ordering below is the ranking order. A contradiction outranks an unresolved
claim because holding two incompatible beliefs is worse than holding one
uncertain belief, and both outrank a merely thin source record.

A hypothesis naming the observation that would settle it, with nothing yet
recorded either way, sits below all three claim gaps and above everything about
the run's breadth. Claims are positions the run already holds, and their
integrity comes first; a stated open question is the most answerable kind of
incompleteness, but it is still an absence rather than a belief in trouble.

Two of these describe an attempt rather than a record. A refused acquisition is
a hole with a known cause, ranked above a source we merely distrust because
there is nothing there at all; and a question put to one provider when two were
available is the thinnest kind of incompleteness, because the run may be
perfectly well supported and simply narrow. Neither says the other provider
would have done better, and neither is a proposal to try again.
"""

from __future__ import annotations

from enum import StrEnum


class ResearchKnowledgeGapKind(StrEnum):
    """Name one bounded reason the recorded evidence is incomplete."""

    CONTRADICTED_CLAIM = "contradicted_claim"
    UNRESOLVED_CLAIM = "unresolved_claim"
    SINGLE_SOURCE_CLAIM = "single_source_claim"
    HYPOTHESIS_EVIDENCE_GAP = "hypothesis_evidence_gap"
    UNSUPPORTED_QUESTION = "unsupported_question"
    FAILED_ACQUISITION = "failed_acquisition"
    LOW_TRUST_SOURCE = "low_trust_source"
    PROVIDER_COVERAGE_GAP = "provider_coverage_gap"
    UNASSESSED_SOURCE = "unassessed_source"
    UNUSED_SOURCE = "unused_source"

    @property
    def severity(self) -> int:
        """Return the ranking weight, higher meaning more epistemically urgent."""
        return _SEVERITIES[self]

    @property
    def subject_required(self) -> bool:
        """Return whether this kind must name a claim or source it is about."""
        return self not in _RUN_SCOPED_KINDS


#: Kinds that are about the run as a whole rather than about one stored record.
#: An unsupported question and a single-provider run both describe the run
#: itself, so neither can name a claim or source it is about.
_RUN_SCOPED_KINDS = frozenset(
    (
        ResearchKnowledgeGapKind.UNSUPPORTED_QUESTION,
        ResearchKnowledgeGapKind.PROVIDER_COVERAGE_GAP,
    )
)

_SEVERITIES: dict[ResearchKnowledgeGapKind, int] = {
    ResearchKnowledgeGapKind.CONTRADICTED_CLAIM: 70,
    ResearchKnowledgeGapKind.UNRESOLVED_CLAIM: 60,
    ResearchKnowledgeGapKind.SINGLE_SOURCE_CLAIM: 50,
    ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP: 45,
    ResearchKnowledgeGapKind.UNSUPPORTED_QUESTION: 40,
    ResearchKnowledgeGapKind.FAILED_ACQUISITION: 35,
    ResearchKnowledgeGapKind.LOW_TRUST_SOURCE: 30,
    ResearchKnowledgeGapKind.PROVIDER_COVERAGE_GAP: 25,
    ResearchKnowledgeGapKind.UNASSESSED_SOURCE: 20,
    ResearchKnowledgeGapKind.UNUSED_SOURCE: 10,
}


def severity_for(kind: ResearchKnowledgeGapKind) -> int:
    """Return the declared severity, refusing an unclassified kind."""
    if kind not in _SEVERITIES:
        raise ValueError(f"Knowledge gap kind {kind} declares no severity.")
    return _SEVERITIES[kind]
