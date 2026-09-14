"""Read-only boundary onto one canonical research execution.

Deliberately one method. Callers that need to *know* what an execution is —
the scheduler, when deciding whether queueing a task means anything — must not
thereby gain the power to advance it, cancel it, resolve an interrupted step,
authorize anything, or touch a budget. Those all live on the execution service
and stay there.

Widening this port is a decision, not a convenience.
"""

from typing import Protocol

from research.ResearchPlanExecutionState import ResearchPlanExecutionState


class ReadsResearchExecution(Protocol):
    """Look up one exact execution without being able to change it."""

    def live_execution(self, plan_id: str) -> ResearchPlanExecutionState | None:
        """Return the execution this process holds for that exact ID.

        ``None`` means this process holds no such execution, which is the same
        answer autonomy already acts on. It never means "look harder", and it
        never licenses falling back to some other execution.
        """
