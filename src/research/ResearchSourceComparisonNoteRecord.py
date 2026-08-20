"""Persistent user-authored note comparing accepted research sources."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.Exceptions import ResearchError

MIN_COMPARISON_NOTE_SOURCES = 2
MAX_COMPARISON_NOTE_SOURCES = 5
MAX_COMPARISON_NOTE_EVIDENCE = 100
MAX_COMPARISON_NOTE_ASSESSMENTS = 50
MAX_COMPARISON_NOTE_CHARACTERS = 4_000


@dataclass(frozen=True, slots=True)
class ResearchSourceComparisonNoteRecord:
    """Append-only authored text bound to exact persisted research records."""

    note_id: str
    source_document_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    assessment_ids: tuple[str, ...]
    text: str
    recorded_at: datetime

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.note_id, "Research comparison note ID"),
            (self.text, "Research comparison note text"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ResearchError(f"{field_name} cannot be empty.")
        normalized_sources = self._normalize_ids(
            self.source_document_ids,
            "Research comparison note source document IDs",
        )
        if (
            not MIN_COMPARISON_NOTE_SOURCES
            <= len(normalized_sources)
            <= (MAX_COMPARISON_NOTE_SOURCES)
        ):
            raise ResearchError("Research comparison note requires 2 to 5 sources.")
        normalized_evidence = self._normalize_ids(
            self.evidence_ids,
            "Research comparison note evidence IDs",
        )
        if len(normalized_evidence) > MAX_COMPARISON_NOTE_EVIDENCE:
            raise ResearchError(
                "Research comparison note cannot cite more than 100 evidence records."
            )
        normalized_assessments = self._normalize_ids(
            self.assessment_ids,
            "Research comparison note assessment IDs",
        )
        if len(normalized_assessments) > MAX_COMPARISON_NOTE_ASSESSMENTS:
            raise ResearchError(
                "Research comparison note cannot cite more than 50 assessments."
            )
        normalized_text = self.text.strip()
        if len(normalized_text) > MAX_COMPARISON_NOTE_CHARACTERS:
            raise ResearchError("Research comparison note text is too long.")
        if (
            not isinstance(self.recorded_at, datetime)
            or self.recorded_at.utcoffset() is None
        ):
            raise ResearchError("Research comparison note time must be timezone-aware.")
        object.__setattr__(self, "note_id", self.note_id.strip())
        object.__setattr__(self, "source_document_ids", normalized_sources)
        object.__setattr__(self, "evidence_ids", normalized_evidence)
        object.__setattr__(self, "assessment_ids", normalized_assessments)
        object.__setattr__(self, "text", normalized_text)

    @staticmethod
    def _normalize_ids(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
        if not isinstance(values, tuple) or not values:
            raise ResearchError(f"{field_name} must be a non-empty immutable tuple.")
        if not all(isinstance(value, str) and value.strip() for value in values):
            raise ResearchError(f"{field_name} are invalid.")
        normalized = tuple(value.strip() for value in values)
        if len(normalized) != len(set(normalized)):
            raise ResearchError(f"{field_name} contain duplicates.")
        return normalized
