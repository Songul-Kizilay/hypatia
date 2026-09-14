"""How an authored claim compares to the evidence structure behind it.

There is a deliberate asymmetry here. Claiming more than the evidence structure
can carry is a finding; claiming less is not. Being more careful than the record
requires is never an error, and a calibration that nagged people toward higher
confidence would be pushing exactly the wrong way.

None of these verdicts is about truth. OVERSTATED does not mean the claim is
wrong, and WITHIN_SUPPORT does not mean it is right. They describe the fit
between what someone wrote down and what the record can carry.
"""

from __future__ import annotations

from enum import StrEnum


class CalibrationVerdict(StrEnum):
    """Name one bounded relationship between a claim and its support."""

    WITHIN_SUPPORT = "within_support"
    UNDERSTATED = "understated"
    OVERSTATED_CONFIDENCE = "overstated_confidence"
    OVERSTATED_STATE = "overstated_state"
    OVERSTATED_BOTH = "overstated_both"
    CONTRADICTED = "contradicted"

    @property
    def needs_attention(self) -> bool:
        """Return whether a person should look at this claim again.

        Understatement never does. Someone deliberately holding back is not a
        problem to be corrected.
        """
        return self not in (
            CalibrationVerdict.WITHIN_SUPPORT,
            CalibrationVerdict.UNDERSTATED,
        )

    @property
    def overstated(self) -> bool:
        """Return whether the claim asserts more than the record can carry."""
        return self in (
            CalibrationVerdict.OVERSTATED_CONFIDENCE,
            CalibrationVerdict.OVERSTATED_STATE,
            CalibrationVerdict.OVERSTATED_BOTH,
        )
