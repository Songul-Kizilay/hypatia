"""Human-readable preview for one exact one-shot schedule."""

from dataclasses import dataclass
from datetime import datetime

from research.OneShotDeferredExecutionSchedule import OneShotDeferredExecutionSchedule


@dataclass(frozen=True, slots=True)
class OneShotDeferredExecutionScheduleView:
    task_id: str
    grant_id: str
    run_at: datetime
    schedule: OneShotDeferredExecutionSchedule | None = None

    def confirmation_text(self) -> str:
        return (
            f"Task: {self.task_id}\n"
            f"Deferred grant: {self.grant_id}\n"
            f"Run once at: {self.run_at.isoformat()}\n\n"
            "This schedules one attempt of this exact task under its exact current "
            "trusted deferred grant. It adds no authority or budget, never chooses "
            "another task, and never repeats."
        )
