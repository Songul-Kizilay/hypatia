"""Persistence and execution ports for one-shot deferred scheduling."""

from typing import Protocol

from core.CancellationSignal import CancellationToken
from research.BackgroundResearchTask import BackgroundResearchTask
from research.OneShotDeferredExecutionSchedule import OneShotDeferredExecutionSchedule


class OneShotDeferredExecutionScheduleStore(Protocol):
    def load(self) -> list[OneShotDeferredExecutionSchedule]: ...

    def save(self, schedules: list[OneShotDeferredExecutionSchedule]) -> None: ...


class RunsExactDeferredTask(Protocol):
    def run_exact_deferred_background_task(
        self,
        task_id: str,
        cancellation_token: CancellationToken | None = None,
    ) -> BackgroundResearchTask | None: ...
