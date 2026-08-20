"""Immutable side-by-side preview for explicitly selected research sources."""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSourceComparisonItem import ResearchSourceComparisonItem
from research.ResearchSourceComparisonNoteRecord import (
    ResearchSourceComparisonNoteRecord,
)

MIN_COMPARISON_SOURCES = 2
MAX_COMPARISON_SOURCES = 5
MAX_COMPARISON_NOTES = 20


@dataclass(frozen=True, slots=True)
class ResearchSourceComparisonPreview:
    """Expose manual comparison material without producing a conclusion."""

    run_id: str
    question: str
    run_status: ResearchRunStatus
    sources: tuple[ResearchSourceComparisonItem, ...]
    reason: str
    comparison_notes: tuple[ResearchSourceComparisonNoteRecord, ...] = ()
    omitted_comparison_note_count: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, str) or not self.run_id.strip():
            raise ResearchError("Research source comparison run ID cannot be empty.")
        if not isinstance(self.question, str) or not self.question.strip():
            raise ResearchError("Research source comparison question cannot be empty.")
        if not isinstance(self.run_status, ResearchRunStatus):
            raise ResearchError("Research source comparison run status is invalid.")
        if not isinstance(self.sources, tuple) or not all(
            isinstance(item, ResearchSourceComparisonItem) for item in self.sources
        ):
            raise ResearchError(
                "Research source comparison entries must be an immutable tuple."
            )
        if not MIN_COMPARISON_SOURCES <= len(self.sources) <= MAX_COMPARISON_SOURCES:
            raise ResearchError("Research source comparison requires 2 to 5 sources.")
        document_ids = [item.source.document_id for item in self.sources]
        if len(document_ids) != len(set(document_ids)):
            raise ResearchError(
                "Research source comparison contains duplicate sources."
            )
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ResearchError("Research source comparison reason cannot be empty.")
        if not isinstance(self.comparison_notes, tuple) or not all(
            isinstance(note, ResearchSourceComparisonNoteRecord)
            for note in self.comparison_notes
        ):
            raise ResearchError(
                "Research source comparison notes must be an immutable tuple."
            )
        selected_document_ids = tuple(document_ids)
        if any(
            note.source_document_ids != selected_document_ids
            for note in self.comparison_notes
        ):
            raise ResearchError(
                "Research source comparison notes must match the selected source order."
            )
        if len(self.comparison_notes) > MAX_COMPARISON_NOTES:
            raise ResearchError("Research source comparison displays too many notes.")
        if (
            isinstance(self.omitted_comparison_note_count, bool)
            or not isinstance(self.omitted_comparison_note_count, int)
            or self.omitted_comparison_note_count < 0
        ):
            raise ResearchError(
                "Research source comparison omitted note count cannot be negative."
            )
        object.__setattr__(self, "run_id", self.run_id.strip())
        object.__setattr__(self, "question", self.question.strip())
        object.__setattr__(self, "reason", self.reason.strip())

    @property
    def total_comparison_note_count(self) -> int:
        """Return the complete matching note count without carrying all records."""
        return len(self.comparison_notes) + self.omitted_comparison_note_count
