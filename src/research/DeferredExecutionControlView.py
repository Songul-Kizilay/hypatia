"""Small operator-facing view of deferred permission state."""

from dataclasses import dataclass

from research.DeferredExecutionEligibility import DeferredExecutionDecision
from research.DeferredExecutionGrant import DeferredExecutionGrant
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchPlanRestriction import ResearchPlanRestriction


@dataclass(frozen=True, slots=True)
class DeferredExecutionControlView:
    task_id: str
    execution_id: str
    plan_digest: str
    task_budget: ResearchAutonomyBudget
    grant: DeferredExecutionGrant | None
    decision: DeferredExecutionDecision
    #: What the exact pending plan would bind into a grant, derived from that
    #: plan alone. Present whether or not a grant exists, because the question
    #: a person answers before pressing Allow is not "what does the grant say"
    #: but "what am I about to authorize".
    pending_restrictions: frozenset[ResearchPlanRestriction] = frozenset()

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

    @property
    def restrictions_to_be_granted_text(self) -> str:
        """Say what a grant made now would carry, before one exists.

        Deliberately not the grant's own answer. "no grant" is true but useless
        here: it reports the absence of a record while the reader is asking
        what that record would carry, and so reads as though there were nothing
        to carry.
        """
        return (
            ", ".join(sorted(value.value for value in self.pending_restrictions))
            or "none"
        )

    @property
    def restriction_line(self) -> str:
        """Answer the restriction question for whichever state this is in.

        Three different facts, never collapsed: what a grant would carry, what
        an existing grant does carry, and that an old grant never recorded it.
        """
        if self.grant is None:
            return f"Restrictions to be granted: {self.restrictions_to_be_granted_text}"
        return f"Approved restrictions: {self.approved_restrictions_text}"

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
            f"{self.restriction_line}\n\n"
            "This allows this exact queued task to use its existing authorized "
            "research execution later without another confirmation at fire time. "
            "It adds no budget or capabilities. No timer exists yet."
        )
