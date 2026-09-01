"""Bounded observability for background research tasks.

Payloads carry task and execution identifiers, bounded status and outcome
categories, retry counters, and an exception class name. They never carry a
research question, URL, source body, evidence text, claim text, or an exception
message.
"""

from __future__ import annotations

from eventbus.EventBus import EventBus
from research.BackgroundResearchTask import BackgroundResearchTask

TASK_CREATED = "background_task.created"
TASK_STARTED = "background_task.started"
TASK_PAUSED = "background_task.paused"
TASK_RESUMED = "background_task.resumed"
TASK_COMPLETED = "background_task.completed"
TASK_FAILED = "background_task.failed"
TASK_CANCELLED = "background_task.cancelled"
TASK_INTERRUPTED = "background_task.interrupted"
TASK_RETRY_SCHEDULED = "background_task.retry_scheduled"
#: A worker finished, but a newer legitimate transition had already won. The
#: run really happened; its outcome was not written, and no completed, failed
#: or retry event may claim otherwise.
TASK_OUTCOME_SUPERSEDED = "background_task.outcome_superseded"

EVENT_SOURCE = "research.background"


class BackgroundResearchEvents:
    """Publish bounded task events, or nothing when no bus is present."""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._event_bus = event_bus

    def created(self, task: BackgroundResearchTask) -> None:
        self._emit(TASK_CREATED, self._payload(task))

    def started(self, task: BackgroundResearchTask) -> None:
        self._emit(TASK_STARTED, self._payload(task))

    def paused(self, task: BackgroundResearchTask) -> None:
        self._emit(TASK_PAUSED, self._payload(task))

    def resumed(self, task: BackgroundResearchTask) -> None:
        self._emit(TASK_RESUMED, self._payload(task))

    def completed(self, task: BackgroundResearchTask) -> None:
        self._emit(TASK_COMPLETED, self._payload(task))

    def failed(self, task: BackgroundResearchTask) -> None:
        self._emit(TASK_FAILED, self._payload(task))

    def cancelled(self, task: BackgroundResearchTask) -> None:
        self._emit(TASK_CANCELLED, self._payload(task))

    def interrupted(self, task: BackgroundResearchTask) -> None:
        self._emit(TASK_INTERRUPTED, self._payload(task))

    def retry_scheduled(self, task: BackgroundResearchTask) -> None:
        self._emit(TASK_RETRY_SCHEDULED, self._payload(task))

    def outcome_superseded(self, task: BackgroundResearchTask) -> None:
        """Report the task as it actually stands, not as the worker expected."""
        self._emit(TASK_OUTCOME_SUPERSEDED, self._payload(task))

    @staticmethod
    def _payload(task: BackgroundResearchTask) -> dict[str, object]:
        return {
            "task_id": task.task_id,
            "execution_id": task.execution_id,
            "status": task.status.value,
            "outcome": task.outcome,
            "retry_count": task.retry_count,
            "max_retries": task.max_retries,
            "failure_cause": task.failure_cause,
        }

    def _emit(self, name: str, payload: dict[str, object]) -> None:
        if self._event_bus is None:
            return
        self._event_bus.emit(name, payload, source=EVENT_SOURCE)
