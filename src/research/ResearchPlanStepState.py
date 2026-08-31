"""Immutable execution state for one research-plan step."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from core.Exceptions import ResearchError
from research.ResearchAttemptResolution import ResearchAttemptResolution
from research.ResearchAuthorizer import ResearchAuthorizer
from research.ResearchPlanStepStatus import ResearchPlanStepStatus

MAX_RESEARCH_PLAN_STEP_DETAIL_CHARACTERS = 500


@dataclass(frozen=True, slots=True)
class ResearchPlanStepState:
    """Keep one step identity, its bounded status, and one bounded detail."""

    step_id: str
    status: ResearchPlanStepStatus = ResearchPlanStepStatus.PENDING
    detail: str = ""
    work_performed: bool = False
    operation: str = ""
    #: A human ruling about an attempt nobody saw the end of. It is canonical
    #: state rather than wording, so what an operator decided survives a restart
    #: and can never be re-derived from prose.
    resolution: ResearchAttemptResolution = ResearchAttemptResolution.NONE
    resolved_at: datetime | None = None
    resolved_by: ResearchAuthorizer | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.step_id, str) or not self.step_id.strip():
            raise ResearchError("Research plan step state ID cannot be empty.")
        if not isinstance(self.status, ResearchPlanStepStatus):
            raise ResearchError("Research plan step state status is invalid.")
        if not isinstance(self.detail, str):
            raise ResearchError("Research plan step state detail must be text.")
        if not isinstance(self.work_performed, bool):
            raise ResearchError("Research plan step work flag must be boolean.")
        if not isinstance(self.operation, str):
            raise ResearchError("Research plan step operation must be text.")
        if self.work_performed and self.status is ResearchPlanStepStatus.PENDING:
            raise ResearchError("A pending research plan step performed no work.")
        if self.work_performed and not self.operation.strip():
            raise ResearchError(
                "Performed research work must record its operation name."
            )
        if not isinstance(self.resolution, ResearchAttemptResolution):
            raise ResearchError("Research plan step resolution is invalid.")
        ruled = self.resolution is not ResearchAttemptResolution.NONE
        if ruled and not isinstance(self.resolved_at, datetime):
            raise ResearchError("A research plan step ruling must record when.")
        if ruled and not isinstance(self.resolved_by, ResearchAuthorizer):
            raise ResearchError("A research plan step ruling must record who.")
        if not ruled and (self.resolved_at is not None or self.resolved_by is not None):
            raise ResearchError("An unruled research plan step has no ruling record.")
        detail = self.detail.strip()
        if len(detail) > MAX_RESEARCH_PLAN_STEP_DETAIL_CHARACTERS:
            raise ResearchError("Research plan step state detail is too long.")
        object.__setattr__(self, "step_id", self.step_id.strip())
        object.__setattr__(self, "detail", detail)
        object.__setattr__(self, "operation", self.operation.strip())

    def with_status(
        self,
        status: ResearchPlanStepStatus,
        detail: str = "",
        work_performed: bool = False,
        operation: str = "",
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
            operation=operation,
        )

    def ruled(
        self,
        resolution: ResearchAttemptResolution,
        status: ResearchPlanStepStatus,
        moment: datetime,
        resolved_by: ResearchAuthorizer,
        detail: str = "",
        work_performed: bool = False,
        operation: str = "",
    ) -> ResearchPlanStepState:
        """Return this step carrying one human ruling about its attempt.

        Separate from `with_status` because the two mean different things. That
        one records what Hypatia observed; this one records what a person said,
        and keeps who said it and when alongside the claim itself.
        """
        return replace(
            self,
            status=status,
            detail=detail,
            work_performed=work_performed,
            operation=operation,
            resolution=resolution,
            resolved_at=moment,
            resolved_by=resolved_by,
        )
