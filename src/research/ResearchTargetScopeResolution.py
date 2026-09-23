"""One scope's literal answer about one target — an explanation, not a grant.

`matched_rule` and `reason` cite only what the scope itself already contains:
the exact allowed/excluded host or network that decided the result, or the
plain fact that no rule in this scope addresses the target. Neither field is
ever inferred, paraphrased, or model-generated, and reading `IN_SCOPE` here is
never itself permission to fetch, scan, or otherwise act on the target — only
`ResearchTargetScope.require_hostname`/`require_addresses` and further
upstream authorization records grant that.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchTargetScopeResolutionStatus import (
    ResearchTargetScopeResolutionStatus,
)

MAX_TARGET_SCOPE_RESOLUTION_TEXT_CHARACTERS = 500


@dataclass(frozen=True, slots=True)
class ResearchTargetScopeResolution:
    """The tri-state result of checking one target against one scope."""

    status: ResearchTargetScopeResolutionStatus
    target: str
    matched_rule: str | None
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, ResearchTargetScopeResolutionStatus):
            raise ResearchError("Target scope resolution status is invalid.")
        for value, label in (
            (self.target, "Target scope resolution target"),
            (self.reason, "Target scope resolution reason"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ResearchError(f"{label} cannot be empty.")
            if len(value.strip()) > MAX_TARGET_SCOPE_RESOLUTION_TEXT_CHARACTERS:
                raise ResearchError(f"{label} is too long.")
        object.__setattr__(self, "target", self.target.strip())
        object.__setattr__(self, "reason", self.reason.strip())
        is_uncertain = self.status is ResearchTargetScopeResolutionStatus.UNCERTAIN
        if is_uncertain and self.matched_rule is not None:
            raise ResearchError(
                "An uncertain target scope resolution cannot cite a matched rule."
            )
        if not is_uncertain:
            if not isinstance(self.matched_rule, str) or not self.matched_rule.strip():
                raise ResearchError(
                    "A settled target scope resolution requires its matched rule."
                )
            matched_rule = self.matched_rule.strip()
            if len(matched_rule) > MAX_TARGET_SCOPE_RESOLUTION_TEXT_CHARACTERS:
                raise ResearchError("Target scope resolution matched rule is too long.")
            object.__setattr__(self, "matched_rule", matched_rule)
