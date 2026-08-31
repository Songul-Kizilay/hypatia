"""Structural boundary for starting one already-derived plan in the foreground.

The research layer names what it needs and the application layer provides it,
as source acceptance and approval recording already do. A caller that derived a
plan itself can begin it without round-tripping the plan through request
metadata, which would mean the plan that runs is the one a message described
rather than the one the caller validated.

Narrow deliberately. It takes a plan, the run it belongs to, and the approval to
spend, and returns the execution state or a refusal. It decides nothing about
whether the caller should be starting anything: the approval is verified and
spent by the existing consumer behind this port, and everything else — whose
question it was, whether the gap is still open — belongs where that context
lives.
"""

from typing import Protocol

from research.ResearchPlan import ResearchPlan
from research.ResearchPlanExecutionState import ResearchPlanExecutionState


class ResearchPlanExecutionStartRefusal:
    """One bounded reason an execution did not begin.

    Carries a reason a person can read rather than an exception, because a
    refusal here is an ordinary answer — the approval was spent elsewhere, the
    plan is already running — and not a fault in the caller.
    """

    __slots__ = ("reason",)

    def __init__(self, reason: str) -> None:
        self.reason = reason


class StartsResearchPlanExecution(Protocol):
    """Begin one canonical plan in the foreground, spending one approval."""

    def start_for_plan(
        self,
        plan: ResearchPlan,
        research_run_id: str,
        authorization_id: str,
    ) -> ResearchPlanExecutionState | ResearchPlanExecutionStartRefusal:
        """Return the started state, or the reason nothing was started."""
