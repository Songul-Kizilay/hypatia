"""Read-only decision for one user-authored source assessment."""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSourceRecord import ResearchSourceRecord


@dataclass(frozen=True, slots=True)
class ResearchSourceAssessmentWritePreview:
    """Explain a proposed assessment without assigning a score or writing it."""

    run_id: str
    run_status: ResearchRunStatus
    source: ResearchSourceRecord
    evidence: tuple[ResearchEvidenceRecord, ...]
    text: str
    allowed: bool
    reason: str

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.run_id, "Research assessment preview run ID"),
            (self.text, "Research assessment preview text"),
            (self.reason, "Research assessment preview reason"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ResearchError(f"{field_name} cannot be empty.")
        if not isinstance(self.run_status, ResearchRunStatus):
            raise ResearchError("Research assessment preview run status is invalid.")
        if not isinstance(self.source, ResearchSourceRecord):
            raise ResearchError("Research assessment preview source is invalid.")
        if not isinstance(self.evidence, tuple) or not self.evidence:
            raise ResearchError(
                "Research assessment preview requires explicit evidence."
            )
        if not all(
            isinstance(record, ResearchEvidenceRecord) for record in self.evidence
        ):
            raise ResearchError("Research assessment preview evidence is invalid.")
        if any(
            record.source_document_id != self.source.document_id
            for record in self.evidence
        ):
            raise ResearchError(
                "Research assessment preview evidence must belong to its source."
            )
        evidence_ids = [record.evidence_id for record in self.evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ResearchError(
                "Research assessment preview contains duplicate evidence IDs."
            )
        if not isinstance(self.allowed, bool):
            raise ResearchError("Research assessment preview decision must be boolean.")
        object.__setattr__(self, "run_id", self.run_id.strip())
        object.__setattr__(self, "text", self.text.strip())
        object.__setattr__(self, "reason", self.reason.strip())
