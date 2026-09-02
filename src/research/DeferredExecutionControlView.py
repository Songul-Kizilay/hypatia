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

    @property
    def approved_restrictions_text(self) -> str:
        """Say what the grant records, distinguishing none from unrecorded.

        "none" is a claim that a grant was made and carried no restriction. A
        grant written before this was recorded cannot support that claim, so it
        says so rather than borrowing the wording of one that can.
        """
        if self.grant is None:
            return "no grant"
        if self.grant.approved_restrictions is None:
            return "unavailable for legacy grant"
        return (
            ", ".join(sorted(value.value for value in self.grant.approved_restrictions))
            or "none"
        )

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
            f"{budget.max_seconds:g}s\n"
            f"Approved restrictions: {self.approved_restrictions_text}\n\n"
            "This allows this exact queued task to use its existing authorized "
            "research execution later without another confirmation at fire time. "
            "It adds no budget or capabilities. No timer exists yet."
        )
