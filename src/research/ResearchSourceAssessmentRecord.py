"""Persistent user-authored assessment of one accepted research source."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.Exceptions import ResearchError
from research.ResearchInformationTrust import ResearchInformationTrust

MAX_SOURCE_ASSESSMENT_CHARACTERS = 2_000


@dataclass(frozen=True, slots=True)
class ResearchSourceAssessmentRecord:
    """Append-only assessment text bound to explicitly selected evidence."""

    assessment_id: str
    source_document_id: str
    evidence_ids: tuple[str, ...]
    text: str
    recorded_at: datetime
    supersedes_assessment_id: str | None = None
    information_trust: ResearchInformationTrust = ResearchInformationTrust.UNASSESSED

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.assessment_id, "Research source assessment ID"),
            (self.source_document_id, "Research source assessment document ID"),
            (self.text, "Research source assessment text"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ResearchError(f"{field_name} cannot be empty.")
        if len(self.text.strip()) > MAX_SOURCE_ASSESSMENT_CHARACTERS:
            raise ResearchError("Research source assessment text is too long.")
        if not isinstance(self.evidence_ids, tuple) or not self.evidence_ids:
            raise ResearchError(
                "Research source assessment requires explicit evidence IDs."
            )
        if not all(
            isinstance(evidence_id, str) and evidence_id.strip()
            for evidence_id in self.evidence_ids
        ):
            raise ResearchError("Research source assessment evidence IDs are invalid.")
        normalized_evidence_ids = tuple(
            evidence_id.strip() for evidence_id in self.evidence_ids
        )
        if len(normalized_evidence_ids) != len(set(normalized_evidence_ids)):
            raise ResearchError(
                "Research source assessment contains duplicate evidence IDs."
            )
        if (
            not isinstance(self.recorded_at, datetime)
            or self.recorded_at.utcoffset() is None
        ):
            raise ResearchError(
                "Research source assessment time must be timezone-aware."
            )
        if not isinstance(self.information_trust, ResearchInformationTrust):
            raise ResearchError("Research source information trust is invalid.")
        supersedes_assessment_id = self.supersedes_assessment_id
        if supersedes_assessment_id is not None:
            if (
                not isinstance(supersedes_assessment_id, str)
                or not supersedes_assessment_id.strip()
            ):
                raise ResearchError(
                    "Superseded research source assessment ID cannot be empty."
                )
            supersedes_assessment_id = supersedes_assessment_id.strip()
            if supersedes_assessment_id == self.assessment_id.strip():
                raise ResearchError(
                    "A research source assessment cannot supersede itself."
                )
        object.__setattr__(self, "assessment_id", self.assessment_id.strip())
        object.__setattr__(
            self,
            "source_document_id",
            self.source_document_id.strip(),
        )
        object.__setattr__(self, "evidence_ids", normalized_evidence_ids)
        object.__setattr__(self, "text", self.text.strip())
        object.__setattr__(
            self,
            "supersedes_assessment_id",
            supersedes_assessment_id,
        )
