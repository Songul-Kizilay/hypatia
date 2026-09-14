"""One detected gap in what a research run actually established.

A gap is an observation about our own record, not a finding about the world.
Detecting one performs no research work, establishes no evidence, and changes
no claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from core.Exceptions import ResearchError
from research.ResearchKnowledgeGapKind import ResearchKnowledgeGapKind

MAX_GAP_SUMMARY_LENGTH = 240


@dataclass(frozen=True, slots=True)
class ResearchKnowledgeGap:
    """Record one bounded, evidence-derived hole in a research run."""

    gap_id: str
    run_id: str
    kind: ResearchKnowledgeGapKind
    subject_id: str
    summary: str
    detected_at: datetime

    def __post_init__(self) -> None:
        for value, label in (
            (self.gap_id, "gap ID"),
            (self.run_id, "run ID"),
            (self.summary, "summary"),
        ):
            if not value.strip():
                raise ResearchError(f"Knowledge gap {label} cannot be empty.")
        if not isinstance(self.kind, ResearchKnowledgeGapKind):
            raise ResearchError("Knowledge gap kind must be a bounded category.")
        if len(self.summary) > MAX_GAP_SUMMARY_LENGTH:
            raise ResearchError("Knowledge gap summary is too long.")
        if self.kind.subject_required and not self.subject_id.strip():
            raise ResearchError(f"Knowledge gap kind {self.kind} requires a subject.")
        if not self.kind.subject_required and self.subject_id.strip():
            raise ResearchError(f"Knowledge gap kind {self.kind} takes no subject.")
        if self.detected_at.tzinfo is None:
            raise ResearchError("Knowledge gap detection time must be timezone aware.")
        if self.detected_at > datetime.now(UTC):
            raise ResearchError("Knowledge gap cannot be detected in the future.")

    @property
    def severity(self) -> int:
        """Return the ranking weight of this gap's kind."""
        return self.kind.severity
