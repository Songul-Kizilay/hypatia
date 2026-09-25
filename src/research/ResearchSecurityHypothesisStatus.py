"""Where a security hypothesis currently stands. None of these means "true".

There is deliberately no CONFIRMED, VALIDATED, EXPLOITED, or severity-flavoured
value. `READY_FOR_VALIDATION` says only that an operator judges enough has
been gathered to justify active testing later — it is not itself a test
result, and this milestone performs no active testing at all. `REFUTED` is
the one terminal state: once an operator records that the evidence gathered
so far has already answered the question against the hypothesis, nothing
further is recorded against it. Every other state can still move.

`means_validated_vulnerability` mirrors `HypothesisStatus.means_true`'s own
discipline: the answer is asserted here, in a property a test can check,
never left to a docstring alone.
"""

from __future__ import annotations

from enum import StrEnum


class ResearchSecurityHypothesisStatus(StrEnum):
    """Name one bounded position a security hypothesis currently occupies."""

    OPEN = "open"
    NEEDS_EVIDENCE = "needs_evidence"
    READY_FOR_VALIDATION = "ready_for_validation"
    REFUTED = "refuted"

    @property
    def terminal(self) -> bool:
        """Return whether no further status transition is possible from here.

        Only `REFUTED` is terminal. Every other status can still move toward
        more evidence, toward a stated readiness for active validation, or to
        `REFUTED` itself.
        """
        return self is ResearchSecurityHypothesisStatus.REFUTED

    @property
    def means_validated_vulnerability(self) -> bool:
        """Return whether this status asserts a validated vulnerability.

        No status does. This milestone performs no active validation of any
        kind, so nothing here could honestly claim confirmation even for
        `READY_FOR_VALIDATION` — that status names an operator's judgement
        that testing is warranted, not a result of having tested.
        """
        return False


#: The closed state-machine table this module enforces. A same-state
#: "transition" never appears in any of these sets, so it is refused by
#: construction rather than needing a separate special case.
_VALID_TRANSITIONS: dict[
    ResearchSecurityHypothesisStatus, frozenset[ResearchSecurityHypothesisStatus]
] = {
    ResearchSecurityHypothesisStatus.OPEN: frozenset(
        {
            ResearchSecurityHypothesisStatus.NEEDS_EVIDENCE,
            ResearchSecurityHypothesisStatus.READY_FOR_VALIDATION,
            ResearchSecurityHypothesisStatus.REFUTED,
        }
    ),
    ResearchSecurityHypothesisStatus.NEEDS_EVIDENCE: frozenset(
        {
            ResearchSecurityHypothesisStatus.OPEN,
            ResearchSecurityHypothesisStatus.READY_FOR_VALIDATION,
            ResearchSecurityHypothesisStatus.REFUTED,
        }
    ),
    ResearchSecurityHypothesisStatus.READY_FOR_VALIDATION: frozenset(
        {
            ResearchSecurityHypothesisStatus.NEEDS_EVIDENCE,
            ResearchSecurityHypothesisStatus.REFUTED,
        }
    ),
    ResearchSecurityHypothesisStatus.REFUTED: frozenset(),
}


def is_valid_status_transition(
    current: ResearchSecurityHypothesisStatus,
    new: ResearchSecurityHypothesisStatus,
) -> bool:
    """Return whether moving from `current` to `new` is allowed.

    A same-state transition is always invalid, including from `REFUTED` to
    itself: `REFUTED` is terminal, and every status's outgoing set already
    excludes itself. Pure and total: an invalid type argument returns `False`
    rather than raising, so a caller that already fail-closes on type is not
    forced to catch an exception here too.
    """
    if not isinstance(current, ResearchSecurityHypothesisStatus) or not isinstance(
        new, ResearchSecurityHypothesisStatus
    ):
        return False
    return new in _VALID_TRANSITIONS[current]
