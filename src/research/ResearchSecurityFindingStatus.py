"""Where a security finding currently stands. None of these is authority to act.

A finding is created only from a hypothesis an operator already judged
`READY_FOR_VALIDATION` (see `cognition.ResearchSecurityFindingApplicationService`),
so its lifecycle starts one step further along than a hypothesis's own
`OPEN`. There is deliberately no CONFIRMED, EXPLOITED, or severity-flavoured
value, and `VALIDATED` never means one either:
`means_confirmed_vulnerability` is `False` for every member, including
`VALIDATED`, mirroring
`ResearchSecurityHypothesisStatus.means_validated_vulnerability`'s exact
discipline — this milestone performs no active validation of any kind, so
nothing here could honestly claim confirmed exploitability even once an
operator judges the evidence sufficient. `REFUTED`, `DUPLICATE`, and
`SUPERSEDED` are the three terminal states: once one of these is recorded,
nothing further is recorded against this finding.

`is_valid_status_transition` only knows the closed state-machine table. It
deliberately does not know that a transition *to* `VALIDATED` also requires
real validation evidence and zero unresolved contradicting evidence, or that
`DUPLICATE`/`SUPERSEDED` require a linkage field — those rules need the
finding's own evidence links and are enforced by the application service,
never baked into this pure function.
"""

from __future__ import annotations

from enum import StrEnum


class ResearchSecurityFindingStatus(StrEnum):
    """Name one bounded position a security finding currently occupies."""

    CANDIDATE = "candidate"
    VALIDATION_REQUIRED = "validation_required"
    VALIDATED = "validated"
    REFUTED = "refuted"
    DUPLICATE = "duplicate"
    SUPERSEDED = "superseded"

    @property
    def terminal(self) -> bool:
        """Return whether no further status transition is possible from here.

        Only `REFUTED`, `DUPLICATE`, and `SUPERSEDED` are terminal. `CANDIDATE`,
        `VALIDATION_REQUIRED`, and `VALIDATED` can all still move.
        """
        return self in (
            ResearchSecurityFindingStatus.REFUTED,
            ResearchSecurityFindingStatus.DUPLICATE,
            ResearchSecurityFindingStatus.SUPERSEDED,
        )

    @property
    def means_confirmed_vulnerability(self) -> bool:
        """Return whether this status asserts a confirmed vulnerability.

        No status does, including `VALIDATED`. This milestone performs no
        active validation of any kind, so `VALIDATED` names only that an
        operator has recorded validating evidence with no live contradiction
        — evidence-backed reasoning, never authority to act and never a
        confirmed exploit.
        """
        return False


#: The closed state-machine table this module enforces. A same-state
#: "transition" never appears in any of these sets, so it is refused by
#: construction rather than needing a separate special case. `VALIDATED`
#: never moves back to `CANDIDATE`/`VALIDATION_REQUIRED` — a corrected
#: validation is explicitly re-refuted, not silently reopened.
_VALID_TRANSITIONS: dict[
    ResearchSecurityFindingStatus, frozenset[ResearchSecurityFindingStatus]
] = {
    ResearchSecurityFindingStatus.CANDIDATE: frozenset(
        {
            ResearchSecurityFindingStatus.VALIDATION_REQUIRED,
            ResearchSecurityFindingStatus.VALIDATED,
            ResearchSecurityFindingStatus.REFUTED,
            ResearchSecurityFindingStatus.DUPLICATE,
            ResearchSecurityFindingStatus.SUPERSEDED,
        }
    ),
    ResearchSecurityFindingStatus.VALIDATION_REQUIRED: frozenset(
        {
            ResearchSecurityFindingStatus.CANDIDATE,
            ResearchSecurityFindingStatus.VALIDATED,
            ResearchSecurityFindingStatus.REFUTED,
            ResearchSecurityFindingStatus.DUPLICATE,
            ResearchSecurityFindingStatus.SUPERSEDED,
        }
    ),
    ResearchSecurityFindingStatus.VALIDATED: frozenset(
        {
            ResearchSecurityFindingStatus.REFUTED,
            ResearchSecurityFindingStatus.DUPLICATE,
            ResearchSecurityFindingStatus.SUPERSEDED,
        }
    ),
    ResearchSecurityFindingStatus.REFUTED: frozenset(),
    ResearchSecurityFindingStatus.DUPLICATE: frozenset(),
    ResearchSecurityFindingStatus.SUPERSEDED: frozenset(),
}


def is_valid_status_transition(
    current: ResearchSecurityFindingStatus,
    new: ResearchSecurityFindingStatus,
) -> bool:
    """Return whether moving from `current` to `new` is allowed.

    A same-state transition is always invalid, including for a terminal
    state moving to itself: every status's outgoing set already excludes
    itself. Pure and total: an invalid type argument returns `False` rather
    than raising, so a caller that already fail-closes on type is not forced
    to catch an exception here too. This function does not know about the
    evidence-gate rule for `VALIDATED`, or the linkage requirement for
    `DUPLICATE`/`SUPERSEDED` — those are enforced at the application-service
    layer.
    """
    if not isinstance(current, ResearchSecurityFindingStatus) or not isinstance(
        new, ResearchSecurityFindingStatus
    ):
        return False
    return new in _VALID_TRANSITIONS[current]
