"""Explicit Brain-facing boundary for no-write Research plan previews."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from core.Exceptions import ResearchError
from research.ResearchAcquisitionBatchDraft import preview_acquisition_batch
from research.ResearchFailureLesson import ResearchFailureLesson
from research.ResearchPlanDraftPreview import ResearchPlanDraftPreview
from research.ResearchPlanDraftService import (
    RESEARCH_PLAN_RESTRICTION_KEY,
    RESEARCH_PLAN_TARGET_BINDING_KEY,
    ResearchPlanDraftService,
    ResearchPlanStepDraft,
)
from research.ResearchPlanFailureLessonTrace import (
    ResearchPlanFailureLessonTrace,
    ResearchPlanFailureLessonTracer,
)
from research.ResearchPlanRestriction import ResearchPlanRestriction
from research.ResearchPlanTargetBinding import ResearchPlanTargetBinding
from research.ResearchRunManager import ResearchRunManager
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
        lesson_tracer: ResearchPlanFailureLessonTracer | None = None,
        research_run_manager: ResearchRunManager | None = None,
    ) -> None:
        self._response_composer = response_composer
        self._draft_service = draft_service or ResearchPlanDraftService()
        self._lesson_advisor = lesson_advisor
        self._lesson_tracer = lesson_tracer or ResearchPlanFailureLessonTracer()
        self._research_run_manager = research_run_manager

    @staticmethod
    def is_draft_preview_request(request: BrainRequest) -> bool:
        """Recognize only the explicit structured plan-preview intent."""
        return request.metadata.get("intent") in (
            "research_plan_draft_preview",
            "research_question_plan_preview",
            "research_acquisition_batch_preview",
        )

    def process_draft_preview(self, request: BrainRequest) -> BrainResponse:
        """Compose the complete no-write preview or bounded rejection."""
        if request.metadata.get("intent") == "research_question_plan_preview":
            return self._process_question_preview(request)
        if request.metadata.get("intent") == "research_acquisition_batch_preview":
            return self._process_acquisition_preview(request)
        question = cast(str, request.metadata.get("research_plan_question"))
        step_drafts = cast(
            tuple[ResearchPlanStepDraft, ...],
            request.metadata.get("research_plan_steps"),
        )
        # Supplied as their own field. A constraint is never inferred from a
        # step's wording, and a step is never demoted by looking like one.
        constraint_drafts = cast(
            tuple[str, ...],
            request.metadata.get("research_plan_constraints") or (),
        )
        preview = self._draft_service.preview(
            question,
            step_drafts,
            constraint_drafts,
            cast(
                ResearchPlanRestriction | None,
                request.metadata.get(RESEARCH_PLAN_RESTRICTION_KEY),
            ),
            target_binding=cast(
                ResearchPlanTargetBinding | None,
                request.metadata.get(RESEARCH_PLAN_TARGET_BINDING_KEY),
            ),
        )
        prior_lessons = self._prior_lessons(preview)
        lesson_trace = self._lesson_trace(preview, prior_lessons)
        return self._response_composer.research_plan_draft_preview(
            request,
            preview,
            prior_lessons,
            lesson_trace,
        )

    def _process_acquisition_preview(self, request: BrainRequest) -> BrainResponse:
        """Resolve membership from current run state, never caller-supplied records."""
        try:
            if self._research_run_manager is None:
                raise ResearchError("Research run storage is unavailable.")
            if any(
                key in request.metadata
                for key in (
                    "research_plan_question",
                    "research_plan_steps",
                    "research_plan_constraints",
                    RESEARCH_PLAN_RESTRICTION_KEY,
                    RESEARCH_PLAN_TARGET_BINDING_KEY,
                )
            ):
                raise ResearchError(
                    "Candidate batch planning cannot replace authored plans or targets."
                )
            run = self._research_run_manager.get(
                cast(str, request.metadata.get("research_run_id"))
            )
            preview = preview_acquisition_batch(
                run,
                cast(str, request.metadata.get("discovery_id")),
                cast(tuple[str, ...], request.metadata.get("selected_candidate_urls")),
                draft_service=self._draft_service,
            )
        except ResearchError as error:
            preview = ResearchPlanDraftPreview.rejected(str(error))
        return self._response_composer.research_plan_draft_preview(request, preview)

    def _process_question_preview(self, request: BrainRequest) -> BrainResponse:
        """Use one explicit template without discarding an authored plan."""
        if any(
            key in request.metadata
            for key in (
                "research_plan_steps",
                "research_plan_constraints",
                RESEARCH_PLAN_RESTRICTION_KEY,
                RESEARCH_PLAN_TARGET_BINDING_KEY,
            )
        ):
            preview = ResearchPlanDraftPreview.rejected(
                "Question planning cannot replace supplied steps, "
                "constraints or targets."
            )
        else:
            preview = self._draft_service.preview_question(
                cast(str, request.metadata.get("research_plan_question")),
                cast(str, request.metadata.get("discovery_provider")),
            )
        lessons = self._prior_lessons(preview)
        return self._response_composer.research_plan_draft_preview(
            request, preview, lessons, self._lesson_trace(preview, lessons)
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

    def _lesson_trace(
        self,
        preview: ResearchPlanDraftPreview,
        lessons: tuple[ResearchFailureLesson, ...],
    ) -> ResearchPlanFailureLessonTrace | None:
        """Trace shown lessons against authored steps, changing nothing."""
        if preview.plan is None or not lessons:
            return None
        try:
            return self._lesson_tracer.trace(preview.plan, lessons)
        except Exception:
            # Like recall itself, this is explanatory decoration on an
            # already-valid preview. It may disappear; the preview may not.
            return None
