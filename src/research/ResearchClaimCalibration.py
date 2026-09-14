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
from research.AssessmentWarningAttention import AssessmentWarningAttention
from research.CalibrationVerdict import CalibrationVerdict
from research.EvidenceSupportProfile import EvidenceSupportProfile
from research.ResearchAssessmentWarning import ResearchAssessmentWarning
from research.ResearchClaimConfidence import ResearchClaimConfidence
from research.ResearchEpistemicState import ResearchEpistemicState


@dataclass(frozen=True, slots=True)
class ResearchClaimCalibration:
    """Compare one authored claim against the support its record provides."""

    claim_id: str
    claim_text: str
    evidence_ids: tuple[str, ...]
    source_document_ids: tuple[str, ...]
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
        if not isinstance(self.claim_text, str) or not self.claim_text.strip():
            raise ResearchError("Claim calibration requires claim text.")
        evidence_ids = self._normalize_ids(self.evidence_ids, "evidence")
        source_document_ids = self._normalize_ids(
            self.source_document_ids,
            "source document",
        )
        if not isinstance(self.warnings, tuple) or not all(
            isinstance(warning, ResearchAssessmentWarning) for warning in self.warnings
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
        object.__setattr__(self, "claim_id", self.claim_id.strip())
        object.__setattr__(self, "claim_text", self.claim_text.strip())
        object.__setattr__(self, "evidence_ids", evidence_ids)
        object.__setattr__(self, "source_document_ids", source_document_ids)

    @staticmethod
    def _normalize_ids(values: tuple[str, ...], label: str) -> tuple[str, ...]:
        """Keep the exact, immutable provenance carried by the authored claim."""
        if not isinstance(values, tuple) or not values:
            raise ResearchError(f"Claim calibration requires {label} IDs.")
        if not all(isinstance(value, str) and value.strip() for value in values):
            raise ResearchError(f"Claim calibration {label} IDs are invalid.")
        normalized = tuple(value.strip() for value in values)
        if len(normalized) != len(set(normalized)):
            raise ResearchError(f"Claim calibration repeats a {label} ID.")
        return normalized

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
