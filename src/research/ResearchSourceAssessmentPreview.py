"""Read-only manual-assessment context for one accepted research source."""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSourceRecord import ResearchSourceRecord


@dataclass(frozen=True, slots=True)
class ResearchSourceAssessmentPreview:
    """Expose accepted provenance and already user-selected evidence only."""

    run_id: str
    run_status: ResearchRunStatus
    source: ResearchSourceRecord
    evidence: tuple[ResearchEvidenceRecord, ...]
    has_recorded_evidence: bool
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, str) or not self.run_id.strip():
            raise ResearchError("Research source assessment run ID cannot be empty.")
        if not isinstance(self.run_status, ResearchRunStatus):
            raise ResearchError("Research source assessment run status is invalid.")
        if not isinstance(self.source, ResearchSourceRecord):
            raise ResearchError("Research source assessment source is invalid.")
        if not isinstance(self.evidence, tuple):
            raise ResearchError(
                "Research source assessment evidence must be an immutable tuple."
            )
        if not all(
            isinstance(record, ResearchEvidenceRecord) for record in self.evidence
        ):
            raise ResearchError("Research source assessment evidence is invalid.")
        if any(
            record.source_document_id != self.source.document_id
            for record in self.evidence
        ):
            raise ResearchError(
                "Research source assessment evidence must belong to its source."
            )
        if not isinstance(self.has_recorded_evidence, bool):
            raise ResearchError(
                "Research source assessment evidence decision must be boolean."
            )
        if self.has_recorded_evidence is not bool(self.evidence):
            raise ResearchError(
                "Research source assessment evidence decision is inconsistent."
            )
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ResearchError("Research source assessment reason cannot be empty.")
        object.__setattr__(self, "run_id", self.run_id.strip())
        object.__setattr__(self, "reason", self.reason.strip())
