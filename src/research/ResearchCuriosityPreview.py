"""What curiosity found, before anything is written down.

A preview is the honest middle step: gaps were detected and questions were
drafted, but nothing is persisted and no research has been performed. Building
one changes no run, no claim, and no source.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchCuriosityQuestion import ResearchCuriosityQuestion
from research.ResearchKnowledgeGap import ResearchKnowledgeGap


@dataclass(frozen=True, slots=True)
class ResearchCuriosityPreview:
    """Report detected gaps and drafted questions without storing either."""

    run_id: str
    gaps: tuple[ResearchKnowledgeGap, ...]
    questions: tuple[ResearchCuriosityQuestion, ...]
    stored: bool = False

    def __post_init__(self) -> None:
        if not self.run_id.strip():
            raise ResearchError("Curiosity preview run ID cannot be empty.")
        if any(gap.run_id != self.run_id for gap in self.gaps):
            raise ResearchError("Curiosity preview gaps must share one run.")
        if any(question.run_id != self.run_id for question in self.questions):
            raise ResearchError("Curiosity preview questions must share one run.")
        gap_ids = {gap.gap_id for gap in self.gaps}
        if any(question.gap_id not in gap_ids for question in self.questions):
            raise ResearchError("Every curiosity question needs a detected gap.")

    @property
    def gap_count(self) -> int:
        """Return how many gaps this preview reports."""
        return len(self.gaps)

    @property
    def question_count(self) -> int:
        """Return how many questions this preview proposes."""
        return len(self.questions)
