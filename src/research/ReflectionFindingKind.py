"""Bounded categories of observation reflection can make about a run.

Every kind here describes the *process* — what the run did, failed to do, or
left uncertain. None of them describes the world. "This claim rests on one
source" is a fact about our record; "this claim is false" would be a research
conclusion, and reflection is not allowed to reach one.

The ordering is the report order, and it is deliberately not flattering:
failures and contradictions come before successes, because a reflection that
opens with what went well is a reflection nobody learns from.
"""

from __future__ import annotations

from enum import StrEnum


class ReflectionFindingKind(StrEnum):
    """Name one bounded observation about how a research run went."""

    FAILED = "failed"
    CONTRADICTION = "contradiction"
    REVISED_BELIEF = "revised_belief"
    WEAK_EVIDENCE = "weak_evidence"
    UNCERTAIN = "uncertain"
    UNUSED_EFFORT = "unused_effort"
    WORKED = "worked"
    NEXT_QUESTION = "next_question"

    @property
    def order(self) -> int:
        """Return the report position, lower meaning reported earlier."""
        return _ORDER[self]

    @property
    def is_lesson(self) -> bool:
        """Return whether this kind describes something to learn from.

        A success and a proposed question are worth reporting, but neither is a
        lesson: nothing went wrong and nothing needs revisiting.
        """
        return self not in (
            ReflectionFindingKind.WORKED,
            ReflectionFindingKind.NEXT_QUESTION,
        )


_ORDER: dict[ReflectionFindingKind, int] = {
    ReflectionFindingKind.FAILED: 0,
    ReflectionFindingKind.CONTRADICTION: 1,
    ReflectionFindingKind.REVISED_BELIEF: 2,
    ReflectionFindingKind.WEAK_EVIDENCE: 3,
    ReflectionFindingKind.UNCERTAIN: 4,
    ReflectionFindingKind.UNUSED_EFFORT: 5,
    ReflectionFindingKind.WORKED: 6,
    ReflectionFindingKind.NEXT_QUESTION: 7,
}


def order_for(kind: ReflectionFindingKind) -> int:
    """Return the declared report order, refusing an unclassified kind."""
    if kind not in _ORDER:
        raise ValueError(f"Reflection finding kind {kind} declares no order.")
    return _ORDER[kind]
