"""Bounded scheduling of approved background research tasks.

The scheduler owns queueing, pausing, retrying, and crash recovery. It owns no
research logic: every cycle drives the existing autonomy service, which in turn
drives the existing execution service. There is one research-driving loop in the
system and this is not it.

Because the scheduler only passes a plan identifier and a declared budget to
autonomy, it cannot invent a capability, weaken a budget, accept a source, or
promote a claim. It decides *which approved task runs next and whether it runs
at all*.

Work is synchronous and demand-driven: one explicit cycle runs a bounded number
of tasks and returns. There is no thread, no polling, and no busy loop.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from cognition.BackgroundResearchEvents import BackgroundResearchEvents
from cognition.ResearchAutonomyApplicationService import (
    RESEARCH_AUTONOMY_RUN_INTENT,
    ResearchAutonomyApplicationService,
)
from core.Exceptions import ResearchError
from eventbus.EventBus import EventBus
from research.BackgroundResearchTask import BackgroundResearchTask
from research.BackgroundResearchTaskStatus import BackgroundResearchTaskStatus
from research.BackgroundTaskOutcome import BackgroundTaskOutcome, outcome_for
from research.BackgroundTaskStore import BackgroundTaskStore
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from response.ResponseComposer import ResponseComposer

BACKGROUND_TASK_CREATE_INTENT = "background_research_task_create"
BACKGROUND_TASK_PAUSE_INTENT = "background_research_task_pause"
BACKGROUND_TASK_RESUME_INTENT = "background_research_task_resume"
BACKGROUND_TASK_CANCEL_INTENT = "background_research_task_cancel"
BACKGROUND_TASK_LIST_INTENT = "background_research_task_list"
BACKGROUND_WORKER_CYCLE_INTENT = "background_research_worker_cycle"

DEFAULT_MAX_TASKS_PER_CYCLE = 1
MAX_TASKS_PER_CYCLE_CEILING = 10
DEFAULT_MAX_ACTIVE_TASKS = 20
MAX_ACTIVE_TASKS_CEILING = 100


class BackgroundResearchSchedulerApplicationService:
    """Queue, pause, retry, and run approved background research tasks."""

    def __init__(
        self,
        autonomy_service: ResearchAutonomyApplicationService,
        response_composer: ResponseComposer,
        *,
        task_store: BackgroundTaskStore | None = None,
        event_bus: EventBus | None = None,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
        max_tasks_per_cycle: int = DEFAULT_MAX_TASKS_PER_CYCLE,
        max_active_tasks: int = DEFAULT_MAX_ACTIVE_TASKS,
    ) -> None:
        self._validate_bound(
            max_tasks_per_cycle,
            MAX_TASKS_PER_CYCLE_CEILING,
            "tasks per cycle",
        )
        self._validate_bound(
            max_active_tasks,
            MAX_ACTIVE_TASKS_CEILING,
            "active tasks",
        )
        self._autonomy_service = autonomy_service
        self._response_composer = response_composer
        self._task_store = task_store
        self._events = BackgroundResearchEvents(event_bus)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or (lambda: str(uuid4()))
        self._max_tasks_per_cycle = max_tasks_per_cycle
        self._max_active_tasks = max_active_tasks
        self._tasks: dict[str, BackgroundResearchTask] = {}
        self._restore()

    @staticmethod
    def is_create_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == BACKGROUND_TASK_CREATE_INTENT

    @staticmethod
    def is_pause_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == BACKGROUND_TASK_PAUSE_INTENT

    @staticmethod
    def is_resume_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == BACKGROUND_TASK_RESUME_INTENT

    @staticmethod
    def is_cancel_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == BACKGROUND_TASK_CANCEL_INTENT

    @staticmethod
    def is_list_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == BACKGROUND_TASK_LIST_INTENT

    @staticmethod
    def is_worker_cycle_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == BACKGROUND_WORKER_CYCLE_INTENT

    def tasks(self) -> tuple[BackgroundResearchTask, ...]:
        """Return every known task in stable creation order."""
        return tuple(self._tasks.values())

    def process_create(self, request: BrainRequest) -> BrainResponse:
        """Queue one approved execution, or explain why it cannot be queued."""
        execution_id = self._required_text(request, "research_plan_id", "execution ID")
        budget = self._budget(request)
        max_retries = self._max_retries(request)
        if self._active_count() >= self._max_active_tasks:
            return self._response_composer.background_task_rejected(
                request,
                "Background task capacity is full.",
            )
        now = self._clock()
        task = BackgroundResearchTask(
            task_id=self._id_factory(),
            execution_id=execution_id,
            budget=budget,
            created_at=now,
            updated_at=now,
            max_retries=max_retries,
        )
        self._tasks[task.task_id] = task
        self._events.created(task)
        self._persist()
        return self._response_composer.background_task_status(request, task)

    def process_pause(self, request: BrainRequest) -> BrainResponse:
        return self._transition(request, "paused")

    def process_resume(self, request: BrainRequest) -> BrainResponse:
        return self._transition(request, "resumed")

    def process_cancel(self, request: BrainRequest) -> BrainResponse:
        return self._transition(request, "cancelled")

    def process_list(self, request: BrainRequest) -> BrainResponse:
        """Report every known task without running anything."""
        return self._response_composer.background_task_list(request, self.tasks())

    def process_worker_cycle(self, request: BrainRequest) -> BrainResponse:
        """Run at most the configured number of runnable tasks, then stop."""
        completed: list[BackgroundResearchTask] = []
        for _ in range(self._max_tasks_per_cycle):
            token = request.cancellation_token
            if token is not None and token.is_cancelled():
                break
            task = self._next_runnable()
            if task is None:
                break
            completed.append(self._run(request, task))
        self._persist()
        return self._response_composer.background_worker_cycle(
            request,
            tuple(completed),
            self.tasks(),
        )

    def _run(
        self,
        request: BrainRequest,
        task: BackgroundResearchTask,
    ) -> BackgroundResearchTask:
        """Drive one task through autonomy and record what actually happened."""
        now = self._clock()
        running = task.started(now)
        self._tasks[running.task_id] = running
        self._events.started(running)
        self._persist()

        response = self._autonomy_service.process_run(
            BrainRequest(
                message="Run research autonomy",
                request_id=request.request_id,
                source=request.source,
                metadata={
                    "intent": RESEARCH_AUTONOMY_RUN_INTENT,
                    "research_plan_id": running.execution_id,
                    "research_autonomy_budget": running.budget,
                },
                cancellation_token=request.cancellation_token,
            )
        )
        finished_at = self._clock()
        result = response.research_autonomy
        if result is None:
            updated = running.failed(
                BackgroundTaskOutcome.FAILED.value,
                finished_at,
                failure_cause="ResearchError",
            )
            self._tasks[updated.task_id] = updated
            self._events.failed(updated)
            return updated

        outcome = outcome_for(result.stop_reason)
        if outcome is BackgroundTaskOutcome.COMPLETED:
            updated = running.completed(outcome.value, finished_at)
            self._events.completed(updated)
        elif outcome is BackgroundTaskOutcome.CANCELLED:
            updated = running.cancelled(finished_at)
            self._events.cancelled(updated)
        elif outcome.retryable and running.retries_remaining > 0:
            updated = running.retry_scheduled(outcome.value, finished_at)
            self._events.retry_scheduled(updated)
        else:
            updated = running.failed(outcome.value, finished_at)
            self._events.failed(updated)
        self._tasks[updated.task_id] = updated
        return updated

    def _next_runnable(self) -> BackgroundResearchTask | None:
        """Pick the oldest runnable task, so nothing starves behind a retry."""
        runnable = [task for task in self._tasks.values() if task.status.runnable]
        if not runnable:
            return None
        return min(runnable, key=lambda task: (task.created_at, task.task_id))

    def _transition(self, request: BrainRequest, action: str) -> BrainResponse:
        task_id = self._required_text(request, "background_task_id", "task ID")
        task = self._tasks.get(task_id)
        if task is None:
            return self._response_composer.background_task_missing(request, task_id)
        now = self._clock()
        try:
            updated = cast(
                BackgroundResearchTask,
                getattr(task, action)(now),
            )
        except ResearchError as error:
            return self._response_composer.background_task_rejected(
                request,
                str(error),
            )
        self._tasks[task_id] = updated
        getattr(self._events, action if action != "cancelled" else "cancelled")(updated)
        self._persist()
        return self._response_composer.background_task_status(request, updated)

    def _restore(self) -> None:
        """Load durable tasks, marking mid-flight work interrupted."""
        if self._task_store is None:
            return
        now = self._clock()
        for task in self._task_store.load():
            restored = task
            if task.status is BackgroundResearchTaskStatus.RUNNING:
                restored = task.interrupted(now)
                self._events.interrupted(restored)
            self._tasks[restored.task_id] = restored

    def _persist(self) -> None:
        """Write durable task state, never erasing it silently on failure."""
        if self._task_store is None:
            return
        try:
            self._task_store.save(list(self._tasks.values()))
        except ResearchError:
            return

    def _active_count(self) -> int:
        return sum(1 for task in self._tasks.values() if not task.status.terminal)

    def _budget(self, request: BrainRequest) -> ResearchAutonomyBudget:
        value = request.metadata.get("research_autonomy_budget")
        if value is None:
            return ResearchAutonomyBudget()
        if not isinstance(value, ResearchAutonomyBudget):
            raise ResearchError("Background task budget is invalid.")
        return value

    @staticmethod
    def _max_retries(request: BrainRequest) -> int:
        value = request.metadata.get("background_task_max_retries")
        if value is None:
            return 1
        if isinstance(value, bool) or not isinstance(value, int):
            raise ResearchError("Background task retry limit is invalid.")
        return value

    @staticmethod
    def _required_text(request: BrainRequest, key: str, label: str) -> str:
        value = request.metadata.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ResearchError(f"Background task {label} cannot be empty.")
        return value.strip()

    @staticmethod
    def _validate_bound(value: int, ceiling: int, label: str) -> None:
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"Background scheduler {label} must be positive.")
        if value > ceiling:
            raise ValueError(f"Background scheduler {label} exceeds its ceiling.")
