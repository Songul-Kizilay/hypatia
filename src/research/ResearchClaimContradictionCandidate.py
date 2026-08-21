"""One bounded, non-persistent claim-contradiction candidate."""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError

MAX_CONTRADICTION_CANDIDATE_EVIDENCE = 40
MAX_CONTRADICTION_CANDIDATE_RATIONALE_CHARACTERS = 1_000


@dataclass(frozen=True, slots=True)
class ResearchClaimContradictionCandidate:
    """A review suggestion that never records or changes either claim."""

    claim_ids: tuple[str, str]
    evidence_ids: tuple[str, ...]
    rationale: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.claim_ids, tuple)
            or len(self.claim_ids) != 2
            or not all(
                isinstance(claim_id, str) and claim_id.strip()
                for claim_id in self.claim_ids
            )
        ):
            raise ResearchError(
                "Research claim contradiction candidate requires two claim IDs."
            )
        normalized_claim_ids = tuple(claim_id.strip() for claim_id in self.claim_ids)
        if normalized_claim_ids[0] == normalized_claim_ids[1]:
            raise ResearchError(
                "Research claim contradiction candidate claims must be distinct."
            )
        if (
            not isinstance(self.evidence_ids, tuple)
            or not self.evidence_ids
            or len(self.evidence_ids) > MAX_CONTRADICTION_CANDIDATE_EVIDENCE
            or not all(
                isinstance(evidence_id, str) and evidence_id.strip()
                for evidence_id in self.evidence_ids
            )
        ):
            raise ResearchError(
                "Research claim contradiction candidate evidence is invalid."
            )
        normalized_evidence_ids = tuple(
            evidence_id.strip() for evidence_id in self.evidence_ids
        )
        if len(normalized_evidence_ids) != len(set(normalized_evidence_ids)):
            raise ResearchError(
                "Research claim contradiction candidate evidence contains duplicates."
            )
        if (
            not isinstance(self.rationale, str)
            or not self.rationale.strip()
            or len(self.rationale.strip())
            > MAX_CONTRADICTION_CANDIDATE_RATIONALE_CHARACTERS
        ):
            raise ResearchError(
                "Research claim contradiction candidate rationale is invalid."
            )
        object.__setattr__(self, "claim_ids", normalized_claim_ids)
        object.__setattr__(self, "evidence_ids", normalized_evidence_ids)
        object.__setattr__(self, "rationale", self.rationale.strip())
