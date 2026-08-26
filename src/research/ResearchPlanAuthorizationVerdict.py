"""The bounded outcome of checking one approval against one exact plan.

An enum rather than a sentence. A caller that had to read prose would end up
parsing it, and a parsed refusal is a refusal one careless edit away from
becoming an approval.

Deliberately not `ToolDisposition`. That vocabulary describes whether a tool
ran, and reusing it here would imply an execution that never started — every
value below except VALID means work was not reached rather than attempted.

Six values are what the pure verifier can decide from an approval, a plan, a run
and a moment — including whether the approval was already spent, which the
record itself now says. The other four need the store or the request: whether
the approval exists at all, whether the work asks for more budget or more
disclosure than was approved, and whether spending it could actually be written
down. They live in one vocabulary because a caller has one question — may this
start? — and two enums would only mean somebody has to map between them.
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
    UNKNOWN = "unknown"
    ALREADY_CONSUMED = "already_consumed"
    BUDGET_EXCEEDED = "budget_exceeded"
    DISCLOSURE_UNSATISFIED = "disclosure_unsatisfied"
    NOT_RECORDED = "not_recorded"

    @property
    def authorizes(self) -> bool:
        """Return whether this verdict permits anything.

        Only one value does. Expressed as "is it VALID" rather than "is it not
        one of the refusals", so a verdict added later is refused by default
        instead of quietly authorizing until someone updates a list.
        """
        return self is ResearchPlanAuthorizationVerdict.VALID
