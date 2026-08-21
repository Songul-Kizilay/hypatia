"""Read-only history of user-reviewed research-claim contradictions."""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchClaimContradictionRecord import (
    ResearchClaimContradictionRecord,
)
from research.ResearchClaimRecord import ResearchClaimRecord
from research.ResearchRunStatus import ResearchRunStatus


@dataclass(frozen=True, slots=True)
class ResearchClaimContradictionPreview:
    """Expose persisted contradiction audit history without inference."""

    run_id: str
    question: str
    run_status: ResearchRunStatus
    claims: tuple[ResearchClaimRecord, ...]
    contradictions: tuple[ResearchClaimContradictionRecord, ...]
    reason: str

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.run_id, "Research claim contradiction preview run ID"),
            (self.question, "Research claim contradiction preview question"),
            (self.reason, "Research claim contradiction preview reason"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ResearchError(f"{field_name} cannot be empty.")
        if not isinstance(self.run_status, ResearchRunStatus):
            raise ResearchError(
                "Research claim contradiction preview run status is invalid."
            )
        if not isinstance(self.claims, tuple) or not all(
            isinstance(claim, ResearchClaimRecord) for claim in self.claims
        ):
            raise ResearchError(
                "Research claim contradiction preview claims are invalid."
            )
        if not isinstance(self.contradictions, tuple) or not all(
            isinstance(record, ResearchClaimContradictionRecord)
            for record in self.contradictions
        ):
            raise ResearchError(
                "Research claim contradiction preview history is invalid."
            )
        claim_ids = {claim.claim_id for claim in self.claims}
        if any(
            not set(record.claim_ids).issubset(claim_ids)
            for record in self.contradictions
        ):
            raise ResearchError(
                "Research claim contradiction preview references unknown claims."
            )
        object.__setattr__(self, "run_id", self.run_id.strip())
        object.__setattr__(self, "question", self.question.strip())
        object.__setattr__(self, "reason", self.reason.strip())
