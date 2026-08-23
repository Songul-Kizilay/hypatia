"""Bounded autonomous continuation of one already-approved execution.

Autonomy is a loop over the existing execution service, not a second execution
engine. Every step it runs is a step a human already authored and authorized,
advanced through the same `process_advance` path with the same registry, the
same operations, and the same run manager.

It therefore cannot invent a capability, infer one from instruction text,
rewrite a plan, fabricate an authorization, accept a source, promote trust,
promote a claim, or resolve a contradiction. It only decides *whether to take
the next already-declared step*, and stops.

Budgets are enforced before each advance, never after the fact, and network and
model costs come from the declared capability cost table rather than from
operation names. Time comes from an injected clock so runs are deterministic in
tests and never sleep.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from cognition.ResearchAutonomyEvents import ResearchAutonomyEvents
from cognition.ResearchPlanExecutionApplicationService import (
    RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT,
    ResearchPlanExecutionApplicationService,
)
from core.Exceptions import ResearchError
from eventbus.EventBus import EventBus
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchAutonomyResult import (
    AutonomyStopReason,
    ResearchAutonomyResult,
)
from research.ResearchCapabilityCost import cost_for
from research.ResearchPlanExecutionState import ResearchPlanExecutionState
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchPlanStepStatus import ResearchPlanStepStatus
from response.ResponseComposer import ResponseComposer

RESEARCH_AUTONOMY_RUN_INTENT = "research_autonomy_run"


class ResearchAutonomyApplicationService:
    """Advance an approved execution under hard budgets, then stop honestly."""

    def __init__(
        self,
        execution_service: ResearchPlanExecutionApplicationService,
        response_composer: ResponseComposer,
        *,
        event_bus: EventBus | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._execution_service = execution_service
        self._response_composer = response_composer
        self._events = ResearchAutonomyEvents(event_bus)
        self._clock = clock or _monotonic

    @staticmethod
    def is_run_request(request: BrainRequest) -> bool:
        """Recognize only the explicit structured autonomy intent."""
        return request.metadata.get("intent") == RESEARCH_AUTONOMY_RUN_INTENT

    def process_run(self, request: BrainRequest) -> BrainResponse:
        """Run the bounded loop over one approved execution."""
        plan_id = self._plan_id(request)
        budget = self._budget(request)
        state = self._execution_service.live_execution(plan_id)
        if state is None:
            return self._response_composer.research_autonomy_missing(request, plan_id)

        started_at = self._clock()
        self._events.started(plan_id, budget)
        steps_attempted = 0
        operations_performed = 0
        network_operations = 0
        llm_operations = 0

        while True:
            elapsed = self._clock() - started_at
            stop = self._stop_reason(
                request,
                state,
                budget,
                steps_attempted,
                network_operations,
                llm_operations,
                elapsed,
            )
            if stop is not None:
                return self._finish(
                    request,
                    plan_id,
                    stop,
                    state,
                    steps_attempted,
                    operations_performed,
                    network_operations,
                    llm_operations,
                    elapsed,
                )

            step_id = state.next_pending_step_id
            assert step_id is not None
            cost = cost_for(self._capability(plan_id, step_id))
            steps_attempted += 1
            network_operations += cost.network_operations
            llm_operations += cost.llm_operations

            self._execution_service.process_advance(
                BrainRequest(
                    message="Advance research plan",
                    request_id=request.request_id,
                    source=request.source,
                    metadata={
                        "intent": RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT,
                        "research_plan_id": plan_id,
                    },
                    cancellation_token=request.cancellation_token,
                )
            )
            advanced = self._execution_service.live_execution(plan_id)
            assert advanced is not None
            state = advanced
            if self._step_status(state, step_id) is ResearchPlanStepStatus.COMPLETED:
                operations_performed += 1

    def _stop_reason(
        self,
        request: BrainRequest,
        state: ResearchPlanExecutionState,
        budget: ResearchAutonomyBudget,
        steps_attempted: int,
        network_operations: int,
        llm_operations: int,
        elapsed: float,
    ) -> AutonomyStopReason | None:
        """Decide whether the loop may take one more step."""
        token = request.cancellation_token
        if token is not None and token.is_cancelled():
            return AutonomyStopReason.CANCELLED
        # Step-level reasons come first: they explain why an execution became
        # terminal, which a bare "terminal" answer would hide.
        if any(step.status is ResearchPlanStepStatus.FAILED for step in state.steps):
            return AutonomyStopReason.STEP_FAILED
        if any(step.status is ResearchPlanStepStatus.BLOCKED for step in state.steps):
            return AutonomyStopReason.STEP_BLOCKED
        if any(
            step.status is ResearchPlanStepStatus.INTERRUPTED for step in state.steps
        ):
            return AutonomyStopReason.STEP_INTERRUPTED
        if state.status.terminal:
            return AutonomyStopReason.EXECUTION_TERMINAL

        step_id = state.next_pending_step_id
        if step_id is None:
            return AutonomyStopReason.NO_PENDING_STEP
        if steps_attempted >= budget.max_step_advances:
            return AutonomyStopReason.STEP_BUDGET_EXHAUSTED
        if elapsed >= budget.max_seconds:
            return AutonomyStopReason.TIME_BUDGET_EXHAUSTED

        cost = cost_for(self._capability(state.plan_id, step_id))
        if network_operations + cost.network_operations > budget.max_network_operations:
            return AutonomyStopReason.NETWORK_BUDGET_EXHAUSTED
        if llm_operations + cost.llm_operations > budget.max_llm_operations:
            return AutonomyStopReason.LLM_BUDGET_EXHAUSTED
        return None

    def _capability(
        self,
        plan_id: str,
        step_id: str,
    ) -> ResearchPlanStepCapability:
        """Read the step's declared capability, never inferring one."""
        plan = self._execution_service.live_plan(plan_id)
        if plan is None:
            raise ResearchError("Research autonomy lost its approved plan.")
        for step in plan.steps:
            if step.step_id == step_id:
                return step.capability
        raise ResearchError("Research autonomy found no such approved step.")

    @staticmethod
    def _step_status(
        state: ResearchPlanExecutionState,
        step_id: str,
    ) -> ResearchPlanStepStatus | None:
        for step in state.steps:
            if step.step_id == step_id:
                return step.status
        return None

    def _finish(
        self,
        request: BrainRequest,
        plan_id: str,
        stop_reason: AutonomyStopReason,
        state: ResearchPlanExecutionState,
        steps_attempted: int,
        operations_performed: int,
        network_operations: int,
        llm_operations: int,
        elapsed: float,
    ) -> BrainResponse:
        result = ResearchAutonomyResult(
            plan_id=plan_id,
            stop_reason=stop_reason,
            execution_status=state.status.value,
            steps_attempted=steps_attempted,
            operations_performed=operations_performed,
            network_operations=network_operations,
            llm_operations=llm_operations,
            elapsed_seconds=max(elapsed, 0.0),
        )
        self._events.stopped(result)
        return self._response_composer.research_autonomy_result(request, result)

    @staticmethod
    def _plan_id(request: BrainRequest) -> str:
        value = request.metadata.get("research_plan_id")
        if not isinstance(value, str) or not value.strip():
            raise ResearchError("Research autonomy plan ID cannot be empty.")
        return value.strip()

    @staticmethod
    def _budget(request: BrainRequest) -> ResearchAutonomyBudget:
        value = request.metadata.get("research_autonomy_budget")
        if value is None:
            return ResearchAutonomyBudget()
        if not isinstance(value, ResearchAutonomyBudget):
            raise ResearchError("Research autonomy budget is invalid.")
        return cast(ResearchAutonomyBudget, value)


def _monotonic() -> float:
    from time import monotonic

    return monotonic()
