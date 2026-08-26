"""The bounded outcome of checking one approval against one exact plan.

An enum rather than a sentence. A caller that had to read prose would end up
parsing it, and a parsed refusal is a refusal one careless edit away from
becoming an approval.

Deliberately not `ToolDisposition`. That vocabulary describes whether a tool
ran, and nothing here runs anything; reusing it would imply an execution that
did not happen.
"""

from __future__ import annotations

from enum import StrEnum


class ResearchPlanAuthorizationVerdict(StrEnum):
    """Say whether one approval covers this exact plan, run, and moment."""

    VALID = "valid"
    DIGEST_MISMATCH = "digest_mismatch"
    RUN_MISMATCH = "run_mismatch"
    CAPABILITY_MISMATCH = "capability_mismatch"
    EXPIRED = "expired"

    @property
    def authorizes(self) -> bool:
        """Return whether this verdict permits anything.

        Only one value does. Expressed as "is it VALID" rather than "is it not
        one of the refusals", so a verdict added later is refused by default
        instead of quietly authorizing until someone updates a list.
        """
        return self is ResearchPlanAuthorizationVerdict.VALID
