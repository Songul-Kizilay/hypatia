"""Bounded no-write result for one explicit Research plan draft."""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchPlan import ResearchPlan

MAX_RESEARCH_PLAN_DRAFT_REASON_CHARACTERS = 500


@dataclass(frozen=True, slots=True)
class ResearchPlanDraftPreview:
    """Return either one immutable plan or one safe validation reason."""

    allowed: bool
    reason: str
    plan: ResearchPlan | None

    def __post_init__(self) -> None:
        if not isinstance(self.allowed, bool):
            raise ResearchError("Research plan draft decision must be boolean.")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ResearchError("Research plan draft reason cannot be empty.")
        reason = self.reason.strip()
        if len(reason) > MAX_RESEARCH_PLAN_DRAFT_REASON_CHARACTERS:
            raise ResearchError("Research plan draft reason is too long.")
        if self.allowed and not isinstance(self.plan, ResearchPlan):
            raise ResearchError("Allowed research plan draft requires a plan.")
        if not self.allowed and self.plan is not None:
            raise ResearchError("Rejected research plan draft cannot contain a plan.")
        object.__setattr__(self, "reason", reason)

    @classmethod
    def ready(cls, plan: ResearchPlan) -> ResearchPlanDraftPreview:
        """Create the no-write result shown before any future confirmation."""
        return cls(
            allowed=True,
            reason="Research plan draft is ready for explicit confirmation.",
            plan=plan,
        )

    @classmethod
    def rejected(cls, reason: str) -> ResearchPlanDraftPreview:
        """Create one bounded validation failure without a partial plan."""
        return cls(allowed=False, reason=reason, plan=None)
