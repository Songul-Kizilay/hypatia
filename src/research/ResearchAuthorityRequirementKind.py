"""Which existing authority domain a paused execution step is missing.

This names one of the codebase's existing, independently-verified authority
domains (`ResearchPlanAuthorization`, `DeferredExecutionGrant`,
`ResearchKaliOperationAuthorization`) so a durable authority-control pause can
say precisely which kind of approval would clear it, without ever becoming
that approval itself.

Exactly one member exists today. Binding a pause to `DeferredExecutionGrant`
or `ResearchKaliOperationAuthorization` is deliberately out of scope for this
foundation slice and is left for future work; this enum is closed and
additive; a future domain is a new named member, never a widened meaning for
an existing one. The closed member set is itself a security control, the same
role `ResearchAuthorizer` plays with its own single `HUMAN` member.
"""

from enum import StrEnum


class ResearchAuthorityRequirementKind(StrEnum):
    """Bounded vocabulary naming which authority domain applies."""

    PLAN_AUTHORIZATION = "plan_authorization"
