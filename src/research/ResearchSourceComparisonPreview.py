"""Immutable side-by-side preview for explicitly selected research sources."""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSourceComparisonItem import ResearchSourceComparisonItem

MIN_COMPARISON_SOURCES = 2
MAX_COMPARISON_SOURCES = 5


@dataclass(frozen=True, slots=True)
class ResearchSourceComparisonPreview:
    """Expose manual comparison material without producing a conclusion."""

    run_id: str
    question: str
    run_status: ResearchRunStatus
    sources: tuple[ResearchSourceComparisonItem, ...]
    reason: str

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
        object.__setattr__(self, "run_id", self.run_id.strip())
        object.__setattr__(self, "question", self.question.strip())
        object.__setattr__(self, "reason", self.reason.strip())
