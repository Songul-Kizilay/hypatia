"""Ephemeral coordination for one explicitly started research-plan execution.

Stages 2 and 3 of research-plan execution. This service owns execution state for
the current process only and performs no persistence.

Starting a plan records that execution began and advances no step. Advancing a
step runs exactly one connected research operation. Only an operation that
actually executed may mark a step as backed by real work; when no operation is
connected, or an operation reports that it performed nothing, the step is
blocked with a bounded reason instead of being reported as completed research.

Stage 3 connects one existing capability: the deterministic local knowledge
search. Source discovery, source fetching, evidence extraction, assessment, and
claims remain unconnected, and no network or LLM call is made here.

State lives here, not in CognitiveEngine, and is lost when the process exits.
That loss is reported explicitly rather than presented as a finished or
resumable execution.
"""

from __future__ import annotations

from typing import cast

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from core.Exceptions import ResearchError
from research.ResearchPlan import ResearchPlan
from research.ResearchPlanDraftService import (
    ResearchPlanDraftService,
    ResearchPlanStepDraft,
)
from research.ResearchPlanExecutionState import ResearchPlanExecutionState
from research.ResearchPlanStepOperation import ResearchPlanStepOperation
from response.ResponseComposer import ResponseComposer

RESEARCH_PLAN_EXECUTION_START_INTENT = "research_plan_execution_start"
RESEARCH_PLAN_EXECUTION_STATUS_INTENT = "research_plan_execution_status"
RESEARCH_PLAN_EXECUTION_CANCEL_INTENT = "research_plan_execution_cancel"
RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT = "research_plan_execution_advance"

MAX_ACTIVE_RESEARCH_PLAN_EXECUTIONS = 20


class ResearchPlanExecutionApplicationService:
    """Coordinate bounded ephemeral execution state without doing research."""

    def __init__(
        self,
        response_composer: ResponseComposer,
        draft_service: ResearchPlanDraftService | None = None,
        *,
        step_operation: ResearchPlanStepOperation | None = None,
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
        self._step_operation = step_operation
        self._max_active_executions = max_active_executions
        self._executions: dict[str, ResearchPlanExecutionState] = {}
        self._plans: dict[str, ResearchPlan] = {}

    @staticmethod
    def is_start_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == RESEARCH_PLAN_EXECUTION_START_INTENT

    @staticmethod
    def is_status_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == RESEARCH_PLAN_EXECUTION_STATUS_INTENT

    @staticmethod
    def is_cancel_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == RESEARCH_PLAN_EXECUTION_CANCEL_INTENT

    @staticmethod
    def is_advance_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT

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
        self._plans[plan.plan_id] = plan
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

    def process_advance(self, request: BrainRequest) -> BrainResponse:
        """Run one real research operation for the next pending step."""
        plan_id = self._normalized_plan_id(request)
        state = self._executions.get(plan_id)
        plan = self._plans.get(plan_id)
        if state is None or plan is None:
            return self._response_composer.research_plan_execution_missing(
                request,
                plan_id,
            )
        step_id = state.next_pending_step_id
        if step_id is None:
            return self._response_composer.research_plan_execution_rejected(
                request,
                "Research plan execution has no pending step to advance.",
            )
        if self._step_operation is None:
            return self._blocked(
                request,
                plan_id,
                state,
                step_id,
                "No research operation is connected; nothing was performed.",
            )

        step = next(
            candidate for candidate in plan.steps if candidate.step_id == step_id
        )
        try:
            running = state.start_step(step_id)
        except ResearchError as error:
            return self._response_composer.research_plan_execution_rejected(
                request,
                str(error),
            )
        try:
            result = self._step_operation.run(step)
        except ResearchError as error:
            failed = running.fail_step(step_id, str(error))
            self._executions[plan_id] = failed
            return self._response_composer.research_plan_execution_status(
                request,
                failed,
            )
        if not result.performed:
            return self._blocked(
                request,
                plan_id,
                running,
                step_id,
                result.detail,
            )
        completed = running.complete_step(
            step_id,
            result.detail,
            work_performed=True,
        )
        self._executions[plan_id] = completed
        return self._response_composer.research_plan_execution_status(
            request,
            completed,
        )

    def _blocked(
        self,
        request: BrainRequest,
        plan_id: str,
        state: ResearchPlanExecutionState,
        step_id: str,
        detail: str,
    ) -> BrainResponse:
        """Block a step instead of implying work that never happened."""
        blocked = state.block_step(step_id, detail)
        self._executions[plan_id] = blocked
        return self._response_composer.research_plan_execution_status(
            request,
            blocked,
        )

    @staticmethod
    def _normalized_plan_id(request: BrainRequest) -> str:
        value = request.metadata.get("research_plan_id")
        if not isinstance(value, str) or not value.strip():
            raise ResearchError("Research plan execution ID cannot be empty.")
        return value.strip()
