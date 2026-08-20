"""Bounded aggregate result of the read-only research evidence audit."""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError


@dataclass(frozen=True, slots=True)
class ResearchEvidenceIntegrityStatus:
    """Expose only aggregate evidence-to-restored-content integrity counts."""

    available: bool
    recorded_evidence_count: int
    matched_evidence_count: int
    missing_evidence_count: int
    changed_evidence_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.available, bool):
            raise ResearchError("Research evidence integrity availability is invalid.")
        counts = (
            (self.recorded_evidence_count, "recorded count"),
            (self.matched_evidence_count, "matched count"),
            (self.missing_evidence_count, "missing count"),
            (self.changed_evidence_count, "changed count"),
        )
        for value, label in counts:
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ResearchError(f"Research evidence integrity {label} is invalid.")
        classified_count = (
            self.matched_evidence_count
            + self.missing_evidence_count
            + self.changed_evidence_count
        )
        if self.available and classified_count != self.recorded_evidence_count:
            raise ResearchError(
                "Research evidence integrity counts do not match the recorded total."
            )
        if not self.available and any(value != 0 for value, _ in counts):
            raise ResearchError(
                "Unavailable research evidence integrity cannot report counts."
            )

    @property
    def state(self) -> str:
        """Return the safe user-facing audit state."""
        return "ready" if self.available else "unavailable"

    @classmethod
    def unavailable(cls) -> ResearchEvidenceIntegrityStatus:
        """Create the bounded state used when an audit cannot be completed."""
        return cls(False, 0, 0, 0, 0)
