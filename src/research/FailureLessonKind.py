"""Bounded categories of lesson a research run can leave behind.

Each kind names a way the work went wrong that is worth remembering. None of
them is a verdict about the world. A failed hypothesis is one we stopped
holding, not one shown to be false; an ineffective strategy is one that did not
pay off here, not one that never works.

That distinction is why every lesson must cite provenance. "This approach does
not work" is an opinion. "This discovery produced eight candidates and none was
accepted, and here are the record identifiers" is a lesson, and it stays checkable
long after whoever wrote it has forgotten the details.
"""

from __future__ import annotations

from enum import StrEnum


class FailureLessonKind(StrEnum):
    """Name one bounded way a run's work did not pay off."""

    FAILED_HYPOTHESIS = "failed_hypothesis"
    REVISED_CLAIM = "revised_claim"
    DISPROVING_EVIDENCE = "disproving_evidence"
    INVALID_ASSUMPTION = "invalid_assumption"
    FALSE_POSITIVE = "false_positive"
    CONFIDENCE_CHANGE = "confidence_change"
    INEFFECTIVE_STRATEGY = "ineffective_strategy"
    OPERATION_FAILURE = "operation_failure"

    @property
    def weight(self) -> int:
        """Return the recall weight, higher meaning more worth remembering."""
        return _WEIGHTS[self]

    @property
    def concerns_belief(self) -> bool:
        """Return whether this lesson is about what we believed.

        The rest are about how we worked. Both are worth keeping, but only the
        first kind should ever make someone revisit a conclusion.
        """
        return self in (
            FailureLessonKind.FAILED_HYPOTHESIS,
            FailureLessonKind.REVISED_CLAIM,
            FailureLessonKind.DISPROVING_EVIDENCE,
            FailureLessonKind.INVALID_ASSUMPTION,
            FailureLessonKind.CONFIDENCE_CHANGE,
        )


_WEIGHTS: dict[FailureLessonKind, int] = {
    FailureLessonKind.DISPROVING_EVIDENCE: 70,
    FailureLessonKind.FAILED_HYPOTHESIS: 60,
    FailureLessonKind.REVISED_CLAIM: 60,
    FailureLessonKind.INVALID_ASSUMPTION: 50,
    FailureLessonKind.FALSE_POSITIVE: 40,
    FailureLessonKind.CONFIDENCE_CHANGE: 30,
    FailureLessonKind.INEFFECTIVE_STRATEGY: 20,
    FailureLessonKind.OPERATION_FAILURE: 10,
}


def weight_for(kind: FailureLessonKind) -> int:
    """Return the declared recall weight, refusing an unclassified kind."""
    if kind not in _WEIGHTS:
        raise ValueError(f"Failure lesson kind {kind} declares no weight.")
    return _WEIGHTS[kind]
