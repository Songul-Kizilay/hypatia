"""The approved budget for one execution, and what is left of it.

One place where budget arithmetic happens. Every question an advance needs to
ask — may this step run, what does it cost, what remains afterwards — is
answered here, so a caller cannot accidentally use a different rule than the
one that will be reported to the operator.

The budget is a copy of what a human approved and is never modified. Only the
spend moves, and only upward.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from core.Exceptions import ResearchError
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchExecutionSpend import ResearchExecutionSpend
from research.ResearchOperationCost import ResearchOperationCost


@dataclass(frozen=True, slots=True)
class ResearchExecutionAllowance:
    """Hold one approved budget beside what has been spent against it."""

    budget: ResearchAutonomyBudget
    spend: ResearchExecutionSpend = ResearchExecutionSpend()

    def __post_init__(self) -> None:
        if not isinstance(self.budget, ResearchAutonomyBudget):
            raise ResearchError("Research execution allowance budget is invalid.")
        if not isinstance(self.spend, ResearchExecutionSpend):
            raise ResearchError("Research execution allowance spend is invalid.")
        if (
            self.spend.step_advances > self.budget.max_step_advances
            or self.spend.network_operations > self.budget.max_network_operations
            or self.spend.llm_operations > self.budget.max_llm_operations
        ):
            raise ResearchError("Research execution has spent beyond its budget.")

    @property
    def remaining_step_advances(self) -> int:
        """Return how many more advances were approved."""
        return self.budget.max_step_advances - self.spend.step_advances

    @property
    def remaining_network_operations(self) -> int:
        """Return how many more network operations were approved."""
        return self.budget.max_network_operations - self.spend.network_operations

    @property
    def remaining_llm_operations(self) -> int:
        """Return how many more model operations were approved."""
        return self.budget.max_llm_operations - self.spend.llm_operations

    @property
    def remaining_seconds(self) -> float:
        """Return how much approved active time is left, never below zero."""
        return max(self.budget.max_seconds - self.spend.active_seconds, 0.0)

    @property
    def exhausted(self) -> bool:
        """Return whether no further advance could be afforded at any cost."""
        return self.remaining_step_advances <= 0 or self.remaining_seconds <= 0

    def affords(self, cost: ResearchOperationCost) -> bool:
        """Return whether one more attempt at this declared cost is approved.

        Checked before the attempt, never reconciled after it. A budget
        consulted afterwards is a budget that has already been exceeded.
        """
        if not isinstance(cost, ResearchOperationCost):
            raise ResearchError("Research execution cost is invalid.")
        return (
            self.remaining_step_advances >= 1
            and self.remaining_seconds > 0
            and self.remaining_network_operations >= cost.network_operations
            and self.remaining_llm_operations >= cost.llm_operations
        )

    def charged(
        self,
        cost: ResearchOperationCost,
        seconds: float = 0.0,
    ) -> ResearchExecutionAllowance:
        """Return this allowance with one attempt at that cost spent."""
        return replace(self, spend=self.spend.charged(cost, seconds))

    def with_elapsed(self, seconds: float) -> ResearchExecutionAllowance:
        """Return this allowance with more active time spent and nothing else."""
        return replace(self, spend=self.spend.with_elapsed(seconds))

    def lines(self) -> tuple[str, ...]:
        """Render approved, spent, and remaining as bounded display lines."""
        budget = self.budget
        spend = self.spend
        return (
            f"Step advances: {spend.step_advances} of "
            f"{budget.max_step_advances} used, "
            f"{self.remaining_step_advances} left",
            f"Network operations: {spend.network_operations} of "
            f"{budget.max_network_operations} used, "
            f"{self.remaining_network_operations} left",
            f"Model calls: {spend.llm_operations} of "
            f"{budget.max_llm_operations} used, "
            f"{self.remaining_llm_operations} left",
            f"Active time: {spend.active_seconds:.3f}s of "
            f"{budget.max_seconds:g}s used, "
            f"{self.remaining_seconds:.3f}s left",
        )
