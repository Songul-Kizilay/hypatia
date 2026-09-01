"""Truthful provenance for unattended research permission."""

from enum import StrEnum


class DeferredGrantAuthorizer(StrEnum):
    """How deferred permission was confirmed.

    This is a local trust-boundary statement, not cryptographic identity or
    protection from arbitrary code already executing inside Hypatia.
    """

    TRUSTED_LOCAL_OPERATOR = "trusted_local_operator"
