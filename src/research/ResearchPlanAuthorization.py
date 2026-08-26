"""One immutable approval of one exact research plan.

This records a decision. It executes nothing, queues nothing, and permits
nothing on its own: no code path currently consults it, which is deliberate.
An approval has to be able to name what it approved before anything may act on
it, and naming that is all this milestone does.

Capabilities are derived from the approved plan by `for_plan` rather than typed
alongside it. A separately typed set is a set that can be typed wider than the
plan, and an approval that grants more than it displays is the failure this
whole boundary exists to prevent. The derived set is still stored so a reviewer
can read what was granted without re-deriving it — and because it is stored, a
hand-built record could still disagree with its plan. That disagreement is
caught by the verifier, at the only point where the plan is actually available.

Validity is bounded and terminal. There is no renewal, no refresh, no grace
period, and no extension, because each of those is a way for one approval to
outlive the moment it described.

Single use is now real. An approval carries at most one consumption naming the
exact execution it was spent on, the transition is one-way, and a consumed
approval can never verify as covering anything again. Nothing refunds it: an
attempt that failed, blocked, was cancelled, or died mid-flight still spent the
approval, because the approval was for the attempt.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from core.Exceptions import ResearchError
from research.ResearchAuthorizer import ResearchAuthorizer
from research.ResearchAutonomyBudget import (
    MAX_AUTONOMY_SECONDS,
    ResearchAutonomyBudget,
)
from research.ResearchDisclosure import ResearchDisclosure
from research.ResearchPlan import ResearchPlan
from research.ResearchPlanAuthorizationConsumption import (
    ResearchPlanAuthorizationConsumption,
)
from research.ResearchPlanDigest import is_plan_digest, plan_digest
from research.ResearchPlanStepCapability import ResearchPlanStepCapability

MAX_AUTHORIZATION_ID_CHARACTERS = 200
MAX_AUTHORIZATION_RUN_ID_CHARACTERS = 200

#: An approval may not outlive the longest single run it could have permitted.
#: Reused from the autonomy ceiling rather than chosen separately, so the two
#: cannot drift into disagreeing about how long "one run" lasts.
MAX_AUTHORIZATION_VALIDITY_SECONDS = MAX_AUTONOMY_SECONDS


@dataclass(frozen=True, slots=True)
class ResearchPlanAuthorization:
    """Bind one approval to one exact plan, run, budget, and validity window."""

    authorization_id: str
    plan_digest: str
    research_run_id: str
    capabilities: frozenset[ResearchPlanStepCapability]
    budget: ResearchAutonomyBudget
    authorized_at: datetime
    expires_at: datetime
    disclosure: ResearchDisclosure = ResearchDisclosure.NONE
    authorized_by: ResearchAuthorizer = ResearchAuthorizer.HUMAN
    consumption: ResearchPlanAuthorizationConsumption | None = None

    def __post_init__(self) -> None:
        authorization_id = self._bounded_text(
            self.authorization_id,
            "Research plan authorization ID",
            MAX_AUTHORIZATION_ID_CHARACTERS,
        )
        research_run_id = self._bounded_text(
            self.research_run_id,
            "Research plan authorization run ID",
            MAX_AUTHORIZATION_RUN_ID_CHARACTERS,
        )
        if not is_plan_digest(self.plan_digest):
            raise ResearchError(
                "Research plan authorization requires a valid plan digest."
            )
        if not isinstance(self.capabilities, frozenset):
            raise ResearchError(
                "Research plan authorization capabilities must be an immutable set."
            )
        if not self.capabilities:
            raise ResearchError(
                "Research plan authorization requires at least one capability."
            )
        if not all(
            isinstance(capability, ResearchPlanStepCapability)
            for capability in self.capabilities
        ):
            raise ResearchError("Research plan authorization capability is invalid.")
        if not isinstance(self.budget, ResearchAutonomyBudget):
            raise ResearchError("Research plan authorization budget is invalid.")
        if not isinstance(self.disclosure, ResearchDisclosure):
            raise ResearchError("Research plan authorization disclosure is invalid.")
        if not isinstance(self.authorized_by, ResearchAuthorizer):
            raise ResearchError("Research plan authorization authority is invalid.")
        if self.consumption is not None and not isinstance(
            self.consumption, ResearchPlanAuthorizationConsumption
        ):
            raise ResearchError("Research plan authorization consumption is invalid.")
        self._validate_window()
        object.__setattr__(self, "authorization_id", authorization_id)
        object.__setattr__(self, "research_run_id", research_run_id)

    @classmethod
    def for_plan(
        cls,
        *,
        authorization_id: str,
        plan: ResearchPlan,
        research_run_id: str,
        budget: ResearchAutonomyBudget,
        authorized_at: datetime,
        expires_at: datetime,
        disclosure: ResearchDisclosure = ResearchDisclosure.NONE,
    ) -> ResearchPlanAuthorization:
        """Approve exactly this plan, deriving its digest and capabilities.

        The only constructor a caller should use. It takes no capability
        argument, so an approval cannot be typed wider than the plan it is
        approving.
        """
        if not isinstance(plan, ResearchPlan):
            raise ResearchError(
                "Research plan authorization requires a validated plan."
            )
        return cls(
            authorization_id=authorization_id,
            plan_digest=plan_digest(plan),
            research_run_id=research_run_id,
            capabilities=capabilities_of(plan),
            budget=budget,
            authorized_at=authorized_at,
            expires_at=expires_at,
            disclosure=disclosure,
        )

    @property
    def is_consumed(self) -> bool:
        """Return whether this approval has already been spent."""
        return self.consumption is not None

    def consumed_for(
        self,
        execution_id: str,
        moment: datetime,
    ) -> ResearchPlanAuthorization:
        """Spend this approval on exactly one execution, once and for good.

        Refuses a second consumption rather than overwriting the first. An
        approval that could be re-consumed would let one permission authorize
        two attempts, which is the failure this whole boundary exists to stop.
        """
        if self.is_consumed:
            raise ResearchError("This approval has already been used.")
        return replace(
            self,
            consumption=ResearchPlanAuthorizationConsumption(
                execution_id=execution_id,
                consumed_at=moment,
            ),
        )

    @property
    def validity(self) -> timedelta:
        """Return how long this approval is valid for."""
        return self.expires_at - self.authorized_at

    def has_expired_at(self, moment: datetime) -> bool:
        """Return whether this approval is no longer valid at this moment."""
        if not isinstance(moment, datetime) or moment.tzinfo is None:
            raise ResearchError(
                "Research plan authorization expiry check requires an aware time."
            )
        return moment >= self.expires_at

    def _validate_window(self) -> None:
        for value, label in (
            (self.authorized_at, "authorization time"),
            (self.expires_at, "expiry time"),
        ):
            if not isinstance(value, datetime) or value.tzinfo is None:
                raise ResearchError(f"Research plan {label} must be timezone-aware.")
        if self.expires_at <= self.authorized_at:
            raise ResearchError(
                "Research plan authorization must expire after it was given."
            )
        if self.validity.total_seconds() > MAX_AUTHORIZATION_VALIDITY_SECONDS:
            raise ResearchError(
                "Research plan authorization validity exceeds its hard ceiling."
            )

    @staticmethod
    def _bounded_text(value: str, label: str, maximum: int) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ResearchError(f"{label} cannot be empty.")
        normalized = value.strip()
        if len(normalized) > maximum:
            raise ResearchError(f"{label} is too long.")
        return normalized


def capabilities_of(plan: ResearchPlan) -> frozenset[ResearchPlanStepCapability]:
    """Return exactly the capabilities this plan's steps declare."""
    if not isinstance(plan, ResearchPlan):
        raise ResearchError("Research plan capabilities require a validated plan.")
    return frozenset(step.capability for step in plan.steps)
