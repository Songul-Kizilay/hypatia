"""Ephemeral coordination for one explicitly started research-plan execution.

Stages 2 and 3 of research-plan execution. This service owns execution state for
the current process only and performs no persistence.

Starting a plan records that execution began and advances no step. Advancing a
step runs exactly one connected research operation. Only an operation that
actually executed may mark a step as backed by real work; when no operation is
connected, or an operation reports that it performed nothing, the step is
blocked with a bounded reason instead of being reported as completed research.

Operation selection is an explicit table lookup on the step's declared typed
capability, never a heuristic over authored instruction text. A step declaring no
capability, or a capability with no registered operation, is blocked rather than
routed to something else.

A completed operation proves only that the operation ran. It is not evidence and
it is not a verified claim; evidence and claims still go through the existing
research evidence pipeline, which remains unconnected here.

State lives here, not in CognitiveEngine, and is lost when the process exits.
That loss is reported explicitly rather than presented as a finished or
resumable execution.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from cognition.ResearchPlanExecutionEvents import (
    ExecutionBlockReason,
    ResearchPlanExecutionEvents,
)
from core.Exceptions import ResearchError
from eventbus.EventBus import EventBus
from research.ResearchExecutionStore import ResearchExecutionStore
from research.ResearchPlan import ResearchPlan
from research.ResearchPlanDraftService import (
    ResearchPlanDraftService,
    ResearchPlanStepDraft,
)
from research.ResearchPlanExecutionContext import ResearchPlanExecutionContext
from research.ResearchPlanExecutionSnapshot import (
    ResearchPlanExecutionSnapshot,
)
from research.ResearchPlanExecutionState import ResearchPlanExecutionState
from research.ResearchPlanOperationRegistry import ResearchPlanOperationRegistry
from research.ResearchPlanStepStatus import ResearchPlanStepStatus
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
        operation_registry: ResearchPlanOperationRegistry | None = None,
        event_bus: EventBus | None = None,
        execution_store: ResearchExecutionStore | None = None,
        clock: Callable[[], datetime] | None = None,
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
        self._operation_registry = operation_registry or ResearchPlanOperationRegistry()
        self._events = ResearchPlanExecutionEvents(event_bus)
        self._max_active_executions = max_active_executions
        self._executions: dict[str, ResearchPlanExecutionState] = {}
        self._plans: dict[str, ResearchPlan] = {}
        self._contexts: dict[str, ResearchPlanExecutionContext] = {}
        self._execution_store = execution_store
        self._clock = clock or (lambda: datetime.now(UTC))
        self._restored: dict[str, ResearchPlanExecutionSnapshot] = {}
        self._restore()

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

        try:
            context = ResearchPlanExecutionContext(
                research_run_id=self._optional_run_id(request)
            )
        except ResearchError as error:
            return self._response_composer.research_plan_execution_rejected(
                request,
                str(error),
            )

        state = ResearchPlanExecutionState.prepare(plan).start()
        self._executions[plan.plan_id] = state
        self._plans[plan.plan_id] = plan
        self._contexts[plan.plan_id] = context
        self._events.started(state, context.has_research_run)
        self._persist(plan.plan_id)
        return self._response_composer.research_plan_execution_status(request, state)

    def process_status(self, request: BrainRequest) -> BrainResponse:
        """Report live state, restored durable state, or neither."""
        plan_id = self._normalized_plan_id(request)
        state = self._executions.get(plan_id)
        if state is None:
            restored = self._restored.get(plan_id)
            if restored is not None:
                return self._response_composer.research_plan_execution_restored(
                    request,
                    restored,
                )
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
        self._events.cancelled(cancelled)
        self._persist(plan_id)
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
        step = next(
            candidate for candidate in plan.steps if candidate.step_id == step_id
        )
        if not step.capability.executable:
            return self._blocked(
                request,
                plan_id,
                state,
                step_id,
                ("Step declares no executable capability; " "nothing was performed."),
                ExecutionBlockReason.NO_DECLARED_CAPABILITY,
            )
        operation = self._operation_registry.resolve(step.capability)
        if operation is None:
            return self._blocked(
                request,
                plan_id,
                state,
                step_id,
                (
                    f"Capability '{step.capability.value}' has no registered "
                    "operation; nothing was performed."
                ),
                ExecutionBlockReason.UNREGISTERED_CAPABILITY,
            )

        try:
            running = state.start_step(step_id)
        except ResearchError as error:
            return self._response_composer.research_plan_execution_rejected(
                request,
                str(error),
            )
        self._events.step_started(
            plan_id,
            step_id,
            step.capability.value,
            operation.operation_name,
        )
        try:
            stored = self._contexts.get(plan_id, ResearchPlanExecutionContext())
            result = operation.run(
                step,
                ResearchPlanExecutionContext(
                    research_run_id=stored.research_run_id,
                    cancellation_token=request.cancellation_token,
                ),
            )
        except ResearchError as error:
            failed = running.fail_step(step_id, str(error))
            self._executions[plan_id] = failed
            self._events.step_failed(
                plan_id,
                step_id,
                operation.operation_name,
                type(error).__name__,
                work_performed=False,
            )
            self._persist(plan_id)
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
                ExecutionBlockReason.OPERATION_PERFORMED_NOTHING,
            )
        if not result.succeeded:
            failed = running.fail_step(
                step_id,
                result.detail,
                work_performed=True,
                operation=operation.operation_name,
            )
            self._executions[plan_id] = failed
            self._events.step_failed(
                plan_id,
                step_id,
                operation.operation_name,
                "operation_did_not_succeed",
                work_performed=True,
            )
            self._persist(plan_id)
            return self._response_composer.research_plan_execution_status(
                request,
                failed,
            )
        completed = running.complete_step(
            step_id,
            result.detail,
            work_performed=True,
            operation=operation.operation_name,
        )
        self._executions[plan_id] = completed
        self._events.step_completed(plan_id, step_id, operation.operation_name)
        self._persist(plan_id)
        return self._response_composer.research_plan_execution_status(
            request,
            completed,
        )

    def _restore(self) -> None:
        """Load durable executions, marking mid-flight work interrupted.

        A corrupt or unreadable store raises here rather than being replaced by
        an empty one, because silently discarding it would erase execution
        history on the next write.
        """
        if self._execution_store is None:
            return
        for snapshot in self._execution_store.load():
            restored = snapshot.restored()
            self._restored[restored.plan_id] = restored
            self._events.restored(
                restored.plan_id,
                restored.status.value,
                sum(
                    1
                    for step in restored.steps
                    if step.status is ResearchPlanStepStatus.INTERRUPTED
                ),
            )

    def _persist(self, plan_id: str) -> None:
        """Write durable state, never erasing it silently on failure."""
        if self._execution_store is None:
            return
        try:
            self._execution_store.save(self._snapshots())
        except ResearchError as error:
            self._events.persistence_failed(plan_id, type(error).__name__)

    def _snapshots(self) -> list[ResearchPlanExecutionSnapshot]:
        """Capture live executions, keeping restored history alongside them."""
        recorded_at = self._clock()
        snapshots = [
            ResearchPlanExecutionSnapshot.capture(
                state,
                self._plans[plan_id].question,
                self._plans[plan_id].steps,
                recorded_at,
                self._contexts.get(
                    plan_id,
                    ResearchPlanExecutionContext(),
                ).research_run_id,
            )
            for plan_id, state in self._executions.items()
        ]
        snapshots.extend(
            snapshot
            for plan_id, snapshot in self._restored.items()
            if plan_id not in self._executions
        )
        return snapshots

    def _blocked(
        self,
        request: BrainRequest,
        plan_id: str,
        state: ResearchPlanExecutionState,
        step_id: str,
        detail: str,
        reason: ExecutionBlockReason,
    ) -> BrainResponse:
        """Block a step instead of implying work that never happened."""
        blocked = state.block_step(step_id, detail)
        self._executions[plan_id] = blocked
        self._events.step_blocked(plan_id, step_id, reason)
        self._persist(plan_id)
        return self._response_composer.research_plan_execution_status(
            request,
            blocked,
        )

    @staticmethod
    def _optional_run_id(request: BrainRequest) -> str | None:
        """Read the optional explicit research run binding for this execution."""
        value = request.metadata.get("research_run_id")
        if value is None:
            return None
        if not isinstance(value, str):
            raise ResearchError("Research execution run ID must be text.")
        return value

    @staticmethod
    def _normalized_plan_id(request: BrainRequest) -> str:
        value = request.metadata.get("research_plan_id")
        if not isinstance(value, str) or not value.strip():
            raise ResearchError("Research plan execution ID cannot be empty.")
        return value.strip()
