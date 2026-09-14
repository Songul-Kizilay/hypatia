"""Human-readable preview for one exact one-shot schedule."""

from dataclasses import dataclass
from datetime import datetime

from research.DeferredExecutionGrant import DeferredExecutionGrant
from research.OneShotDeferredExecutionSchedule import OneShotDeferredExecutionSchedule


@dataclass(frozen=True, slots=True)
class OneShotDeferredExecutionScheduleView:
    task_id: str
    grant_id: str
    run_at: datetime
    schedule: OneShotDeferredExecutionSchedule | None = None
    #: The exact grant this schedule will run under. Carried so the screen can
    #: say what that grant already permits: the id alone names the authority
    #: without describing it, and this is the control that arms an unattended
    #: run. Always the grant selected by that id, never whichever grant happens
    #: to be active for the task.
    grant: DeferredExecutionGrant | None = None

    @property
    def approved_restrictions_text(self) -> str:
        """Describe the exact grant being armed, never a re-derived plan.

        This screen acts on a grant that already exists, so the grant's own
        recorded snapshot is the audit source. Rebuilding it from the current
        plan could describe something the grant never recorded.
        """
        if self.grant is None:
            return "unavailable"
        return self.grant.approved_restrictions_text

    def confirmation_text(self) -> str:
        return (
            f"Task: {self.task_id}\n"
            f"Deferred grant: {self.grant_id}\n"
            f"Run once at: {self.run_at.isoformat()}\n"
            f"Approved restrictions: {self.approved_restrictions_text}\n\n"
            "This schedules one attempt of this exact task under its exact current "
            "trusted deferred grant. It adds no authority or budget, never chooses "
            "another task, and never repeats."
        )
