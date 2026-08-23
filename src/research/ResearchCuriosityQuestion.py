"""One ranked question the system proposes to itself about its own gaps.

A curiosity question is a proposal, not a task. Nothing in this module runs
research, and accepting a question deliberately does not create a plan or queue
a background task: turning a question into work stays a separate, explicit human
decision.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime

from core.Exceptions import ResearchError
from research.CuriosityQuestionStatus import CuriosityQuestionStatus
from research.ResearchKnowledgeGapKind import ResearchKnowledgeGapKind

MAX_QUESTION_TEXT_LENGTH = 300


@dataclass(frozen=True, slots=True)
class ResearchCuriosityQuestion:
    """Record one proposed follow-up question derived from a detected gap."""

    question_id: str
    gap_id: str
    run_id: str
    kind: ResearchKnowledgeGapKind
    subject_id: str
    text: str
    rank_score: int
    generated_at: datetime
    status: CuriosityQuestionStatus = CuriosityQuestionStatus.PROPOSED
    decided_at: datetime | None = None

    def __post_init__(self) -> None:
        for value, label in (
            (self.question_id, "question ID"),
            (self.gap_id, "gap ID"),
            (self.run_id, "run ID"),
            (self.text, "text"),
        ):
            if not value.strip():
                raise ResearchError(f"Curiosity question {label} cannot be empty.")
        if not isinstance(self.kind, ResearchKnowledgeGapKind):
            raise ResearchError("Curiosity question kind must be a bounded category.")
        if not isinstance(self.status, CuriosityQuestionStatus):
            raise ResearchError("Curiosity question status must be a bounded state.")
        if len(self.text) > MAX_QUESTION_TEXT_LENGTH:
            raise ResearchError("Curiosity question text is too long.")
        if isinstance(self.rank_score, bool) or not isinstance(self.rank_score, int):
            raise ResearchError("Curiosity question rank must be a whole number.")
        if self.rank_score < 0:
            raise ResearchError("Curiosity question rank cannot be negative.")
        if self.generated_at.tzinfo is None:
            raise ResearchError("Curiosity question time must be timezone aware.")
        if self.generated_at > datetime.now(UTC):
            raise ResearchError("Curiosity question cannot be generated in the future.")
        self._validate_decision()

    def _validate_decision(self) -> None:
        if self.status.decided and self.decided_at is None:
            raise ResearchError("A decided curiosity question must record its time.")
        if not self.status.decided and self.decided_at is not None:
            raise ResearchError("A proposed curiosity question records no decision.")
        if self.decided_at is None:
            return
        if self.decided_at.tzinfo is None:
            raise ResearchError("Curiosity decision time must be timezone aware.")
        if self.decided_at < self.generated_at:
            raise ResearchError("Curiosity question cannot be decided before proposal.")

    def accepted(self, moment: datetime) -> ResearchCuriosityQuestion:
        """Mark this question worth pursuing without starting any research."""
        return self._decided(CuriosityQuestionStatus.ACCEPTED, moment)

    def dismissed(self, moment: datetime) -> ResearchCuriosityQuestion:
        """Mark this question not worth pursuing."""
        return self._decided(CuriosityQuestionStatus.DISMISSED, moment)

    def _decided(
        self,
        status: CuriosityQuestionStatus,
        moment: datetime,
    ) -> ResearchCuriosityQuestion:
        if self.status.decided:
            raise ResearchError(
                f"A {self.status.value} curiosity question cannot be decided again."
            )
        return replace(self, status=status, decided_at=moment)
