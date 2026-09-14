"""Typed, non-authoritative state for the one pre-approved mission follow-up.

The bounded semantic mission already owns one conditional third-source slot.
This value makes the resolver's decision about that *existing* slot explicit
without authoring another plan, selecting a URL, or granting any authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from core.Exceptions import ResearchError
from research.ResearchPlanStepCapability import ResearchPlanStepCapability


class ResearchMissionFollowupDecisionStatus(StrEnum):
    """Bounded outcomes for the existing conditional mission slot."""

    NOT_APPLICABLE = "not_applicable"
    PROPOSED = "proposed"
    NOT_NEEDED = "not_needed"
    BLOCKED_PREDECESSOR = "blocked_predecessor"
    BUDGET_LIMITED = "budget_limited"
    ALREADY_ATTEMPTED = "already_attempted"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class ResearchMissionFollowupDecision:
    """Describe one existing slot from canonical mission observations only."""

    status: ResearchMissionFollowupDecisionStatus
    plan_digest: str = ""
    step_id: str = ""
    capability: ResearchPlanStepCapability | None = None
    semantic_note_id: str = ""
    semantic_input_fingerprint: str = ""
    semantic_relation: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.status, ResearchMissionFollowupDecisionStatus):
            raise ResearchError("Mission follow-up decision status is invalid.")
        text = (
            self.plan_digest,
            self.step_id,
            self.semantic_note_id,
            self.semantic_input_fingerprint,
            self.semantic_relation,
        )
        if any(not isinstance(value, str) or value != value.strip() for value in text):
            raise ResearchError("Mission follow-up decision binding is invalid.")
        applicable = (
            self.status is not ResearchMissionFollowupDecisionStatus.NOT_APPLICABLE
        )
        if applicable != bool(self.plan_digest and self.step_id):
            raise ResearchError("Mission follow-up decision binding is incomplete.")
        semantic_binding = bool(
            self.semantic_note_id
            and self.semantic_input_fingerprint
            and self.semantic_relation
        )
        if self.status is ResearchMissionFollowupDecisionStatus.BLOCKED_PREDECESSOR:
            if semantic_binding or any(
                (
                    self.semantic_note_id,
                    self.semantic_input_fingerprint,
                    self.semantic_relation,
                )
            ):
                raise ResearchError(
                    "Blocked follow-up cannot invent predecessor state."
                )
        elif applicable != semantic_binding:
            raise ResearchError("Mission follow-up semantic binding is incomplete.")
        if applicable and (
            len(self.plan_digest) != 64
            or any(
                character not in "0123456789abcdef"
                for value in (self.plan_digest,)
                for character in value
            )
            or self.capability is not ResearchPlanStepCapability.SOURCE_FETCH
        ):
            raise ResearchError("Mission follow-up decision cannot change authority.")
        if (
            self.status is not ResearchMissionFollowupDecisionStatus.BLOCKED_PREDECESSOR
            and (
                applicable
                and (
                    len(self.semantic_input_fingerprint) != 64
                    or any(
                        character not in "0123456789abcdef"
                        for character in self.semantic_input_fingerprint
                    )
                )
            )
        ):
            raise ResearchError("Mission follow-up fingerprint is invalid.")
        if not applicable and self.capability is not None:
            raise ResearchError("Inapplicable follow-up cannot name a capability.")

    @property
    def proposed(self) -> bool:
        """Return whether the pre-approved existing slot is ready to derive."""
        return self.status is ResearchMissionFollowupDecisionStatus.PROPOSED
