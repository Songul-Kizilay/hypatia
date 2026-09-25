"""Immutable, inert context attached to already-recorded HTTP evidence.

An identity label is a human-chosen display name such as ``test-user-1`` or
``admin``. It is not a username field, credential, token, password, cookie,
authorization-header value, or live session identifier. No consumer of this
record may use any value here to perform a request or grant authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.Exceptions import ResearchError
from research.ResearchAuthenticationState import ResearchAuthenticationState
from research.ResearchHttpEvidenceRecord import is_http_evidence_id

MAX_SESSION_CONTEXT_ID_CHARACTERS = 200
MAX_SESSION_CONTEXT_PROGRAM_ID_CHARACTERS = 200
MAX_SESSION_CONTEXT_IDENTITY_LABEL_CHARACTERS = 200
MAX_SESSION_CONTEXT_NOTE_CHARACTERS = 2_000
MAX_SESSION_CONTEXT_EVIDENCE_REFERENCES = 100


def _bounded_identifier(value: object, label: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise ResearchError(f"{label} is invalid.")
    normalized = value.strip()
    if any(ord(character) < 32 or ord(character) == 127 for character in normalized):
        raise ResearchError(f"{label} must be single-line text.")
    return normalized


@dataclass(frozen=True, slots=True)
class ResearchSessionContextRecord:
    """One operator-authored historical authentication-context attestation."""

    session_context_id: str
    program_id: str
    authentication_state: ResearchAuthenticationState
    identity_label: str
    evidence_ids: tuple[str, ...]
    note: str
    recorded_at: datetime

    def __post_init__(self) -> None:
        context_id = _bounded_identifier(
            self.session_context_id,
            "Research session context ID",
            MAX_SESSION_CONTEXT_ID_CHARACTERS,
        )
        program_id = _bounded_identifier(
            self.program_id,
            "Research session context program ID",
            MAX_SESSION_CONTEXT_PROGRAM_ID_CHARACTERS,
        )
        if not isinstance(self.authentication_state, ResearchAuthenticationState):
            raise ResearchError("Research session authentication state is invalid.")
        if not isinstance(self.identity_label, str):
            raise ResearchError("Research session identity label is invalid.")
        identity_label = self.identity_label.strip()
        if len(identity_label) > MAX_SESSION_CONTEXT_IDENTITY_LABEL_CHARACTERS:
            raise ResearchError("Research session identity label is too long.")
        if any(
            ord(character) < 32 or ord(character) == 127 for character in identity_label
        ):
            raise ResearchError(
                "Research session identity label must be single-line display text."
            )
        if self.authentication_state is ResearchAuthenticationState.AUTHENTICATED:
            if not identity_label:
                raise ResearchError(
                    "Authenticated research session context requires an identity label."
                )
        elif self.authentication_state is ResearchAuthenticationState.UNAUTHENTICATED:
            if identity_label:
                raise ResearchError(
                    "Unauthenticated research session context cannot carry an"
                    " identity label."
                )
        else:
            raise ResearchError("Research session authentication state is invalid.")
        if not isinstance(self.evidence_ids, tuple) or any(
            not is_http_evidence_id(value) for value in self.evidence_ids
        ):
            raise ResearchError("Research session evidence references are invalid.")
        if len(self.evidence_ids) > MAX_SESSION_CONTEXT_EVIDENCE_REFERENCES:
            raise ResearchError("Research session has too many evidence references.")
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ResearchError(
                "Research session evidence references contain duplicates."
            )
        if not isinstance(self.note, str):
            raise ResearchError("Research session context note is invalid.")
        note = self.note.strip()
        if len(note) > MAX_SESSION_CONTEXT_NOTE_CHARACTERS:
            raise ResearchError("Research session context note is too long.")
        if (
            not isinstance(self.recorded_at, datetime)
            or self.recorded_at.utcoffset() is None
        ):
            raise ResearchError(
                "Research session context recorded time must be timezone-aware."
            )
        object.__setattr__(self, "session_context_id", context_id)
        object.__setattr__(self, "program_id", program_id)
        object.__setattr__(self, "identity_label", identity_label)
        object.__setattr__(self, "note", note)
