"""Persistent evidence-linked user-authored research claim."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.Exceptions import ResearchError
from research.ResearchClaimConfidence import ResearchClaimConfidence
from research.ResearchEpistemicState import ResearchEpistemicState

MAX_RESEARCH_CLAIM_CHARACTERS = 2_000
MAX_RESEARCH_CLAIM_EVIDENCE = 20
MAX_RESEARCH_CLAIM_SOURCES = 20


@dataclass(frozen=True, slots=True)
class ResearchClaimRecord:
    """Append-only claim with explicit provenance and authored uncertainty."""

    claim_id: str
    text: str
    epistemic_state: ResearchEpistemicState
    confidence: ResearchClaimConfidence
    source_document_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    recorded_at: datetime
    supersedes_claim_id: str | None = None

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.claim_id, "Research claim ID"),
            (self.text, "Research claim text"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ResearchError(f"{field_name} cannot be empty.")
        if len(self.text.strip()) > MAX_RESEARCH_CLAIM_CHARACTERS:
            raise ResearchError("Research claim text is too long.")
        if not isinstance(self.epistemic_state, ResearchEpistemicState):
            raise ResearchError("Research claim epistemic state is invalid.")
        if not isinstance(self.confidence, ResearchClaimConfidence):
            raise ResearchError("Research claim confidence is invalid.")
        normalized_sources = self._normalize_ids(
            self.source_document_ids,
            "source document",
            MAX_RESEARCH_CLAIM_SOURCES,
        )
        normalized_evidence = self._normalize_ids(
            self.evidence_ids,
            "evidence",
            MAX_RESEARCH_CLAIM_EVIDENCE,
        )
        if (
            not isinstance(self.recorded_at, datetime)
            or self.recorded_at.utcoffset() is None
        ):
            raise ResearchError("Research claim time must be timezone-aware.")
        supersedes_claim_id = self.supersedes_claim_id
        if supersedes_claim_id is not None:
            if (
                not isinstance(supersedes_claim_id, str)
                or not supersedes_claim_id.strip()
            ):
                raise ResearchError("Superseded research claim ID cannot be empty.")
            supersedes_claim_id = supersedes_claim_id.strip()
            if supersedes_claim_id == self.claim_id.strip():
                raise ResearchError("A research claim cannot supersede itself.")
        object.__setattr__(self, "claim_id", self.claim_id.strip())
        object.__setattr__(self, "text", self.text.strip())
        object.__setattr__(self, "source_document_ids", normalized_sources)
        object.__setattr__(self, "evidence_ids", normalized_evidence)
        object.__setattr__(self, "supersedes_claim_id", supersedes_claim_id)

    @staticmethod
    def _normalize_ids(
        values: tuple[str, ...],
        label: str,
        maximum: int,
    ) -> tuple[str, ...]:
        if not isinstance(values, tuple) or not values:
            raise ResearchError(f"Research claim requires explicit {label} IDs.")
        if len(values) > maximum:
            raise ResearchError(f"Research claim has too many {label} IDs.")
        if not all(isinstance(value, str) and value.strip() for value in values):
            raise ResearchError(f"Research claim {label} IDs are invalid.")
        normalized = tuple(value.strip() for value in values)
        if len(normalized) != len(set(normalized)):
            raise ResearchError(f"Research claim contains duplicate {label} IDs.")
        return normalized
