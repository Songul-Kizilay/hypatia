"""Transient tentative comparison, bound to one canonical attempt."""

from dataclasses import dataclass, field

from core.Exceptions import ResearchError
from research.SemanticComparisonCandidate import SemanticComparisonCandidate
from research.SemanticComparisonRequest import SemanticComparisonRequest


@dataclass(frozen=True, slots=True)
class SemanticComparisonStepResult:
    execution_id: str
    step_id: str
    request: SemanticComparisonRequest = field(repr=False)
    candidates: tuple[SemanticComparisonCandidate, ...] = field(repr=False)

    def __post_init__(self) -> None:
        if (
            any(
                not isinstance(v, str) or not v.strip() or len(v) > 200
                for v in (self.execution_id, self.step_id)
            )
            or not isinstance(self.request, SemanticComparisonRequest)
            or not isinstance(self.candidates, tuple)
            or len(self.candidates) > self.request.limit
            or any(
                not isinstance(c, SemanticComparisonCandidate)
                or c.request != self.request
                for c in self.candidates
            )
        ):
            raise ResearchError("Invalid semantic comparison result.")
        pairs = [(c.left_quote, c.right_quote) for c in self.candidates]
        if len(pairs) != len(set(pairs)):
            raise ResearchError("Duplicate semantic comparison result.")
