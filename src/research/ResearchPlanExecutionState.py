"""Immutable deterministic state machine for one research-plan execution.

Stage 1 of research-plan execution: pure in-memory state transitions with no
network, LLM, provider, persistence, or run-lifecycle integration. Every
transition returns a new immutable state and rejects an invalid transition with
one bounded reason instead of silently repairing it.

A plan reaches COMPLETED only when every step reached COMPLETED, so a partial or
failed execution can never present itself as finished.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from core.Exceptions import ResearchError
from research.ResearchPlan import ResearchPlan
from research.ResearchPlanExecutionStatus import ResearchPlanExecutionStatus
from research.ResearchPlanStepState import ResearchPlanStepState
from research.ResearchPlanStepStatus import ResearchPlanStepStatus

MAX_RESEARCH_PLAN_EXECUTION_DETAIL_CHARACTERS = 500


@dataclass(frozen=True, slots=True)
class ResearchPlanExecutionState:
    """Track bounded plan and step execution status without side effects."""

    plan_id: str
    status: ResearchPlanExecutionStatus
    steps: tuple[ResearchPlanStepState, ...]
    detail: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.plan_id, str) or not self.plan_id.strip():
            raise ResearchError("Research plan execution ID cannot be empty.")
        if not isinstance(self.status, ResearchPlanExecutionStatus):
            raise ResearchError("Research plan execution status is invalid.")
        if not isinstance(self.steps, tuple) or not self.steps:
            raise ResearchError("Research plan execution requires step states.")
        if not all(isinstance(step, ResearchPlanStepState) for step in self.steps):
            raise ResearchError("Research plan execution contains an invalid step.")
        step_ids = tuple(step.step_id for step in self.steps)
        if len(step_ids) != len(set(step_ids)):
            raise ResearchError("Research plan execution has duplicate step IDs.")
        if not isinstance(self.detail, str):
            raise ResearchError("Research plan execution detail must be text.")
        detail = self.detail.strip()
        if len(detail) > MAX_RESEARCH_PLAN_EXECUTION_DETAIL_CHARACTERS:
            raise ResearchError("Research plan execution detail is too long.")
        if self.status is ResearchPlanExecutionStatus.COMPLETED and not all(
            step.status is ResearchPlanStepStatus.COMPLETED for step in self.steps
        ):
            raise ResearchError(
                "Research plan execution cannot be completed with unfinished steps."
            )
        if (
            sum(
                1
                for step in self.steps
                if step.status is ResearchPlanStepStatus.RUNNING
            )
            > 1
        ):
            raise ResearchError("Research plan execution allows only one running step.")
        object.__setattr__(self, "plan_id", self.plan_id.strip())
        object.__setattr__(self, "detail", detail)

    @classmethod
    def prepare(cls, plan: ResearchPlan) -> ResearchPlanExecutionState:
        """Return the inert ready state for an authored plan without starting it."""
        if not isinstance(plan, ResearchPlan):
            raise ResearchError("Research plan execution requires a research plan.")
        return cls(
            plan_id=plan.plan_id,
            status=ResearchPlanExecutionStatus.READY,
            steps=tuple(
                ResearchPlanStepState(step_id=step.step_id) for step in plan.steps
            ),
        )

    @property
    def completed_steps(self) -> int:
        return self._count(ResearchPlanStepStatus.COMPLETED)

    @property
    def pending_steps(self) -> int:
        return self._count(ResearchPlanStepStatus.PENDING)

    @property
    def running_step_id(self) -> str | None:
        for step in self.steps:
            if step.status is ResearchPlanStepStatus.RUNNING:
                return step.step_id
        return None

    @property
    def next_pending_step_id(self) -> str | None:
        """Return the first authored step still awaiting execution."""
        for step in self.steps:
            if step.status is ResearchPlanStepStatus.PENDING:
                return step.step_id
        return None

    def start(self) -> ResearchPlanExecutionState:
        """Move an explicitly prepared plan into running without starting a step."""
        if self.status is not ResearchPlanExecutionStatus.READY:
            raise ResearchError(
                "Research plan execution can start only from the ready status."
            )
        return replace(self, status=ResearchPlanExecutionStatus.RUNNING, detail="")

    def start_step(self, step_id: str) -> ResearchPlanExecutionState:
        """Begin one pending step in authored order while the plan is running."""
        self._require_running()
        if self.running_step_id is not None:
            raise ResearchError("Research plan execution already has a running step.")
        if self.next_pending_step_id != self._normalized(step_id):
            raise ResearchError(
                "Research plan execution must start the next pending step."
            )
        return self._replace_step(step_id, ResearchPlanStepStatus.RUNNING)

    def complete_step(
        self,
        step_id: str,
        detail: str = "",
    ) -> ResearchPlanExecutionState:
        """Record one finished step and complete the plan only when all finished."""
        self._require_running()
        self._require_step_status(step_id, ResearchPlanStepStatus.RUNNING)
        updated = self._replace_step(
            step_id,
            ResearchPlanStepStatus.COMPLETED,
            detail,
        )
        if all(
            step.status is ResearchPlanStepStatus.COMPLETED for step in updated.steps
        ):
            return replace(updated, status=ResearchPlanExecutionStatus.COMPLETED)
        return updated

    def fail_step(
        self,
        step_id: str,
        detail: str,
    ) -> ResearchPlanExecutionState:
        """Record one failed step and fail the plan without hiding progress."""
        self._require_running()
        self._require_step_status(step_id, ResearchPlanStepStatus.RUNNING)
        updated = self._replace_step(
            step_id,
            ResearchPlanStepStatus.FAILED,
            detail,
        )
        return replace(
            updated,
            status=ResearchPlanExecutionStatus.FAILED,
            detail=detail,
        )

    def block_step(
        self,
        step_id: str,
        detail: str,
    ) -> ResearchPlanExecutionState:
        """Record one step that cannot proceed and block the plan for review."""
        self._require_running()
        current = self._step(step_id)
        if current.status not in (
            ResearchPlanStepStatus.PENDING,
            ResearchPlanStepStatus.RUNNING,
        ):
            raise ResearchError(
                "Research plan execution can block only an unfinished step."
            )
        updated = self._replace_step(
            step_id,
            ResearchPlanStepStatus.BLOCKED,
            detail,
        )
        return replace(
            updated,
            status=ResearchPlanExecutionStatus.BLOCKED,
            detail=detail,
        )

    def cancel(self, detail: str = "") -> ResearchPlanExecutionState:
        """Cancel every unfinished step without rewriting finished history."""
        if self.status.terminal:
            raise ResearchError(
                "Research plan execution is already in a terminal status."
            )
        steps = tuple(
            (
                step
                if step.status.terminal
                else step.with_status(ResearchPlanStepStatus.CANCELLED, detail)
            )
            for step in self.steps
        )
        return replace(
            self,
            status=ResearchPlanExecutionStatus.CANCELLED,
            steps=steps,
            detail=detail,
        )

    def _count(self, status: ResearchPlanStepStatus) -> int:
        return sum(1 for step in self.steps if step.status is status)

    def _require_running(self) -> None:
        if self.status is not ResearchPlanExecutionStatus.RUNNING:
            raise ResearchError("Research plan execution is not currently running.")

    def _require_step_status(
        self,
        step_id: str,
        status: ResearchPlanStepStatus,
    ) -> None:
        if self._step(step_id).status is not status:
            raise ResearchError(f"Research plan step is not currently {status.value}.")

    def _step(self, step_id: str) -> ResearchPlanStepState:
        normalized = self._normalized(step_id)
        for step in self.steps:
            if step.step_id == normalized:
                return step
        raise ResearchError("Research plan execution has no such step.")

    def _replace_step(
        self,
        step_id: str,
        status: ResearchPlanStepStatus,
        detail: str = "",
    ) -> ResearchPlanExecutionState:
        normalized = self._normalized(step_id)
        steps = tuple(
            step.with_status(status, detail) if step.step_id == normalized else step
            for step in self.steps
        )
        return replace(self, steps=steps)

    @staticmethod
    def _normalized(step_id: str) -> str:
        if not isinstance(step_id, str) or not step_id.strip():
            raise ResearchError("Research plan execution step ID cannot be empty.")
        return step_id.strip()
