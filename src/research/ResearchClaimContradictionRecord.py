"""Persistent user-reviewed contradiction between two research claims."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.Exceptions import ResearchError

MAX_CLAIM_CONTRADICTION_EVIDENCE = 40
MAX_CLAIM_CONTRADICTION_NOTE_CHARACTERS = 2_000


@dataclass(frozen=True, slots=True)
class ResearchClaimContradictionRecord:
    """Append-only authored relationship with exact persisted provenance."""

    contradiction_id: str
    claim_ids: tuple[str, str]
    evidence_ids: tuple[str, ...]
    note: str
    recorded_at: datetime

    def __post_init__(self) -> None:
        if (
            not isinstance(self.contradiction_id, str)
            or not self.contradiction_id.strip()
        ):
            raise ResearchError("Research claim contradiction ID cannot be empty.")
        normalized_claim_ids = self._normalize_ids(
            self.claim_ids,
            "Research claim contradiction claim IDs",
        )
        if len(normalized_claim_ids) != 2:
            raise ResearchError(
                "Research claim contradiction requires exactly two claim IDs."
            )
        normalized_evidence_ids = self._normalize_ids(
            self.evidence_ids,
            "Research claim contradiction evidence IDs",
        )
        if len(normalized_evidence_ids) > MAX_CLAIM_CONTRADICTION_EVIDENCE:
            raise ResearchError(
                "Research claim contradiction cites too many evidence records."
            )
        if not isinstance(self.note, str) or not self.note.strip():
            raise ResearchError("Research claim contradiction note cannot be empty.")
        normalized_note = self.note.strip()
        if len(normalized_note) > MAX_CLAIM_CONTRADICTION_NOTE_CHARACTERS:
            raise ResearchError("Research claim contradiction note is too long.")
        if (
            not isinstance(self.recorded_at, datetime)
            or self.recorded_at.utcoffset() is None
        ):
            raise ResearchError(
                "Research claim contradiction time must be timezone-aware."
            )
        object.__setattr__(self, "contradiction_id", self.contradiction_id.strip())
        object.__setattr__(self, "claim_ids", normalized_claim_ids)
        object.__setattr__(self, "evidence_ids", normalized_evidence_ids)
        object.__setattr__(self, "note", normalized_note)

    @staticmethod
    def _normalize_ids(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
        if not isinstance(values, tuple) or not values:
            raise ResearchError(f"{field_name} must be a non-empty immutable tuple.")
        if not all(isinstance(value, str) and value.strip() for value in values):
            raise ResearchError(f"{field_name} are invalid.")
        normalized = tuple(value.strip() for value in values)
        if len(normalized) != len(set(normalized)):
            raise ResearchError(f"{field_name} contain duplicates.")
        return normalized
