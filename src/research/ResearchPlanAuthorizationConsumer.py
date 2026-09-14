"""The narrow port through which execution may spend one approval.

Execution depends on this rather than on the approval service, so it can ask
exactly one question — may this exact execution begin, and if so spend the
approval — without gaining the ability to preview, list, or create one. A
component that could create the permission it needs is a component that does
not need permission.

Consuming is deliberately part of asking. A separate verify-then-consume pair
would leave a window in which an approval had been checked and not yet spent,
and a crash inside that window is exactly how one permission becomes two
attempts.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchDisclosure import ResearchDisclosure
from research.ResearchPlan import ResearchPlan
from research.ResearchPlanAuthorizationDecision import (
    ResearchPlanAuthorizationDecision,
)


class ResearchPlanAuthorizationConsumer(Protocol):
    """Spend one approval on one execution, or refuse and spend nothing."""

    def consume_for_execution(
        self,
        authorization_id: str,
        plan: ResearchPlan,
        research_run_id: str,
        execution_id: str,
        moment: datetime,
        *,
        budget: ResearchAutonomyBudget | None = None,
        disclosure: ResearchDisclosure | None = None,
    ) -> ResearchPlanAuthorizationDecision:
        """Return whether this execution may begin, having spent the approval.

        A VALID decision means the approval is already durably consumed for
        this exact execution identity. Any other verdict means nothing was
        spent and nothing was written.
        """
