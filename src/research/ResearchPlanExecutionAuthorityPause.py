"""Durable record that one execution step is paused pending named authority.

This is a control-plane record, not authority. It names exactly which
existing authority domain (`ResearchAuthorityRequirementKind`), which exact
plan content (`plan_digest`) and which exact research run
(`research_run_id`) would need to be matched by a fresh, independently
verified authorization of that domain before this step could proceed. It
carries no method that authorizes, consumes, or grants anything, and no code
elsewhere may treat it as if it were an authorization, a grant, or a
consulted verdict: it can only be compared against, never presented in place
of, the authorization type it names.

Immutable, typed, and deterministic: two pauses with the same fields are
equal, and there is no way to construct one that both step-matches and
digest-matches by accident, because every identity field is required and
validated together.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchAuthorityRequirementKind import ResearchAuthorityRequirementKind
from research.ResearchPlanDigest import is_plan_digest

MAX_AUTHORITY_PAUSE_DETAIL_CHARACTERS = 500


@dataclass(frozen=True, slots=True)
class ResearchPlanExecutionAuthorityPause:
    """One step's exact, named, unmet authority requirement."""

    requirement_kind: ResearchAuthorityRequirementKind
    step_id: str
    plan_digest: str
    research_run_id: str
    detail: str

    def __post_init__(self) -> None:
        if not isinstance(self.requirement_kind, ResearchAuthorityRequirementKind):
            raise ResearchError("Authority pause requirement kind is invalid.")
        if not isinstance(self.step_id, str) or not self.step_id.strip():
            raise ResearchError("Authority pause step ID cannot be empty.")
        if not is_plan_digest(self.plan_digest):
            raise ResearchError("Authority pause plan digest is invalid.")
        if (
            not isinstance(self.research_run_id, str)
            or not self.research_run_id.strip()
        ):
            raise ResearchError("Authority pause research run ID cannot be empty.")
        if not isinstance(self.detail, str) or not self.detail.strip():
            raise ResearchError("Authority pause requires a reason.")
        if len(self.detail.strip()) > MAX_AUTHORITY_PAUSE_DETAIL_CHARACTERS:
            raise ResearchError("Authority pause detail is too long.")
        object.__setattr__(self, "step_id", self.step_id.strip())
        object.__setattr__(self, "research_run_id", self.research_run_id.strip())
        object.__setattr__(self, "detail", self.detail.strip())
