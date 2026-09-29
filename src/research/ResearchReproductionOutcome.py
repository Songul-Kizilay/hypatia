"""What an operator observed when manually following a validation recipe.

A reproduction record is a low-stakes, repeatable observation, deliberately
separate from `ResearchSecurityFindingStatus`/`ResearchSecurityHypothesisStatus`:
recording one is never a status transition, never mutates the recipe,
hypothesis, or finding it references, and never grants execution authority.
`REPRODUCED` mirrors `ResearchSecurityFindingStatus.VALIDATED`'s own exact
discipline — a named, useful value that is not itself a confirmed
exploit, a severity assertion, or permission to act.
`means_confirmed_vulnerability` is `False` for every member, including
`REPRODUCED`, matching `ResearchSecurityFindingStatus`'s/
`ResearchSecurityHypothesisStatus`'s identical property exactly.

There is deliberately no `EXPLOITED`, `OWNED`, or severity-flavoured value.
`NOT_RUN` exists because an operator may want to record that a recipe was
read but not yet attempted, without inventing a null/sentinel outcome.
Each attempt is its own new, immutable record — there is no lifecycle or
state machine here, unlike the finding/hypothesis statuses: recording a
second reproduction of the same recipe is simply a second record, never an
edit or transition of the first.
"""

from __future__ import annotations

from enum import StrEnum


class ResearchReproductionOutcome(StrEnum):
    """Name one bounded, operator-recorded reproduction outcome."""

    NOT_RUN = "not_run"
    REPRODUCED = "reproduced"
    NOT_REPRODUCED = "not_reproduced"
    INCONCLUSIVE = "inconclusive"

    @property
    def means_confirmed_vulnerability(self) -> bool:
        """Return whether this outcome asserts a confirmed vulnerability.

        No outcome does, including `REPRODUCED`. A reproduction record is an
        operator's own observation, never itself authority to act, never a
        severity assertion, and never automatic validation of any finding.
        """
        return False
