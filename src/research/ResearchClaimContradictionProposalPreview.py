"""Read-only result of an explicitly requested contradiction proposal."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.Exceptions import ResearchError
from research.ResearchClaimContradictionCandidate import (
    ResearchClaimContradictionCandidate,
)
from research.ResearchClaimRecord import ResearchClaimRecord
from research.ResearchRunStatus import ResearchRunStatus


@dataclass(frozen=True, slots=True)
class ResearchClaimContradictionProposalPreview:
    """Expose validated candidates without changing the research audit."""

    run_id: str
    question: str
    run_status: ResearchRunStatus
    snapshot_updated_at: datetime
    provider_name: str
    claims: tuple[ResearchClaimRecord, ...]
    candidates: tuple[ResearchClaimContradictionCandidate, ...]
    reason: str

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.run_id, "Research contradiction proposal run ID"),
            (self.question, "Research contradiction proposal question"),
            (self.provider_name, "Research contradiction proposal provider"),
            (self.reason, "Research contradiction proposal reason"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ResearchError(f"{field_name} cannot be empty.")
        if not isinstance(self.run_status, ResearchRunStatus):
            raise ResearchError("Research contradiction proposal status is invalid.")
        if (
            not isinstance(self.snapshot_updated_at, datetime)
            or self.snapshot_updated_at.utcoffset() is None
        ):
            raise ResearchError(
                "Research contradiction proposal snapshot time must be timezone-aware."
            )
        if not isinstance(self.claims, tuple) or not all(
            isinstance(claim, ResearchClaimRecord) for claim in self.claims
        ):
            raise ResearchError("Research contradiction proposal claims are invalid.")
        if not isinstance(self.candidates, tuple) or not all(
            isinstance(candidate, ResearchClaimContradictionCandidate)
            for candidate in self.candidates
        ):
            raise ResearchError(
                "Research contradiction proposal candidates are invalid."
            )
        claims_by_id = {claim.claim_id: claim for claim in self.claims}
        seen_pairs: set[frozenset[str]] = set()
        for candidate in self.candidates:
            if any(claim_id not in claims_by_id for claim_id in candidate.claim_ids):
                raise ResearchError(
                    "Research contradiction proposal references an unknown claim."
                )
            expected_evidence_ids = tuple(
                dict.fromkeys(
                    evidence_id
                    for claim_id in candidate.claim_ids
                    for evidence_id in claims_by_id[claim_id].evidence_ids
                )
            )
            if candidate.evidence_ids != expected_evidence_ids:
                raise ResearchError(
                    "Research contradiction proposal evidence is inconsistent."
                )
            pair_key = frozenset(candidate.claim_ids)
            if pair_key in seen_pairs:
                raise ResearchError(
                    "Research contradiction proposal contains a duplicate pair."
                )
            seen_pairs.add(pair_key)
        object.__setattr__(self, "run_id", self.run_id.strip())
        object.__setattr__(self, "question", self.question.strip())
        object.__setattr__(self, "provider_name", self.provider_name.strip())
        object.__setattr__(self, "reason", self.reason.strip())
