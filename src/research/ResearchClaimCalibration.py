"""One claim, what it asserts, and what its evidence structure can carry.

A calibration is a comparison, not a correction. It records the state and
confidence someone authored, the ceilings the recorded evidence supports, and
how the two relate. It never rewrites the claim: the epistemic state of a claim
belongs to the person who authored it, and a system that quietly adjusted it
would be editing someone else's judgement while calling it bookkeeping.

A ceiling is not a floor. Meeting it does not make a claim true; it means
nothing in our own record contradicts asserting that much.

Warnings sit alongside the verdict for the same reason and with the same limits.
The verdict compares the claim to the shape of its support; a warning reports
that a person, having read one of those sources, recorded something about it
worth knowing before leaning on it further. Neither changes the claim, and a
claim with no warnings has not been checked and found sound — nobody may have
looked at all.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.CalibrationVerdict import CalibrationVerdict
from research.EvidenceSupportProfile import EvidenceSupportProfile
from research.AssessmentWarningAttention import AssessmentWarningAttention
from research.ResearchAssessmentWarning import ResearchAssessmentWarning
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
    warnings: tuple[ResearchAssessmentWarning, ...] = ()

    def __post_init__(self) -> None:
        if not self.claim_id.strip():
            raise ResearchError("Claim calibration requires a claim ID.")
        if not isinstance(self.warnings, tuple) or not all(
            isinstance(warning, ResearchAssessmentWarning)
            for warning in self.warnings
        ):
            raise ResearchError("Claim calibration warnings are invalid.")
        if any(warning.claim_id != self.claim_id.strip() for warning in self.warnings):
            raise ResearchError("A calibration warning belongs to another claim.")
        if len({warning.identity for warning in self.warnings}) != len(self.warnings):
            raise ResearchError("A calibration warning is repeated.")
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

    @property
    def highest_attention(self) -> AssessmentWarningAttention | None:
        """Return the most pressing warning level, or nothing when there are none."""
        if not self.warnings:
            return None
        return max(
            (warning.attention for warning in self.warnings),
            key=lambda attention: attention.rank,
        )

    def summary(self) -> str:
        """Render the comparison in one bounded line."""
        return (
            f"authored {self.authored_state.value}/"
            f"{self.authored_confidence.value}, "
            f"record supports up to {self.supported_state.value}/"
            f"{self.supported_confidence.value}"
        )
