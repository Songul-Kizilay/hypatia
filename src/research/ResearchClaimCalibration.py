"""One claim, what it asserts, and what its evidence structure can carry.

A calibration is a comparison, not a correction. It records the state and
confidence someone authored, the ceilings the recorded evidence supports, and
how the two relate. It never rewrites the claim: the epistemic state of a claim
belongs to the person who authored it, and a system that quietly adjusted it
would be editing someone else's judgement while calling it bookkeeping.

A ceiling is not a floor. Meeting it does not make a claim true; it means
nothing in our own record contradicts asserting that much.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.CalibrationVerdict import CalibrationVerdict
from research.EvidenceSupportProfile import EvidenceSupportProfile
from research.ResearchClaimConfidence import ResearchClaimConfidence
from research.ResearchEpistemicState import ResearchEpistemicState


@dataclass(frozen=True, slots=True)
class ResearchClaimCalibration:
    """Compare one authored claim against the support its record provides."""

    claim_id: str
    authored_state: ResearchEpistemicState
    authored_confidence: ResearchClaimConfidence
    supported_state: ResearchEpistemicState
    supported_confidence: ResearchClaimConfidence
    profile: EvidenceSupportProfile
    verdict: CalibrationVerdict

    def __post_init__(self) -> None:
        if not self.claim_id.strip():
            raise ResearchError("Claim calibration requires a claim ID.")
        for state, state_label in (
            (self.authored_state, "authored state"),
            (self.supported_state, "supported state"),
        ):
            if not isinstance(state, ResearchEpistemicState):
                raise ResearchError(
                    f"Calibration {state_label} must be a bounded state."
                )
        for confidence, confidence_label in (
            (self.authored_confidence, "authored confidence"),
            (self.supported_confidence, "supported confidence"),
        ):
            if not isinstance(confidence, ResearchClaimConfidence):
                raise ResearchError(
                    f"Calibration {confidence_label} must be a bounded confidence."
                )
        if not isinstance(self.profile, EvidenceSupportProfile):
            raise ResearchError("Claim calibration requires an evidence profile.")
        if not isinstance(self.verdict, CalibrationVerdict):
            raise ResearchError("Calibration verdict must be a bounded category.")

    @property
    def needs_attention(self) -> bool:
        """Return whether a person should look at this claim again."""
        return self.verdict.needs_attention

    def summary(self) -> str:
        """Render the comparison in one bounded line."""
        return (
            f"authored {self.authored_state.value}/"
            f"{self.authored_confidence.value}, "
            f"record supports up to {self.supported_state.value}/"
            f"{self.supported_confidence.value}"
        )
