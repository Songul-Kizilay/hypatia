"""A restriction a person selected, and the capabilities it forbids.

Constraint text has been advisory since v0.3.285: "Do not access external
sources" is displayed and bound into the plan's identity, but nothing stops a
step from reaching the network. Reading that sentence and acting on it would
mean guessing what a sentence means, which is the one thing this boundary must
never do.

So enforcement comes from a value the operator picks, never from words. The
text can say anything; only this typed selection blocks anything.

What counts as external is not decided here either. `ResearchCapabilityCost`
already declares, per capability, how many network operations it costs, and
autonomy enforces network budgets from that same table. Asking it means the
restriction and the budget can never disagree about what touches the network —
and a capability added later with a network cost is forbidden automatically
rather than slipping through a list nobody remembered to update.

This can only ever refuse a plan. It grants nothing, widens nothing, and
substitutes nothing.
"""

from __future__ import annotations

from enum import StrEnum

from research.ResearchCapabilityCost import cost_for
from research.ResearchPlanStepCapability import ResearchPlanStepCapability


class ResearchPlanRestriction(StrEnum):
    """Bounded set of mechanically enforced plan restrictions."""

    NO_EXTERNAL_SOURCE_ACCESS = "no_external_source_access"

    def forbids(self, capability: ResearchPlanStepCapability) -> bool:
        """Return whether this restriction refuses that declared capability.

        Derived from the declared cost rather than from a hand-written list of
        capability names, so nothing that spends a network operation can be
        forgotten here.
        """
        if self is ResearchPlanRestriction.NO_EXTERNAL_SOURCE_ACCESS:
            return cost_for(capability).network_operations > 0
        # Unreachable while one member exists. Kept so a second member added
        # later fails loudly here instead of silently forbidding nothing.
        raise NotImplementedError(f"Restriction '{self.value}' forbids nothing.")
