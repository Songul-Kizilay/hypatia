"""Whether a plan contradicts a restriction its own author selected.

A plan that forbids external source access and also declares a discovery step
is not a plan anybody can carry out. The contradiction is answerable from the
plan alone — declared capabilities against selected restrictions — so it is
answered here, once, and both the approval boundary and the execution start
ask this same function.

Two copies of this rule would be the real hazard: the one that drifted would be
the one deciding what to allow. There is deliberately no second table.

The answer names the exact step and the exact capability, because "this plan is
contradictory" is not something an author can act on. Nothing is repaired: no
step is dropped, no capability lowered, no provider swapped for a local one. A
plan that says two incompatible things is returned to the person who wrote it.

Pure. Reads a plan, allocates a tuple, and can make nothing happen.
"""

from __future__ import annotations

from dataclasses import dataclass

from research.ResearchPlan import ResearchPlan
from research.ResearchPlanRestriction import ResearchPlanRestriction
from research.ResearchPlanStepCapability import ResearchPlanStepCapability


@dataclass(frozen=True, slots=True)
class ResearchPlanRestrictionConflict:
    """One exact step whose capability a selected restriction forbids."""

    step_id: str
    capability: ResearchPlanStepCapability
    restriction: ResearchPlanRestriction

    def summary(self) -> str:
        """Describe the contradiction without proposing a way around it."""
        return (
            f"Step {self.step_id} declares capability "
            f"'{self.capability.value}', which the selected restriction "
            f"'{self.restriction.value}' forbids."
        )


def plan_restriction_conflicts(
    plan: ResearchPlan,
) -> tuple[ResearchPlanRestrictionConflict, ...]:
    """Return every contradiction between this plan's steps and restrictions.

    An empty tuple means no selected restriction forbids any declared
    capability. It is not a claim that the plan is good, and it says nothing
    about constraints left advisory.
    """
    restrictions = tuple(
        constraint.restriction
        for constraint in plan.constraints
        if constraint.restriction is not None
    )
    if not restrictions:
        return ()
    return tuple(
        ResearchPlanRestrictionConflict(
            step_id=step.step_id,
            capability=step.capability,
            restriction=restriction,
        )
        for step in plan.steps
        for restriction in restrictions
        if restriction.forbids(step.capability)
    )
