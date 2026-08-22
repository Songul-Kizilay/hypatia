"""Pure no-write construction of explicit user-authored Research plan drafts."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from core.Exceptions import ResearchError
from research.ResearchPlan import ResearchPlan
from research.ResearchPlanDraftPreview import ResearchPlanDraftPreview
from research.ResearchPlanStep import ResearchPlanStep

ResearchPlanStepDraft = tuple[str, tuple[str, ...]]


class ResearchPlanDraftService:
    """Validate explicit draft inputs without persistence or execution."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or (lambda: str(uuid4()))

    def preview(
        self,
        question: str,
        step_drafts: tuple[ResearchPlanStepDraft, ...],
    ) -> ResearchPlanDraftPreview:
        """Return a complete inert plan or one bounded validation failure."""
        try:
            steps = self._build_steps(step_drafts)
            plan = ResearchPlan(
                plan_id=self._id_factory(),
                question=question,
                steps=steps,
                created_at=self._clock(),
            )
        except ResearchError as error:
            return ResearchPlanDraftPreview.rejected(str(error))
        return ResearchPlanDraftPreview.ready(plan)

    @staticmethod
    def _build_steps(
        step_drafts: tuple[ResearchPlanStepDraft, ...],
    ) -> tuple[ResearchPlanStep, ...]:
        if not isinstance(step_drafts, tuple):
            raise ResearchError("Research plan draft steps must be an immutable tuple.")
        steps: list[ResearchPlanStep] = []
        for index, draft in enumerate(step_drafts, start=1):
            if not isinstance(draft, tuple) or len(draft) != 2:
                raise ResearchError("Research plan draft step is invalid.")
            instruction, source_ids = draft
            steps.append(
                ResearchPlanStep(
                    step_id=f"step-{index}",
                    instruction=instruction,
                    selected_source_document_ids=source_ids,
                )
            )
        return tuple(steps)
