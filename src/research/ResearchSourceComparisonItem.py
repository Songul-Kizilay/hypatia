"""One source column in a read-only manual research comparison."""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchSourceAssessmentRecord import ResearchSourceAssessmentRecord
from research.ResearchSourceRecord import ResearchSourceRecord

MAX_COMPARISON_EVIDENCE_PER_SOURCE = 20
MAX_COMPARISON_ASSESSMENTS_PER_SOURCE = 10


@dataclass(frozen=True, slots=True)
class ResearchSourceComparisonItem:
    """Keep one accepted source beside its selected evidence and current notes."""

    source: ResearchSourceRecord
    evidence: tuple[ResearchEvidenceRecord, ...]
    current_assessments: tuple[ResearchSourceAssessmentRecord, ...]
    omitted_evidence_count: int = 0
    omitted_current_assessment_count: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.source, ResearchSourceRecord):
            raise ResearchError("Research comparison source is invalid.")
        if not isinstance(self.evidence, tuple) or not all(
            isinstance(record, ResearchEvidenceRecord) for record in self.evidence
        ):
            raise ResearchError(
                "Research comparison evidence must be an immutable record tuple."
            )
        if any(
            record.source_document_id != self.source.document_id
            for record in self.evidence
        ):
            raise ResearchError(
                "Research comparison evidence must belong to its source."
            )
        if not isinstance(self.current_assessments, tuple) or not all(
            isinstance(record, ResearchSourceAssessmentRecord)
            for record in self.current_assessments
        ):
            raise ResearchError(
                "Research comparison assessments must be an immutable record tuple."
            )
        if any(
            record.source_document_id != self.source.document_id
            for record in self.current_assessments
        ):
            raise ResearchError(
                "Research comparison assessments must belong to their source."
            )
        for count, field_name in (
            (self.omitted_evidence_count, "omitted evidence count"),
            (
                self.omitted_current_assessment_count,
                "omitted current assessment count",
            ),
        ):
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ResearchError(
                    f"Research comparison {field_name} cannot be negative."
                )
        if len(self.evidence) > MAX_COMPARISON_EVIDENCE_PER_SOURCE:
            raise ResearchError(
                "Research comparison displays too many evidence records."
            )
        if len(self.current_assessments) > MAX_COMPARISON_ASSESSMENTS_PER_SOURCE:
            raise ResearchError(
                "Research comparison displays too many current assessments."
            )

    @property
    def total_evidence_count(self) -> int:
        """Return the complete persisted count without carrying every record."""
        return len(self.evidence) + self.omitted_evidence_count

    @property
    def total_current_assessment_count(self) -> int:
        """Return the complete current count without carrying every record."""
        return len(self.current_assessments) + self.omitted_current_assessment_count
