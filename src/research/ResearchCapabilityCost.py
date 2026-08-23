"""Declared resource cost for every executable research capability.

Autonomy budgets are enforced from this table, never inferred from operation
names or authored instruction text. The table is exhaustive by construction: a
capability added without a declared cost raises here rather than silently
consuming an unaccounted network or model call.
"""

from __future__ import annotations

from core.Exceptions import ResearchError
from research.ResearchOperationCost import ResearchOperationCost
from research.ResearchPlanStepCapability import ResearchPlanStepCapability

_LOCAL = ResearchOperationCost()
_ONE_NETWORK_CALL = ResearchOperationCost(network_operations=1)

CAPABILITY_COSTS: dict[ResearchPlanStepCapability, ResearchOperationCost] = {
    ResearchPlanStepCapability.NONE: _LOCAL,
    ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH: _LOCAL,
    ResearchPlanStepCapability.ACCEPTED_SOURCE_LISTING: _LOCAL,
    ResearchPlanStepCapability.EVIDENCE_INTEGRITY_CHECK: _LOCAL,
    ResearchPlanStepCapability.SOURCE_DISCOVERY: _ONE_NETWORK_CALL,
    ResearchPlanStepCapability.SOURCE_FETCH: _ONE_NETWORK_CALL,
    ResearchPlanStepCapability.SOURCE_ACCEPT: _ONE_NETWORK_CALL,
    ResearchPlanStepCapability.EVIDENCE_RECORDING: _LOCAL,
    ResearchPlanStepCapability.SOURCE_ASSESSMENT: _LOCAL,
    ResearchPlanStepCapability.CLAIM_CREATION: _LOCAL,
    ResearchPlanStepCapability.CLAIM_CONTRADICTION: _LOCAL,
    ResearchPlanStepCapability.SOURCE_COMPARISON: _LOCAL,
    ResearchPlanStepCapability.RESEARCH_RUN_COMPLETION: _LOCAL,
}


def cost_for(capability: ResearchPlanStepCapability) -> ResearchOperationCost:
    """Return the declared cost, refusing an undeclared capability."""
    if not isinstance(capability, ResearchPlanStepCapability):
        raise ResearchError("Research capability is invalid.")
    cost = CAPABILITY_COSTS.get(capability)
    if cost is None:
        raise ResearchError(
            f"Research capability '{capability.value}' has no declared cost."
        )
    return cost
