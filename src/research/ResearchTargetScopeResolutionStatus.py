"""What one already-authored scope says about one hostname or address.

This is an explanation, never an authorization primitive. Nothing here grants,
implies, or substitutes for a fetch, a scan, or any other active interaction —
only the existing `require_hostname`/`require_addresses` gates and further
upstream authorization records do that. Reading `IN_SCOPE` off a resolution is
not permission to proceed with anything.
"""

from __future__ import annotations

from enum import StrEnum


class ResearchTargetScopeResolutionStatus(StrEnum):
    """A true tri-state read of a scope's stance toward one target.

    Three answers and deliberately no fourth. `IN_SCOPE` and `OUT_OF_SCOPE` are
    the two confident answers, each citing the exact rule that produced them.
    `UNCERTAIN` is the honest default for a target no rule in this scope
    addresses at all — it must never be silently folded into either confident
    state, and discovering a hostname (by redirect, CNAME, or any other means)
    never moves it out of `UNCERTAIN` on its own.
    """

    IN_SCOPE = "in_scope"
    OUT_OF_SCOPE = "out_of_scope"
    UNCERTAIN = "uncertain"

    @property
    def settles(self) -> bool:
        """Return whether this status names a confident scope stance."""
        return self is not ResearchTargetScopeResolutionStatus.UNCERTAIN
