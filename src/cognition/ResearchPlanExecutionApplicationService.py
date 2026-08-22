"""Ephemeral coordination for one explicitly started research-plan execution.

Stage 2 of research-plan execution. This service owns execution state for the
current process only. It performs no research work: no source discovery, no
source fetch, no evidence extraction, no assessment, no claim, no network, no
LLM, and no persistence.

Because no research operation runs yet, no step can be reported as completed
research. Starting a plan records that execution began; it does not advance any
step. Stage 3 connects real research operations one at a time, and only those
operations may mark a step as backed by real work.

State lives here, not in CognitiveEngine, and is lost when the process exits.
That loss is reported explicitly rather than presented as a finished or
resumable execution.
"""

from __future__ import annotations

from typing import cast

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from core.Exceptions import ResearchError
from research.ResearchPlanDraftService import (
    ResearchPlanDraftService,
    ResearchPlanStepDraft,
)
from research.ResearchPlanExecutionState import ResearchPlanExecutionState
from response.ResponseComposer import ResponseComposer

RESEARCH_PLAN_EXECUTION_START_INTENT = "research_plan_execution_start"
RESEARCH_PLAN_EXECUTION_STATUS_INTENT = "research_plan_execution_status"
RESEARCH_PLAN_EXECUTION_CANCEL_INTENT = "research_plan_execution_cancel"

MAX_ACTIVE_RESEARCH_PLAN_EXECUTIONS = 20


class ResearchPlanExecutionApplicationService:
    """Coordinate bounded ephemeral execution state without doing research."""

    def __init__(
        self,
        response_composer: ResponseComposer,
        draft_service: ResearchPlanDraftService | None = None,
        *,
        max_active_executions: int = MAX_ACTIVE_RESEARCH_PLAN_EXECUTIONS,
    ) -> None:
        if (
            isinstance(max_active_executions, bool)
            or not isinstance(max_active_executions, int)
            or max_active_executions < 1
        ):
            raise ValueError(
                "Research plan execution capacity must be a positive integer."
            )
        self._response_composer = response_composer
        self._draft_service = draft_service or ResearchPlanDraftService()
        self._max_active_executions = max_active_executions
        self._executions: dict[str, ResearchPlanExecutionState] = {}

    @staticmethod
    def is_start_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == RESEARCH_PLAN_EXECUTION_START_INTENT

    @staticmethod
    def is_status_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == RESEARCH_PLAN_EXECUTION_STATUS_INTENT

    @staticmethod
    def is_cancel_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == RESEARCH_PLAN_EXECUTION_CANCEL_INTENT

    def process_start(self, request: BrainRequest) -> BrainResponse:
        """Start execution for one authored plan, or explain why it cannot."""
        question = request.metadata.get("research_plan_question")
        step_drafts = request.metadata.get("research_plan_steps")
        preview = self._draft_service.preview(
            cast(str, question),
            cast(tuple[ResearchPlanStepDraft, ...], step_drafts),
        )
        if not preview.allowed:
            return self._response_composer.research_plan_execution_rejected(
                request,
                preview.reason,
            )
        plan = preview.plan
        assert plan is not None

        if plan.plan_id in self._executions:
            return self._response_composer.research_plan_execution_rejected(
                request,
                "Research plan already has execution state in this process.",
            )
        if len(self._executions) >= self._max_active_executions:
            return self._response_composer.research_plan_execution_rejected(
                request,
                "Research plan execution capacity is full in this process.",
            )

        state = ResearchPlanExecutionState.prepare(plan).start()
        self._executions[plan.plan_id] = state
        return self._response_composer.research_plan_execution_status(request, state)

    def process_status(self, request: BrainRequest) -> BrainResponse:
        """Report current ephemeral state, or that none exists in this process."""
        plan_id = self._normalized_plan_id(request)
        state = self._executions.get(plan_id)
        if state is None:
            return self._response_composer.research_plan_execution_missing(
                request,
                plan_id,
            )
        return self._response_composer.research_plan_execution_status(request, state)

    def process_cancel(self, request: BrainRequest) -> BrainResponse:
        """Cancel unfinished steps while preserving completed-step history."""
        plan_id = self._normalized_plan_id(request)
        state = self._executions.get(plan_id)
        if state is None:
            return self._response_composer.research_plan_execution_missing(
                request,
                plan_id,
            )
        try:
            cancelled = state.cancel("Cancelled by explicit user request.")
        except ResearchError as error:
            return self._response_composer.research_plan_execution_rejected(
                request,
                str(error),
            )
        self._executions[plan_id] = cancelled
        return self._response_composer.research_plan_execution_status(
            request,
            cancelled,
        )

    @staticmethod
    def _normalized_plan_id(request: BrainRequest) -> str:
        value = request.metadata.get("research_plan_id")
        if not isinstance(value, str) or not value.strip():
            raise ResearchError("Research plan execution ID cannot be empty.")
        return value.strip()
