"""Explicit Brain-facing boundary for no-write Research plan previews."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from research.ResearchFailureLesson import ResearchFailureLesson
from research.ResearchPlanDraftPreview import ResearchPlanDraftPreview
from research.ResearchPlanDraftService import (
    ResearchPlanDraftService,
    ResearchPlanStepDraft,
)
from response.ResponseComposer import ResponseComposer


class ResearchPlanPreviewApplicationService:
    """Delegate one structured draft request without persistence or execution."""

    def __init__(
        self,
        response_composer: ResponseComposer,
        draft_service: ResearchPlanDraftService | None = None,
        lesson_advisor: (
            Callable[[str], tuple[ResearchFailureLesson, ...]] | None
        ) = None,
    ) -> None:
        self._response_composer = response_composer
        self._draft_service = draft_service or ResearchPlanDraftService()
        self._lesson_advisor = lesson_advisor

    @staticmethod
    def is_draft_preview_request(request: BrainRequest) -> bool:
        """Recognize only the explicit structured plan-preview intent."""
        return request.metadata.get("intent") == "research_plan_draft_preview"

    def process_draft_preview(self, request: BrainRequest) -> BrainResponse:
        """Compose the complete no-write preview or bounded rejection."""
        question = cast(str, request.metadata.get("research_plan_question"))
        step_drafts = cast(
            tuple[ResearchPlanStepDraft, ...],
            request.metadata.get("research_plan_steps"),
        )
        preview = self._draft_service.preview(question, step_drafts)
        prior_lessons = self._prior_lessons(preview)
        return self._response_composer.research_plan_draft_preview(
            request,
            preview,
            prior_lessons,
        )

    def _prior_lessons(
        self,
        preview: ResearchPlanDraftPreview,
    ) -> tuple[ResearchFailureLesson, ...]:
        """Decorate a valid preview with bounded advice, never a precondition."""
        advisor = self._lesson_advisor
        plan = preview.plan
        if advisor is None or plan is None:
            return ()
        try:
            return advisor(plan.question)
        except Exception:
            # A plan preview has already succeeded. Advisory recall must not
            # turn that success into a failure or change the plan itself.
            return ()
