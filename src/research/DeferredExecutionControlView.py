"""Small operator-facing view of deferred permission state."""

from dataclasses import dataclass

from research.DeferredExecutionEligibility import DeferredExecutionDecision
from research.DeferredExecutionGrant import DeferredExecutionGrant
from research.ResearchAutonomyBudget import ResearchAutonomyBudget


@dataclass(frozen=True, slots=True)
class DeferredExecutionControlView:
    task_id: str
    execution_id: str
    plan_digest: str
    task_budget: ResearchAutonomyBudget
    grant: DeferredExecutionGrant | None
    decision: DeferredExecutionDecision

    @property
    def short_digest(self) -> str:
        return self.plan_digest[:16]

    def confirmation_text(self) -> str:
        budget = self.task_budget
        return (
            f"Task: {self.task_id}\n"
            f"Execution: {self.execution_id}\n"
            f"Plan digest: {self.short_digest}\n"
            "Outer task bound: "
            f"{budget.max_step_advances} steps, "
            f"{budget.max_network_operations} network, "
            f"{budget.max_llm_operations} model, "
            f"{budget.max_seconds:g}s\n\n"
            "This allows this exact queued task to use its existing authorized "
            "research execution later without another confirmation at fire time. "
            "It adds no budget or capabilities. No timer exists yet."
        )
