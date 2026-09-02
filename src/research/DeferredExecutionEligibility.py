"""Pure exact-match decision for future unattended scheduler selection."""

from dataclasses import dataclass

from research.BackgroundResearchTask import BackgroundResearchTask
from research.DeferredExecutionGrant import DeferredExecutionGrant
from research.ResearchCapabilityCost import cost_for
from research.ResearchExecutionAllowance import ResearchExecutionAllowance
from research.ResearchExecutionProgressBlock import progress_block
from research.ResearchPlan import ResearchPlan
from research.ResearchPlanAuthorization import capabilities_of, restrictions_of
from research.ResearchPlanDigest import plan_digest
from research.ResearchPlanExecutionState import ResearchPlanExecutionState


@dataclass(frozen=True, slots=True)
class DeferredExecutionDecision:
    allowed: bool
    reason: str


def deferred_execution_decision(
    task: BackgroundResearchTask,
    execution: ResearchPlanExecutionState | None,
    plan: ResearchPlan | None,
    allowance: ResearchExecutionAllowance | None,
    grant: DeferredExecutionGrant | None,
) -> DeferredExecutionDecision:
    """Decide without mutating, spending, refreshing, or executing anything."""

    if grant is None or not grant.active:
        return DeferredExecutionDecision(False, "manual_only")
    if grant.task_id != task.task_id:
        return DeferredExecutionDecision(False, "task_mismatch")
    if grant.execution_id != task.execution_id:
        return DeferredExecutionDecision(False, "execution_mismatch")
    if grant.task_budget != task.budget:
        return DeferredExecutionDecision(False, "task_budget_mismatch")
    if not task.status.runnable:
        return DeferredExecutionDecision(False, "task_not_runnable")
    if execution is None or execution.plan_id != task.execution_id:
        return DeferredExecutionDecision(False, "execution_unavailable")
    blocked = progress_block(execution)
    if blocked is not None:
        return DeferredExecutionDecision(False, blocked.value)
    if plan is None or plan.plan_id != execution.plan_id:
        return DeferredExecutionDecision(False, "plan_unavailable")
    if grant.plan_digest != plan_digest(plan):
        return DeferredExecutionDecision(False, "plan_digest_mismatch")
    if grant.capabilities != capabilities_of(plan):
        return DeferredExecutionDecision(False, "capability_mismatch")
    # A grant written before restrictions were recorded cannot say what it was
    # granted under, and this is the one authority that runs without a person
    # present. Unreadable is treated as not eligible rather than as harmless:
    # the operator can look at it, and grant it again if they still mean it.
    if grant.approved_restrictions is None:
        return DeferredExecutionDecision(False, "restrictions_unrecorded")
    # Checked exactly as capabilities are, and refused in either direction
    # rather than reconciled.
    if grant.approved_restrictions != restrictions_of(plan):
        return DeferredExecutionDecision(False, "restriction_mismatch")
    if allowance is None:
        return DeferredExecutionDecision(False, "allowance_unavailable")
    step_id = execution.next_pending_step_id
    step = next((value for value in plan.steps if value.step_id == step_id), None)
    if step is None or not allowance.affords(cost_for(step.capability)):
        return DeferredExecutionDecision(False, "allowance_exhausted")
    return DeferredExecutionDecision(True, "deferred_eligible")
