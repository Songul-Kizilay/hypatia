"""One bounded observation about how a research run actually went.

A finding points at something already persisted — a recorded failure, a
contradiction, a superseded claim, a thin claim, an uncited source — and says
what it means for the *process*. It never says what is true about the subject
being researched.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.DisplayText import one_line
from research.ReflectionFindingKind import ReflectionFindingKind

MAX_FINDING_DETAIL_LENGTH = 300


@dataclass(frozen=True, slots=True)
class ResearchReflectionFinding:
    """Record one bounded, evidence-derived observation about a run."""

    kind: ReflectionFindingKind
    subject_id: str
    detail: str

    def __post_init__(self) -> None:
        # A reflection is rendered one finding per line. Persisted failure
        # reasons and other authored text can contain line breaks, so keep the
        # record-level guarantee here: no producer or renderer can accidentally
        # turn one finding into a second, forged-looking entry.
        object.__setattr__(self, "detail", one_line(self.detail))
        if not isinstance(self.kind, ReflectionFindingKind):
            raise ResearchError("Reflection finding kind must be a bounded category.")
        if not self.detail.strip():
            raise ResearchError("Reflection finding detail cannot be empty.")
        if len(self.detail) > MAX_FINDING_DETAIL_LENGTH:
            raise ResearchError("Reflection finding detail is too long.")

    @property
    def order(self) -> int:
        """Return the report position of this finding's kind."""
        return self.kind.order

    @property
    def is_lesson(self) -> bool:
        """Return whether this finding describes something to learn from."""
        return self.kind.is_lesson
