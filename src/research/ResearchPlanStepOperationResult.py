"""Immutable outcome of one real research operation for a plan step."""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError

MAX_RESEARCH_STEP_OPERATION_DETAIL_CHARACTERS = 500


@dataclass(frozen=True, slots=True)
class ResearchPlanStepOperationResult:
    """Report whether real work ran and one bounded factual summary.

    ``performed`` is set only by an operation that actually executed. It is the
    single signal allowed to mark a step as backed by real research work.
    """

    performed: bool
    detail: str

    def __post_init__(self) -> None:
        if not isinstance(self.performed, bool):
            raise ResearchError("Research step operation flag must be boolean.")
        if not isinstance(self.detail, str) or not self.detail.strip():
            raise ResearchError("Research step operation detail cannot be empty.")
        detail = self.detail.strip()
        if len(detail) > MAX_RESEARCH_STEP_OPERATION_DETAIL_CHARACTERS:
            raise ResearchError("Research step operation detail is too long.")
        object.__setattr__(self, "detail", detail)
