"""What one bounded foreground continuation actually did.

A structured answer rather than a paragraph, because the interesting questions
are countable: how many steps were asked for, how many happened, which ones, and
why it stopped. A caller that had to read that out of prose would be guessing,
and the desktop showing "3 requested, 1 attempted" is the whole point.

`attempted_step_ids` names the steps that left PENDING during this run — the
ones that reached a canonical outcome of their own. A step refused before its
attempt, because the budget would not cover it, is not among them; it is still
pending, and the stop reason says why nobody touched it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.Exceptions import ResearchError
from research.ResearchContinuationStopReason import ResearchContinuationStopReason
from research.ResearchExecutionAllowance import ResearchExecutionAllowance
from research.ResearchPlanExecutionStatus import ResearchPlanExecutionStatus

#: The most foreground steps one press may run. Deliberately well below the
#: twenty a plan may hold: this is how much an operator can set going without
#: looking again, not how large a plan is allowed to be.
MAX_FOREGROUND_CONTINUATION_STEPS = 10


@dataclass(frozen=True, slots=True)
class ResearchExecutionContinuation:
    """One bounded run of the ordinary one-step advance, described exactly."""

    execution_id: str
    requested_max_steps: int
    final_status: ResearchPlanExecutionStatus
    stop_reason: ResearchContinuationStopReason
    attempted_step_ids: tuple[str, ...] = ()
    next_step_id: str = ""
    allowance: ResearchExecutionAllowance | None = field(default=None)

    def __post_init__(self) -> None:
        if not isinstance(self.execution_id, str) or not self.execution_id.strip():
            raise ResearchError("A continuation names one exact execution.")
        if (
            not isinstance(self.requested_max_steps, int)
            or isinstance(self.requested_max_steps, bool)
            or self.requested_max_steps < 1
            or self.requested_max_steps > MAX_FOREGROUND_CONTINUATION_STEPS
        ):
            raise ResearchError("A continuation bound is out of range.")
        if not isinstance(self.final_status, ResearchPlanExecutionStatus):
            raise ResearchError("A continuation final status is invalid.")
        if not isinstance(self.stop_reason, ResearchContinuationStopReason):
            raise ResearchError("A continuation stop reason is invalid.")
        if not isinstance(self.attempted_step_ids, tuple) or not all(
            isinstance(step_id, str) and step_id.strip()
            for step_id in self.attempted_step_ids
        ):
            raise ResearchError("A continuation step list is invalid.")
        if len(self.attempted_step_ids) > self.requested_max_steps:
            raise ResearchError("A continuation cannot exceed its own bound.")
        if not isinstance(self.next_step_id, str):
            raise ResearchError("A continuation next step must be text.")
        if self.allowance is not None and not isinstance(
            self.allowance, ResearchExecutionAllowance
        ):
            raise ResearchError("A continuation allowance is invalid.")
        object.__setattr__(self, "execution_id", self.execution_id.strip())
        object.__setattr__(self, "next_step_id", self.next_step_id.strip())

    @property
    def attempted_steps(self) -> int:
        """Return how many steps reached an outcome of their own."""
        return len(self.attempted_step_ids)
