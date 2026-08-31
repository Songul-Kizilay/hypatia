"""Read-only handoff from claim calibration to human-authored revision work.

This object carries the exact current claim and its calibration into a review
surface.  It deliberately contains no proposed replacement text, epistemic
state, or confidence: those remain authored decisions, and constructing this
object never records or changes a claim.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchClaimCalibration import ResearchClaimCalibration


@dataclass(frozen=True, slots=True)
class ResearchClaimRevisionPreparation:
    """One calibration worth reviewing, with an inert authoring handoff."""

    run_id: str
    calibration: ResearchClaimCalibration

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, str) or not self.run_id.strip():
            raise ResearchError("Claim revision preparation requires a run ID.")
        if not isinstance(self.calibration, ResearchClaimCalibration):
            raise ResearchError("Claim revision preparation requires calibration.")
        if not (self.calibration.needs_attention or self.calibration.warnings):
            raise ResearchError(
                "Claim calibration identifies no reason for a second look."
            )
        object.__setattr__(self, "run_id", self.run_id.strip())

    @property
    def supersedes_claim_id(self) -> str:
        """Name the current claim a person may choose to replace."""
        return self.calibration.claim_id

    @property
    def current_evidence_ids(self) -> tuple[str, ...]:
        """Expose existing provenance for review, never as an automatic choice."""
        return self.calibration.evidence_ids

    @property
    def current_source_document_ids(self) -> tuple[str, ...]:
        """Expose the sources behind the current claim for inspection."""
        return self.calibration.source_document_ids
