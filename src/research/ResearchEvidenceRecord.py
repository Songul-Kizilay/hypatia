"""Traceable bounded evidence selected from one accepted research source."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256

from core.Exceptions import ResearchError
from knowledge.Chunk import Chunk
from research.ResearchSensitiveInputPolicy import ResearchSensitiveInputPolicy

MAX_EVIDENCE_EXCERPT_CHARACTERS = 1_000
MAX_EVIDENCE_NOTE_CHARACTERS = 1_000

_SENSITIVE_INPUT_POLICY = ResearchSensitiveInputPolicy()


def _refuse_sensitive_input(value: str, label: str) -> None:
    sensitive_class = _SENSITIVE_INPUT_POLICY.classify(value)
    if sensitive_class.refused:
        raise ResearchError(f"{label} was refused as {sensitive_class.operator_label}.")


@dataclass(frozen=True, slots=True)
class ResearchEvidenceRecord:
    """Persist a bounded chunk snapshot and its integrity fingerprint."""

    evidence_id: str
    source_document_id: str
    chunk_id: str
    chunk_index: int
    excerpt: str
    excerpt_truncated: bool
    chunk_sha256: str
    note: str
    recorded_at: datetime

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.evidence_id, "Research evidence ID"),
            (self.source_document_id, "Research evidence source document ID"),
            (self.chunk_id, "Research evidence chunk ID"),
            (self.excerpt, "Research evidence excerpt"),
            (self.note, "Research evidence note"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ResearchError(f"{field_name} cannot be empty.")
        if isinstance(self.chunk_index, bool) or not isinstance(self.chunk_index, int):
            raise ResearchError("Research evidence chunk index must be an integer.")
        if self.chunk_index < 0:
            raise ResearchError("Research evidence chunk index cannot be negative.")
        if len(self.excerpt.strip()) > MAX_EVIDENCE_EXCERPT_CHARACTERS:
            raise ResearchError("Research evidence excerpt is too long.")
        if not isinstance(self.excerpt_truncated, bool):
            raise ResearchError("Research evidence truncation flag must be boolean.")
        if (
            not isinstance(self.chunk_sha256, str)
            or len(self.chunk_sha256) != 64
            or any(
                character not in "0123456789abcdef" for character in self.chunk_sha256
            )
        ):
            raise ResearchError("Research evidence chunk fingerprint is invalid.")
        if len(self.note.strip()) > MAX_EVIDENCE_NOTE_CHARACTERS:
            raise ResearchError("Research evidence note is too long.")
        _refuse_sensitive_input(self.note.strip(), "Research evidence note")
        if (
            not isinstance(self.recorded_at, datetime)
            or self.recorded_at.utcoffset() is None
        ):
            raise ResearchError("Research evidence time must be timezone-aware.")
        object.__setattr__(self, "evidence_id", self.evidence_id.strip())
        object.__setattr__(
            self,
            "source_document_id",
            self.source_document_id.strip(),
        )
        object.__setattr__(self, "chunk_id", self.chunk_id.strip())
        object.__setattr__(self, "excerpt", self.excerpt.strip())
        object.__setattr__(self, "chunk_sha256", self.chunk_sha256.casefold())
        object.__setattr__(self, "note", self.note.strip())

    @classmethod
    def from_chunk(
        cls,
        evidence_id: str,
        chunk: Chunk,
        note: str,
        recorded_at: datetime,
    ) -> ResearchEvidenceRecord:
        """Create a bounded immutable record from one currently indexed chunk."""
        if not isinstance(chunk, Chunk):
            raise ResearchError("Research evidence expects a knowledge chunk.")
        content = chunk.content.strip()
        return cls(
            evidence_id=evidence_id,
            source_document_id=chunk.document_id,
            chunk_id=chunk.chunk_id,
            chunk_index=chunk.index,
            excerpt=content[:MAX_EVIDENCE_EXCERPT_CHARACTERS],
            excerpt_truncated=len(content) > MAX_EVIDENCE_EXCERPT_CHARACTERS,
            chunk_sha256=sha256(content.encode("utf-8")).hexdigest(),
            note=note,
            recorded_at=recorded_at,
        )
