"""Transient unaccepted proposals bound to one execution attempt."""

from dataclasses import dataclass, field

from core.Exceptions import ResearchError
from research.SemanticEvidenceCandidate import SemanticEvidenceCandidate
from research.SemanticEvidenceRequest import SemanticEvidenceRequest


@dataclass(frozen=True, slots=True)
class SemanticEvidenceStepResult:
    execution_id: str
    step_id: str
    request: SemanticEvidenceRequest = field(repr=False)
    candidates: tuple[SemanticEvidenceCandidate, ...] = field(repr=False)

    def __post_init__(self) -> None:
        if (
            any(
                not isinstance(v, str) or not v.strip() or len(v) > 200
                for v in (self.execution_id, self.step_id)
            )
            or not isinstance(self.request, SemanticEvidenceRequest)
            or not isinstance(self.candidates, tuple)
            or len(self.candidates) > self.request.limit
            or any(
                not isinstance(c, SemanticEvidenceCandidate)
                or c.preview not in self.request.previews
                for c in self.candidates
            )
        ):
            raise ResearchError("Semantic evidence result is invalid.")
