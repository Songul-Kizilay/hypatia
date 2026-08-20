"""Read-only decision for a user-authored research comparison note."""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchSourceAssessmentRecord import ResearchSourceAssessmentRecord
from research.ResearchSourceComparisonPreview import ResearchSourceComparisonPreview


@dataclass(frozen=True, slots=True)
class ResearchSourceComparisonNoteWritePreview:
    """Show exact persisted references before an authored note is appended."""

    comparison: ResearchSourceComparisonPreview
    evidence: tuple[ResearchEvidenceRecord, ...]
    assessments: tuple[ResearchSourceAssessmentRecord, ...]
    text: str
    allowed: bool
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.comparison, ResearchSourceComparisonPreview):
            raise ResearchError("Research comparison note preview is invalid.")
        if not isinstance(self.text, str) or not self.text.strip():
            raise ResearchError(
                "Research comparison note preview text cannot be empty."
            )
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ResearchError(
                "Research comparison note preview reason cannot be empty."
            )
        if not isinstance(self.allowed, bool):
            raise ResearchError(
                "Research comparison note preview decision must be boolean."
            )
        if not isinstance(self.evidence, tuple) or not self.evidence:
            raise ResearchError(
                "Research comparison note preview requires explicit evidence."
            )
        if not all(
            isinstance(record, ResearchEvidenceRecord) for record in self.evidence
        ):
            raise ResearchError("Research comparison note evidence is invalid.")
        if not isinstance(self.assessments, tuple) or not self.assessments:
            raise ResearchError(
                "Research comparison note preview requires current assessments."
            )
        if not all(
            isinstance(record, ResearchSourceAssessmentRecord)
            for record in self.assessments
        ):
            raise ResearchError("Research comparison note assessments are invalid.")
        selected_source_ids = {
            item.source.document_id for item in self.comparison.sources
        }
        evidence_source_ids = {record.source_document_id for record in self.evidence}
        assessment_source_ids = {
            record.source_document_id for record in self.assessments
        }
        if evidence_source_ids != selected_source_ids:
            raise ResearchError(
                "Research comparison note evidence must cover every selected source."
            )
        if assessment_source_ids != selected_source_ids:
            raise ResearchError(
                "Research comparison note assessments must cover every selected source."
            )
        evidence_ids = {record.evidence_id for record in self.evidence}
        if any(
            not set(assessment.evidence_ids).issubset(evidence_ids)
            for assessment in self.assessments
        ):
            raise ResearchError(
                "Research comparison note must cite each assessment's evidence."
            )
        object.__setattr__(self, "text", self.text.strip())
        object.__setattr__(self, "reason", self.reason.strip())
