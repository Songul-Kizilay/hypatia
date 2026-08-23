"""Bounded observability for research-plan execution.

Emits visibility only. No event changes behavior, and a missing event bus makes
every call a no-op, so execution works identically with observability absent.

Payloads carry safe identifiers, capability and operation names, counts, and
booleans. They never carry authored instructions, questions, notes, claim or
assessment text, URLs, source content, excerpts, provider payloads, or exception
messages. A failure reports its exception class name; a block reports a bounded
category rather than free text.
"""

from __future__ import annotations

from enum import StrEnum

from eventbus.EventBus import EventBus
from research.ResearchPlanExecutionState import ResearchPlanExecutionState

EXECUTION_STARTED = "research.plan.execution.started"
EXECUTION_STEP_STARTED = "research.plan.execution.step_started"
EXECUTION_STEP_COMPLETED = "research.plan.execution.step_completed"
EXECUTION_STEP_FAILED = "research.plan.execution.step_failed"
EXECUTION_STEP_BLOCKED = "research.plan.execution.step_blocked"
EXECUTION_CANCELLED = "research.plan.execution.cancelled"
EXECUTION_RESTORED = "research.plan.execution.restored"
EXECUTION_PERSISTENCE_FAILED = "research.plan.execution.persistence_failed"

EVENT_SOURCE = "research.execution"


class ExecutionBlockReason(StrEnum):
    """Bounded categories explaining why a step was blocked."""

    NO_DECLARED_CAPABILITY = "no_declared_capability"
    UNREGISTERED_CAPABILITY = "unregistered_capability"
    OPERATION_PERFORMED_NOTHING = "operation_performed_nothing"


class ResearchPlanExecutionEvents:
    """Publish bounded execution events, or nothing when no bus is present."""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._event_bus = event_bus

    def started(self, state: ResearchPlanExecutionState, bound_run: bool) -> None:
        """Report that an execution began, without any authored content."""
        self._emit(
            EXECUTION_STARTED,
            {
                "plan_id": state.plan_id,
                "steps": len(state.steps),
                "bound_research_run": bound_run,
            },
        )

    def step_started(
        self,
        plan_id: str,
        step_id: str,
        capability: str,
        operation: str,
    ) -> None:
        """Report which operation a step is about to run."""
        self._emit(
            EXECUTION_STEP_STARTED,
            {
                "plan_id": plan_id,
                "step_id": step_id,
                "capability": capability,
                "operation": operation,
            },
        )

    def step_completed(self, plan_id: str, step_id: str, operation: str) -> None:
        """Report a step whose operation genuinely performed work."""
        self._emit(
            EXECUTION_STEP_COMPLETED,
            {
                "plan_id": plan_id,
                "step_id": step_id,
                "operation": operation,
                "work_performed": True,
            },
        )

    def step_failed(
        self,
        plan_id: str,
        step_id: str,
        operation: str,
        cause: str,
        work_performed: bool,
    ) -> None:
        """Report a failed step by cause category, never by message."""
        self._emit(
            EXECUTION_STEP_FAILED,
            {
                "plan_id": plan_id,
                "step_id": step_id,
                "operation": operation,
                "cause": cause,
                "work_performed": work_performed,
            },
        )

    def step_blocked(
        self,
        plan_id: str,
        step_id: str,
        reason: ExecutionBlockReason,
    ) -> None:
        """Report a blocked step using a bounded category."""
        self._emit(
            EXECUTION_STEP_BLOCKED,
            {
                "plan_id": plan_id,
                "step_id": step_id,
                "reason": reason.value,
            },
        )

    def cancelled(self, state: ResearchPlanExecutionState) -> None:
        """Report a cancelled execution and how much survived it."""
        self._emit(
            EXECUTION_CANCELLED,
            {
                "plan_id": state.plan_id,
                "completed_steps": state.completed_steps,
                "steps_with_research_work": state.steps_with_research_work,
            },
        )

    def restored(self, plan_id: str, status: str, interrupted_steps: int) -> None:
        """Report one execution restored from durable state, never resumed."""
        self._emit(
            EXECUTION_RESTORED,
            {
                "plan_id": plan_id,
                "status": status,
                "interrupted_steps": interrupted_steps,
            },
        )

    def persistence_failed(self, plan_id: str, cause: str) -> None:
        """Report that durable state could not be written, by cause class."""
        self._emit(
            EXECUTION_PERSISTENCE_FAILED,
            {"plan_id": plan_id, "cause": cause},
        )

    def _emit(self, name: str, payload: dict[str, object]) -> None:
        if self._event_bus is None:
            return
        self._event_bus.emit(name, payload, source=EVENT_SOURCE)
