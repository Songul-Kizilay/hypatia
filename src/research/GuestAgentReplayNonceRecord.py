"""One durable fact: this exact replay identity has already been spent.

REPLAY ACCEPTED != AUTHORITY TO EXECUTE. REPLAY REJECTED != AUTHORITY
DECISION. A record here answers exactly one question -- "has this one-time
protocol token already been consumed?" -- and nothing else. It grants
nothing, checks no scope, reads no authorization store, and starts no
process; `research.GuestAgentReplayProtector.GuestAgentReplayProtector` is
the only thing that ever decides whether a new record may be written, and
even that decision is bookkeeping, not permission.

The replay identity is the triple `(protocol_version, operation_digest,
nonce)`, not `nonce` alone. A protocol message's own `operation_digest`
already commits (the digest is
`research.ResearchKaliOperationPreview.kali_operation_preview_digest`,
hashed over the complete authorized preview) to exactly which reviewed
operation a nonce was issued for, so binding the two together is what
keeps two unrelated requests that happen to reuse the same nonce text from
accidentally aliasing into the same spent token. `protocol_version` is
included too so a future, differently-shaped wire generation can never
collide with this one merely by reusing a nonce string. `operation_kind`
is deliberately not a separate field: it is already implied by
`operation_digest` (the digest is computed over a preview that names it),
and restating it here would be a second, derivable copy of a fact the
digest already owns.

`request_id` is carried for correlation and audit only -- exactly the role
it already has on `research.GuestAgentProtocol.GuestAgentRequest` -- and is
not part of the replay identity: two different replay-protected requests
are never meant to share a `request_id`, but nothing here enforces that,
because `request_id` was never meant to disambiguate operations in the
first place.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from core.Exceptions import ResearchError
from research.GuestAgentProtocol import (
    MAX_NONCE_LENGTH,
    MAX_REQUEST_ID_LENGTH,
    GuestAgentProtocolVersion,
)
from research.ResearchKaliOperationPreview import is_kali_operation_digest


@dataclass(frozen=True, slots=True)
class GuestAgentReplayNonceRecord:
    """Name one already-consumed replay identity, and when it was spent."""

    protocol_version: GuestAgentProtocolVersion
    operation_digest: str
    nonce: str
    request_id: str
    consumed_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.protocol_version, GuestAgentProtocolVersion):
            raise ResearchError(
                "Guest-agent replay record protocol version is invalid."
            )
        if not is_kali_operation_digest(self.operation_digest):
            raise ResearchError(
                "Guest-agent replay record operation digest is invalid."
            )
        self._require_bounded_text(self.nonce, "nonce", MAX_NONCE_LENGTH)
        self._require_bounded_text(
            self.request_id, "request identifier", MAX_REQUEST_ID_LENGTH
        )
        if (
            not isinstance(self.consumed_at, datetime)
            or self.consumed_at.tzinfo is None
        ):
            raise ResearchError(
                "Guest-agent replay record consumption time must be timezone-aware."
            )
        if self.consumed_at.utcoffset() != timedelta(0):
            raise ResearchError(
                "Guest-agent replay record consumption time must be stored in UTC."
            )

    @property
    def replay_identity(self) -> tuple[str, str, str]:
        """Return the exact `(protocol_version, operation_digest, nonce)`
        triple this record claims to have already consumed."""
        return (self.protocol_version.value, self.operation_digest, self.nonce)

    @staticmethod
    def _require_bounded_text(value: object, label: str, maximum: int) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ResearchError(f"Guest-agent replay record {label} cannot be empty.")
        if "\x00" in value or "\r" in value or "\n" in value:
            raise ResearchError(
                f"Guest-agent replay record {label} contains control data."
            )
        if len(value) > maximum:
            raise ResearchError(f"Guest-agent replay record {label} is too long.")
