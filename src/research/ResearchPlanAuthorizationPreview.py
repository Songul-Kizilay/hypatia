"""No-write view of the approval that confirming would actually record.

Shaped after `ResearchPlanDraftPreview`: either one complete immutable result
or one bounded reason it cannot be produced. Nothing here writes, executes,
fetches, or spends anything.

The preview carries `plan_id` alongside the authorization so a reader can see
both identities at once and see that they are different things. `plan_id` is
the preview someone is looking at; `plan_digest` is the content being approved.
Showing only the first would let a person approve one plan believing they had
approved another, which is the failure this whole boundary exists to prevent.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchPlanAuthorization import ResearchPlanAuthorization
from research.ResearchPlanBudgetRequirement import ResearchPlanBudgetFit
from research.ResearchPlanTargetBinding import ResearchPlanTargetBinding

MAX_AUTHORIZATION_PREVIEW_REASON_CHARACTERS = 500

#: Said on every preview, because the one thing a person needs to know before
#: approving is what approving will not do.
NO_EXECUTION_NOTICE = (
    "Confirming records this approval only. No research is started, no source "
    "is fetched, no model is called, and nothing is queued."
)


@dataclass(frozen=True, slots=True)
class ResearchPlanAuthorizationPreview:
    """Show the exact approval a confirmation would persist, or why it cannot."""

    allowed: bool
    reason: str
    plan_id: str
    authorization: ResearchPlanAuthorization | None
    discovery_providers: tuple[ResearchDiscoveryProviderName, ...] = ()
    #: What one clean pass of this plan would cost, against the budget being
    #: offered. Carried structurally so a refusal names the dimension that ran
    #: out rather than leaving somebody to read it out of a sentence.
    budget_fit: ResearchPlanBudgetFit | None = None
    target_binding: ResearchPlanTargetBinding | None = None

    def __post_init__(self) -> None:
        if self.target_binding is not None and not isinstance(
            self.target_binding, ResearchPlanTargetBinding
        ):
            raise ResearchError("Authorization preview target binding is invalid.")
        if not isinstance(self.allowed, bool):
            raise ResearchError("Authorization preview decision must be boolean.")
        for value, label in (
            (self.reason, "Authorization preview reason"),
            (self.plan_id, "Authorization preview plan ID"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ResearchError(f"{label} cannot be empty.")
        reason = self.reason.strip()
        if len(reason) > MAX_AUTHORIZATION_PREVIEW_REASON_CHARACTERS:
            raise ResearchError("Authorization preview reason is too long.")
        if self.allowed and not isinstance(
            self.authorization, ResearchPlanAuthorization
        ):
            raise ResearchError("An allowed authorization preview requires a record.")
        if not self.allowed and self.authorization is not None:
            raise ResearchError("A refused authorization preview carries no record.")
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "plan_id", self.plan_id.strip())

    @classmethod
    def ready(
        cls,
        plan_id: str,
        authorization: ResearchPlanAuthorization,
        discovery_providers: tuple[ResearchDiscoveryProviderName, ...] = (),
        budget_fit: ResearchPlanBudgetFit | None = None,
        target_binding: ResearchPlanTargetBinding | None = None,
    ) -> ResearchPlanAuthorizationPreview:
        """Show exactly what confirming would record."""
        return cls(
            allowed=True,
            reason=NO_EXECUTION_NOTICE,
            plan_id=plan_id,
            authorization=authorization,
            budget_fit=budget_fit,
            target_binding=target_binding,
        )

    @classmethod
    def rejected(
        cls,
        plan_id: str,
        reason: str,
        budget_fit: ResearchPlanBudgetFit | None = None,
    ) -> ResearchPlanAuthorizationPreview:
        """Explain why no approval can be offered, without a partial record."""
        return cls(
            allowed=False,
            reason=reason,
            plan_id=plan_id,
            authorization=None,
            budget_fit=budget_fit,
        )
