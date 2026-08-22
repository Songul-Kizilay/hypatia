"""Immutable execution state for one research-plan step."""

from __future__ import annotations

from dataclasses import dataclass, replace

from core.Exceptions import ResearchError
from research.ResearchPlanStepStatus import ResearchPlanStepStatus

MAX_RESEARCH_PLAN_STEP_DETAIL_CHARACTERS = 500


@dataclass(frozen=True, slots=True)
class ResearchPlanStepState:
    """Keep one step identity, its bounded status, and one bounded detail."""

    step_id: str
    status: ResearchPlanStepStatus = ResearchPlanStepStatus.PENDING
    detail: str = ""
    work_performed: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.step_id, str) or not self.step_id.strip():
            raise ResearchError("Research plan step state ID cannot be empty.")
        if not isinstance(self.status, ResearchPlanStepStatus):
            raise ResearchError("Research plan step state status is invalid.")
        if not isinstance(self.detail, str):
            raise ResearchError("Research plan step state detail must be text.")
        if not isinstance(self.work_performed, bool):
            raise ResearchError("Research plan step work flag must be boolean.")
        if self.work_performed and self.status is ResearchPlanStepStatus.PENDING:
            raise ResearchError("A pending research plan step performed no work.")
        detail = self.detail.strip()
        if len(detail) > MAX_RESEARCH_PLAN_STEP_DETAIL_CHARACTERS:
            raise ResearchError("Research plan step state detail is too long.")
        object.__setattr__(self, "step_id", self.step_id.strip())
        object.__setattr__(self, "detail", detail)

    def with_status(
        self,
        status: ResearchPlanStepStatus,
        detail: str = "",
        work_performed: bool = False,
    ) -> ResearchPlanStepState:
        """Return a new state carrying the requested status, detail, and origin.

        ``work_performed`` records whether a real research operation backed this
        transition. It never becomes true on its own, so a state-machine advance
        can never masquerade as completed research work.
        """
        return replace(
            self,
            status=status,
            detail=detail,
            work_performed=work_performed,
        )
