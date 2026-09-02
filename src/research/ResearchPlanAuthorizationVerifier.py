"""Answer one question, purely: does this approval cover this exact work?

No I/O, no persistence, no network, no model call, no tool call, no filesystem
access, no mutation, no task, no evidence, no execution. The verifier reads
three values and returns one bounded verdict.

The capability check exists because the authorization stores its derived set
alongside the digest. A hand-built record could therefore claim capabilities its
plan does not declare, and this is the only place where the plan is actually
present to notice. Deriving again and comparing costs nothing and closes the one
route by which an approval could grant more than the plan it approved.

Check order is fixed and tested: is this the same plan, is it the same run, does
it grant only what the plan declares, has it already been spent, and is it still
valid. Identity before validity, because "you edited the plan" is more useful to
a reader than "and also it expired"; spent before expired for the same reason,
since an approval that was already used will never be usable again whatever the
clock says.
"""

from __future__ import annotations

from datetime import datetime

from core.Exceptions import ResearchError
from research.ResearchPlan import ResearchPlan
from research.ResearchPlanAuthorization import (
    ResearchPlanAuthorization,
    capabilities_of,
    restrictions_of,
)
from research.ResearchPlanAuthorizationVerdict import (
    ResearchPlanAuthorizationVerdict,
)
from research.ResearchPlanDigest import plan_digest


def verify_plan_authorization(
    authorization: ResearchPlanAuthorization,
    plan: ResearchPlan,
    research_run_id: str,
    moment: datetime,
) -> ResearchPlanAuthorizationVerdict:
    """Return whether this approval covers this plan, run, and moment."""
    if not isinstance(authorization, ResearchPlanAuthorization):
        raise ResearchError("Verification requires a validated authorization.")
    if not isinstance(plan, ResearchPlan):
        raise ResearchError("Verification requires a validated plan.")
    if not isinstance(research_run_id, str) or not research_run_id.strip():
        raise ResearchError("Verification requires a research run ID.")
    if not isinstance(moment, datetime) or moment.tzinfo is None:
        raise ResearchError("Verification requires a timezone-aware moment.")

    if authorization.plan_digest != plan_digest(plan):
        return ResearchPlanAuthorizationVerdict.DIGEST_MISMATCH
    if authorization.research_run_id != research_run_id.strip():
        return ResearchPlanAuthorizationVerdict.RUN_MISMATCH
    if authorization.capabilities != capabilities_of(plan):
        return ResearchPlanAuthorizationVerdict.CAPABILITY_MISMATCH
    # Checked the same way and for the same reason. The digest already covers
    # the plan's restrictions, so disagreement here means the stored approval
    # and the plan it names describe different things; that is refused rather
    # than reconciled, in either direction.
    if authorization.approved_restrictions != restrictions_of(plan):
        return ResearchPlanAuthorizationVerdict.RESTRICTION_MISMATCH
    if authorization.is_consumed:
        return ResearchPlanAuthorizationVerdict.ALREADY_CONSUMED
    if authorization.has_expired_at(moment):
        return ResearchPlanAuthorizationVerdict.EXPIRED
    return ResearchPlanAuthorizationVerdict.VALID
