"""What one plan would nominally cost, and whether an approval covers it.

Nominal, and deliberately only that: the cost of attempting each authored step
exactly once, summed from the same `cost_for` the executor charges. It is a
floor, not a forecast. A step that fails still spent what it spent, and a plan
that finishes may well have cost more than this; the number exists so that a
person approving a plan can see whether the budget in front of them could cover
even one clean pass, which is a question nobody could previously ask.

Nothing here approves anything. It computes a requirement and compares it to a
budget somebody else chose — the requirement never becomes the permission, and
no part of this can enlarge a budget to fit a plan.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchCapabilityCost import cost_for
from research.ResearchOperationCost import ResearchOperationCost
from research.ResearchPlan import ResearchPlan


def required_cost(plan: ResearchPlan) -> ResearchOperationCost:
    """Return the cost of attempting every authored step exactly once.

    Summed over the authored steps and nothing else. Preparing a proposal,
    approving it and starting an execution reach no operation and so cost
    nothing here; neither do the human decisions — resolving an interrupted
    attempt, accepting a source — because those are not authored steps and
    never execute. Retries are absent for the same reason: nothing retries.
    """
    if not isinstance(plan, ResearchPlan):
        raise ResearchError("A plan budget requirement needs a validated plan.")
    network = 0
    llm = 0
    for step in plan.steps:
        if not step.capability.executable:
            continue
        cost = cost_for(step.capability)
        network += cost.network_operations
        llm += cost.llm_operations
    return ResearchOperationCost(network_operations=network, llm_operations=llm)


def required_advances(plan: ResearchPlan) -> int:
    """Return how many advances one clean pass of this plan would take."""
    if not isinstance(plan, ResearchPlan):
        raise ResearchError("A plan budget requirement needs a validated plan.")
    return len(plan.steps)


@dataclass(frozen=True, slots=True)
class ResearchPlanBudgetFit:
    """Whether one budget covers one clean pass of one plan, dimension by dimension.

    The shortfalls are kept as numbers rather than folded into a sentence, so a
    caller refusing an approval can say which dimension ran out and by how much
    without anybody parsing prose to find out.

    `max_seconds` is deliberately absent. How long a step takes is not derivable
    from what it declares, and inventing a duration here would turn a guess into
    an approval criterion.
    """

    required: ResearchOperationCost
    required_advances: int
    budget: ResearchAutonomyBudget

    def __post_init__(self) -> None:
        if not isinstance(self.required, ResearchOperationCost):
            raise ResearchError("A plan budget fit needs a validated cost.")
        if not isinstance(self.required_advances, int) or self.required_advances < 0:
            raise ResearchError("A plan budget fit needs a real advance count.")
        if not isinstance(self.budget, ResearchAutonomyBudget):
            raise ResearchError("A plan budget fit needs a validated budget.")

    @classmethod
    def of(
        cls,
        plan: ResearchPlan,
        budget: ResearchAutonomyBudget,
    ) -> ResearchPlanBudgetFit:
        """Return the fit between one exact plan and one exact budget."""
        return cls(
            required=required_cost(plan),
            required_advances=required_advances(plan),
            budget=budget,
        )

    @property
    def network_shortfall(self) -> int:
        return max(
            0,
            self.required.network_operations - self.budget.max_network_operations,
        )

    @property
    def llm_shortfall(self) -> int:
        return max(0, self.required.llm_operations - self.budget.max_llm_operations)

    @property
    def advance_shortfall(self) -> int:
        return max(0, self.required_advances - self.budget.max_step_advances)

    @property
    def sufficient(self) -> bool:
        """Return whether this budget could cover one clean pass of this plan."""
        return not (
            self.network_shortfall or self.llm_shortfall or self.advance_shortfall
        )

    def lines(self) -> tuple[str, ...]:
        """Render the comparison, without implying the requirement was granted."""
        rendered = [
            "Plan budget (one attempt at each authored step, not a guarantee):",
            f"Steps requiring an advance: {self.required_advances} "
            f"| approved advances: {self.budget.max_step_advances}",
            f"Network operations required: {self.required.network_operations} "
            f"| approved: {self.budget.max_network_operations}",
            f"Model operations required: {self.required.llm_operations} "
            f"| approved: {self.budget.max_llm_operations}",
        ]
        if self.sufficient:
            rendered.append(
                "Fit: the budget being approved covers one attempt at every "
                "authored step. It is not a promise the plan will finish."
            )
            return tuple(rendered)
        rendered.append("Fit: INSUFFICIENT. Approving this would not be honest.")
        for label, shortfall in (
            ("advances", self.advance_shortfall),
            ("network operations", self.network_shortfall),
            ("model operations", self.llm_shortfall),
        ):
            if shortfall:
                rendered.append(f"Short by {shortfall} {label}.")
        rendered.append(
            "What a plan needs is not what a person has granted. Nothing here "
            "raises the budget to meet the plan."
        )
        return tuple(rendered)
