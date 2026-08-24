"""Where a hypothesis currently stands. None of these means "true".

There is deliberately no CONFIRMED and no PROVEN. SUPPORTED is as far as this
enum goes, and it means that evidence has accumulated from more than one
independent source, every supporting source has an active authored trust
assessment of at least medium, and none opposes it. That is still the position
from which most abandoned theories looked healthy. A vocabulary that offered
"confirmed" would get used, and once something is filed as confirmed nobody
looks for the observation that would have undone it.

CONTRADICTED is likewise not "false". It records that evidence was entered
against the hypothesis, and which way that resolves is a judgement someone makes
by reading both sides.
"""

from __future__ import annotations

from enum import StrEnum


class HypothesisStatus(StrEnum):
    """Name one bounded position a hypothesis currently occupies."""

    OPEN = "open"
    SUPPORTED = "supported"
    WEAKENED = "weakened"
    CONTRADICTED = "contradicted"
    WITHDRAWN = "withdrawn"

    @property
    def settled(self) -> bool:
        """Return whether anyone has stopped working on this hypothesis.

        Only withdrawal settles anything. Support does not: a hypothesis with
        evidence on one side is still open to the observation that would sink
        it, and treating it as finished is how that observation stops being
        looked for.
        """
        return self is HypothesisStatus.WITHDRAWN

    @property
    def has_opposing_evidence(self) -> bool:
        """Return whether evidence was recorded against this hypothesis."""
        return self in (
            HypothesisStatus.WEAKENED,
            HypothesisStatus.CONTRADICTED,
        )

    @property
    def means_true(self) -> bool:
        """Return whether this status asserts the hypothesis is true.

        No status does. Kept as an explicit property so the answer is asserted
        in a test rather than merely promised in a docstring.
        """
        return False
