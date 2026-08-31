"""One human ruling about an attempt whose outcome Hypatia never learned."""

from __future__ import annotations

from enum import Enum


class ResearchAttemptResolution(Enum):
    """What an operator says happened during an interrupted attempt.

    Three answers and deliberately no fourth. The two confident ones say only
    whether the external operation *happened* — never whether it succeeded,
    because nobody here saw the result and no ruling invents one. The third is
    the honest default: an operator who does not know says so, and the execution
    stays exactly where it is rather than being tidied into a guess.

    `NONE` is the absence of a ruling, not a ruling of its own.
    """

    NONE = "none"
    PERFORMED_RESULT_UNKNOWN = "performed_result_unknown"
    NOT_PERFORMED = "not_performed"
    REMAINS_UNKNOWN = "remains_unknown"

    @property
    def settles(self) -> bool:
        """Return whether this ruling establishes what happened."""
        return self in (
            ResearchAttemptResolution.PERFORMED_RESULT_UNKNOWN,
            ResearchAttemptResolution.NOT_PERFORMED,
        )
