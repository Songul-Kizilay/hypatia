"""What an operator does about an attempt that ran without being seen."""

from __future__ import annotations

from enum import Enum


class ResearchAttemptRecoveryDecision(Enum):
    """The two ways forward from a performed attempt whose result is unknown.

    Neither invents an outcome. Supplying information says only that a person
    went and looked and is reporting what they found; the report is theirs, not
    the provider's, and stays labelled that way wherever it is shown. Abandoning
    says the step will not be pursued, which settles what happens next without
    claiming anything about what already happened.

    `NONE` is the absence of a decision, not a decision.
    """

    NONE = "none"
    OPERATOR_SUPPLIED_RESULT = "operator_supplied_result"
    ABANDONED = "abandoned"

    @property
    def decided(self) -> bool:
        """Return whether an operator has actually chosen something."""
        return self is not ResearchAttemptRecoveryDecision.NONE
