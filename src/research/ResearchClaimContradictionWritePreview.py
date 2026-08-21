"""No-write decision for one user-reviewed claim contradiction."""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchClaimRecord import ResearchClaimRecord
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchRunStatus import ResearchRunStatus


@dataclass(frozen=True, slots=True)
class ResearchClaimContradictionWritePreview:
    """Show exact claims, evidence, and authored note before confirmation."""

    run_id: str
    run_status: ResearchRunStatus
    claims: tuple[ResearchClaimRecord, ResearchClaimRecord]
    evidence: tuple[ResearchEvidenceRecord, ...]
    note: str
    allowed: bool
    reason: str

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.run_id, "Research claim contradiction preview run ID"),
            (self.note, "Research claim contradiction preview note"),
            (self.reason, "Research claim contradiction preview reason"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ResearchError(f"{field_name} cannot be empty.")
        if not isinstance(self.run_status, ResearchRunStatus):
            raise ResearchError(
                "Research claim contradiction preview run status is invalid."
            )
        if (
            not isinstance(self.claims, tuple)
            or len(self.claims) != 2
            or not all(isinstance(claim, ResearchClaimRecord) for claim in self.claims)
            or self.claims[0].claim_id == self.claims[1].claim_id
        ):
            raise ResearchError(
                "Research claim contradiction preview requires two distinct claims."
            )
        if (
            not isinstance(self.evidence, tuple)
            or not self.evidence
            or not all(
                isinstance(record, ResearchEvidenceRecord) for record in self.evidence
            )
        ):
            raise ResearchError(
                "Research claim contradiction preview evidence is invalid."
            )
        expected_evidence_ids = tuple(
            dict.fromkeys(
                evidence_id
                for claim in self.claims
                for evidence_id in claim.evidence_ids
            )
        )
        if (
            tuple(record.evidence_id for record in self.evidence)
            != expected_evidence_ids
        ):
            raise ResearchError(
                "Research claim contradiction preview provenance is inconsistent."
            )
        if not isinstance(self.allowed, bool):
            raise ResearchError(
                "Research claim contradiction preview decision must be boolean."
            )
        object.__setattr__(self, "run_id", self.run_id.strip())
        object.__setattr__(self, "note", self.note.strip())
        object.__setattr__(self, "reason", self.reason.strip())
