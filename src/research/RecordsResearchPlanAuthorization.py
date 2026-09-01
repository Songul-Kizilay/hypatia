"""Structural boundary for recording one human approval of an exact plan.

The research layer names what it needs and the application layer provides it,
exactly as source acceptance already works. Curiosity therefore depends on the
idea of an approval being recorded rather than on the service that records it,
and the dependency runs one way: nothing here imports cognition.

Narrow on purpose. There is one method, it takes an already-canonical plan, and
it returns the approval or nothing. Deciding *whether* to approve — whose
question it was, whether the gap is still current, whether the digest is the one
a person read — belongs to the caller that holds that context, so this port
cannot be mistaken for the place those checks live.
"""

from typing import Protocol

from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchDisclosure import ResearchDisclosure
from research.ResearchPlan import ResearchPlan
from research.ResearchPlanAuthorization import ResearchPlanAuthorization


class RecordsResearchPlanAuthorization(Protocol):
    """Record one human approval of an exact plan, or report it was not kept."""

    def record_for_plan(
        self,
        plan: ResearchPlan,
        research_run_id: str,
        disclosure: ResearchDisclosure = ResearchDisclosure.NONE,
        budget: ResearchAutonomyBudget | None = None,
    ) -> ResearchPlanAuthorization | None:
        """Return the recorded approval, or None when it was not made durable.

        The budget is the authority a person chose to grant. Passing nothing
        means they left it alone and the standing default applies; it never
        means "work out what this plan needs and grant that".
        """

    def authorization_for_execution(
        self,
        execution_id: str,
    ) -> ResearchPlanAuthorization | None:
        """Return the approval that was spent on this exact execution, if any.

        Matched on the consumption's own execution identity, so it names one
        approval or none. A caller uses it to check what was approved, never to
        gain permission: the approval it returns is already spent.
        """
