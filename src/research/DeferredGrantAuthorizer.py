"""Truthful provenance for unattended research permission."""

from enum import StrEnum


class DeferredGrantAuthorizer(StrEnum):
    """How deferred permission was confirmed, or why it stopped applying.

    This is a local trust-boundary statement, not cryptographic identity or
    protection from arbitrary code already executing inside Hypatia.

    Closed and additive, the same security-control role
    `ResearchAuthorityRequirementKind` plays with its own member set: a
    future reason is a new named member, never a widened meaning for an
    existing one. `SUPERSEDED_BY_RENEWAL` exists specifically so an expired
    grant's automatic retirement, when a fresh one is issued for the same
    task, is never misattributed to `TRUSTED_LOCAL_OPERATOR` -- nobody
    reviewed or chose to revoke it; its own validity window simply ran out,
    and issuing its replacement is what closes it, not a human decision
    about that exact record.
    """

    TRUSTED_LOCAL_OPERATOR = "trusted_local_operator"
    SUPERSEDED_BY_RENEWAL = "superseded_by_renewal"
