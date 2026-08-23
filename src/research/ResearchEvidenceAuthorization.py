"""Explicit authorization for one evidence record on a plan step.

Grouped rather than spread across flat step fields so capability-specific
authorization stays cohesive as more capabilities are connected.

This authorizes *which* already-accepted content may be recorded and *what a
human said about it*. It never supplies the evidence text itself: the excerpt,
chunk identity, and hash are computed from the real `Chunk` by the existing
evidence domain, so no caller can fabricate an excerpt.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError

MAX_EVIDENCE_AUTHORIZATION_DOCUMENT_ID_CHARACTERS = 200
MAX_EVIDENCE_AUTHORIZATION_NOTE_CHARACTERS = 1_000


@dataclass(frozen=True, slots=True)
class ResearchEvidenceAuthorization:
    """One exact document, one exact chunk index, and one authored note."""

    document_id: str
    chunk_index: int
    note: str

    def __post_init__(self) -> None:
        if not isinstance(self.document_id, str) or not self.document_id.strip():
            raise ResearchError("Evidence authorization document ID cannot be empty.")
        document_id = self.document_id.strip()
        if len(document_id) > MAX_EVIDENCE_AUTHORIZATION_DOCUMENT_ID_CHARACTERS:
            raise ResearchError("Evidence authorization document ID is too long.")
        if (
            isinstance(self.chunk_index, bool)
            or not isinstance(self.chunk_index, int)
            or self.chunk_index < 0
        ):
            raise ResearchError(
                "Evidence authorization chunk index must be a non-negative integer."
            )
        if not isinstance(self.note, str) or not self.note.strip():
            raise ResearchError("Evidence authorization note cannot be empty.")
        note = self.note.strip()
        if len(note) > MAX_EVIDENCE_AUTHORIZATION_NOTE_CHARACTERS:
            raise ResearchError("Evidence authorization note is too long.")
        object.__setattr__(self, "document_id", document_id)
        object.__setattr__(self, "note", note)
