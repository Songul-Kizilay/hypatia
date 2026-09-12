"""Bounded inert contract for one user-authored Research plan."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.Exceptions import ResearchError
from research.ResearchMissionScope import ResearchMissionScope
from research.ResearchPlanConstraint import ResearchPlanConstraint
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchPlanTargetBinding import ResearchPlanTargetBinding

MAX_RESEARCH_PLAN_ID_CHARACTERS = 200
MAX_RESEARCH_PLAN_QUESTION_CHARACTERS = 2_000
MAX_RESEARCH_PLAN_STEPS = 20
MAX_RESEARCH_PLAN_CONSTRAINTS = 20


@dataclass(frozen=True, slots=True)
class ResearchPlan:
    """Preserve explicit step order without execution or lifecycle state."""

    plan_id: str
    question: str
    steps: tuple[ResearchPlanStep, ...]
    created_at: datetime
    #: Appended after the original fields so an empty constraint tuple can be
    #: skipped by the digest and retain the original step-only identity.
    constraints: tuple[ResearchPlanConstraint, ...] = ()
    #: Absent for existing reference research; present values enter approval.
    target_binding: ResearchPlanTargetBinding | None = None
    mission_scope: ResearchMissionScope | None = None

    def __post_init__(self) -> None:
        if self.mission_scope is not None:
            if not isinstance(self.mission_scope, ResearchMissionScope):
                raise ResearchError("Research mission scope is invalid.")
            if self.target_binding is not None:
                raise ResearchError(
                    "Reference missions do not authorize target testing."
                )
            if not isinstance(self.steps, tuple) or not all(
                isinstance(step, ResearchPlanStep) for step in self.steps
            ):
                raise ResearchError("Mission steps are invalid.")
            self.mission_scope.validate_steps(self.steps)
        plan_id = self._normalize_bounded_text(
            self.plan_id,
            "Research plan ID",
            MAX_RESEARCH_PLAN_ID_CHARACTERS,
        )
        question = self._normalize_bounded_text(
            self.question,
            "Research plan question",
            MAX_RESEARCH_PLAN_QUESTION_CHARACTERS,
        )
        if not isinstance(self.steps, tuple) or not self.steps:
            raise ResearchError("Research plan requires an immutable step tuple.")
        if len(self.steps) > MAX_RESEARCH_PLAN_STEPS:
            raise ResearchError("Research plan has too many steps.")
        if not all(isinstance(step, ResearchPlanStep) for step in self.steps):
            raise ResearchError("Research plan contains an invalid step.")
        if any(
            step.semantic_comparison_binding is not None
            and step.semantic_comparison_binding.request.question != question
            for step in self.steps
        ):
            raise ResearchError("Comparison input must bind the exact plan question.")
        step_ids = tuple(step.step_id for step in self.steps)
        if len(step_ids) != len(set(step_ids)):
            raise ResearchError("Research plan contains duplicate step IDs.")
        if (
            not isinstance(self.created_at, datetime)
            or self.created_at.utcoffset() is None
        ):
            raise ResearchError("Research plan creation time must be timezone-aware.")
        if not isinstance(self.constraints, tuple):
            raise ResearchError("Research plan requires an immutable constraint tuple.")
        if len(self.constraints) > MAX_RESEARCH_PLAN_CONSTRAINTS:
            raise ResearchError("Research plan has too many constraints.")
        if not all(
            isinstance(constraint, ResearchPlanConstraint)
            for constraint in self.constraints
        ):
            raise ResearchError("Research plan contains an invalid constraint.")
        if self.target_binding is not None:
            if not isinstance(self.target_binding, ResearchPlanTargetBinding):
                raise ResearchError("Research plan target binding is invalid.")
            # Only the existing bounded target HTTPS retrieval path is wired.
            # Discovery providers and other operations have separate boundaries.
            if any(
                step.capability
                not in {
                    ResearchPlanStepCapability.SOURCE_FETCH,
                    ResearchPlanStepCapability.SOURCE_ACCEPT,
                }
                for step in self.steps
            ):
                raise ResearchError(
                    "Target-bound plans support only source fetch and source accept."
                )
        object.__setattr__(self, "plan_id", plan_id)
        object.__setattr__(self, "question", question)

    @property
    def selected_source_document_ids(self) -> tuple[str, ...]:
        """Return the exact first-selected source order across all steps."""
        return tuple(
            dict.fromkeys(
                source_id
                for step in self.steps
                for source_id in step.selected_source_document_ids
            )
        )

    @staticmethod
    def _normalize_bounded_text(value: str, label: str, maximum: int) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ResearchError(f"{label} cannot be empty.")
        normalized = value.strip()
        if len(normalized) > maximum:
            raise ResearchError(f"{label} is too long.")
        return normalized
