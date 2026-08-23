"""Explicit authorization for one confirmed claim contradiction.

Authorizes exactly two current claims from the bound run and one authored note
explaining the contradiction.

A proposal is not a contradiction. Any suggestion, including one produced by a
language model, remains a proposal until a human authorizes it here and the
canonical path persists it.

Recording a contradiction never edits either claim's text, epistemic state, or
confidence, and never decides which claim is true. It records that two authored
claims conflict, and nothing more.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError

MAX_CONTRADICTION_AUTHORIZATION_NOTE_CHARACTERS = 1_000


@dataclass(frozen=True, slots=True)
class ResearchContradictionAuthorization:
    """Exactly two current claim identities and one authored note."""

    claim_ids: tuple[str, str]
    note: str

    def __post_init__(self) -> None:
        if not isinstance(self.claim_ids, tuple):
            raise ResearchError(
                "Contradiction authorization claim IDs must be an immutable tuple."
            )
        if len(self.claim_ids) != 2:
            raise ResearchError(
                "Contradiction authorization requires exactly two claim IDs."
            )
        if not all(
            isinstance(claim_id, str) and claim_id.strip()
            for claim_id in self.claim_ids
        ):
            raise ResearchError("Contradiction authorization claim ID cannot be empty.")
        normalized = tuple(claim_id.strip() for claim_id in self.claim_ids)
        if normalized[0] == normalized[1]:
            raise ResearchError(
                "Contradiction authorization requires two distinct claim IDs."
            )
        if not isinstance(self.note, str) or not self.note.strip():
            raise ResearchError("Contradiction authorization note cannot be empty.")
        note = self.note.strip()
        if len(note) > MAX_CONTRADICTION_AUTHORIZATION_NOTE_CHARACTERS:
            raise ResearchError("Contradiction authorization note is too long.")
        object.__setattr__(self, "claim_ids", normalized)
        object.__setattr__(self, "note", note)
