"""Deterministic, pure wire encoding for one signed dispatch envelope.

Mirrors `research.GuestAgentProtocolSerialization`'s exact structural
pattern -- closed required-key sets, fail-closed decoding, the one
existing canonical-JSON convention (`json.dumps(..., sort_keys=True,
ensure_ascii=True, separators=(",", ":"), allow_nan=False)`) -- rather
than inventing a second wire-encoding style for this new, security-
sensitive contract.

Reuses, never duplicates: `research.GuestAgentProtocolSerialization
.guest_agent_request_document`/`guest_agent_request_from_document` for
the envelope's inner `GuestAgentRequest`, and
`research.GuestAgentDispatchProof.guest_agent_dispatch_proof_metadata_document`
for the proof's signable metadata. This module adds only what did not
already exist: the reverse (bytes/document -> typed value) direction
for the proof metadata, the proof, and the envelope itself.

Decoding fails closed exactly like its precedent: an unknown top-level
key, a missing required key, an unrecognized proof version, or a
malformed timestamp all raise `core.Exceptions.ResearchError` before
any cryptographic verification is ever attempted. Every envelope-level,
proof-level, and metadata-level key set here is closed -- no optional
keys exist at any of the three levels, unlike the sibling plain-request/
response contract, because every field of a signed dispatch envelope is
required by construction (see `research.GuestAgentDispatchProof`).

This module is pure data-shape plumbing: no cryptographic verification,
no replay consumption, no admission decision, and no network or process
of any kind. SIGNED ENVELOPE DECODED != VERIFIED. SIGNED ENVELOPE
DECODED != ADMITTED. Composing this with
`research.GuestAgentDispatchVerification.verify_signed_dispatch_envelope`
is a caller's job, never this module's.
"""

from __future__ import annotations

import json
from datetime import datetime

from core.Exceptions import ResearchError
from research.GuestAgentDispatchProof import (
    GuestAgentDispatchAuthorizationProof,
    GuestAgentDispatchProofMetadata,
    GuestAgentDispatchProofVersion,
    GuestAgentSignedDispatchEnvelope,
    guest_agent_dispatch_proof_metadata_document,
)
from research.GuestAgentProtocolSerialization import (
    guest_agent_request_document,
    guest_agent_request_from_document,
)

_ENVELOPE_REQUIRED_KEYS = frozenset({"request", "proof"})
_PROOF_REQUIRED_KEYS = frozenset({"metadata", "signature_hex"})
_METADATA_REQUIRED_KEYS = frozenset(
    {
        "proof_version",
        "request_sha256",
        "issuer_identity",
        "audience_identity",
        "issued_at",
        "expires_at",
    }
)


def guest_agent_signed_dispatch_envelope_document(
    envelope: GuestAgentSignedDispatchEnvelope,
) -> dict[str, object]:
    """Render one signed dispatch envelope as a plain, JSON-safe document."""
    if not isinstance(envelope, GuestAgentSignedDispatchEnvelope):
        raise ResearchError("Guest-agent signed dispatch envelope is invalid.")
    return {
        "request": guest_agent_request_document(envelope.request),
        "proof": _proof_document(envelope.proof),
    }


def canonical_guest_agent_signed_dispatch_envelope_bytes(
    envelope: GuestAgentSignedDispatchEnvelope,
) -> bytes:
    """Encode one signed dispatch envelope as canonical, deterministic JSON bytes."""
    return _canonical_bytes(guest_agent_signed_dispatch_envelope_document(envelope))


def guest_agent_signed_dispatch_envelope_from_document(
    document: object,
) -> GuestAgentSignedDispatchEnvelope:
    """Parse one signed dispatch envelope from an already-decoded document.

    Fails closed on anything unknown, missing, or malformed -- at the
    envelope, proof, or metadata level -- before returning. Never performs
    cryptographic verification; see the module docstring.
    """
    fields = _require_object_with_keys(
        document,
        _ENVELOPE_REQUIRED_KEYS,
        _ENVELOPE_REQUIRED_KEYS,
        "signed dispatch envelope",
    )
    request = guest_agent_request_from_document(fields["request"])
    proof = _proof_from_document(fields["proof"])
    return GuestAgentSignedDispatchEnvelope(request=request, proof=proof)


def guest_agent_signed_dispatch_envelope_from_bytes(
    data: bytes,
) -> GuestAgentSignedDispatchEnvelope:
    """Parse one signed dispatch envelope from canonical JSON bytes.

    Fails closed on anything that is not exactly this contract.
    """
    return guest_agent_signed_dispatch_envelope_from_document(_parse_json(data))


def _proof_document(
    proof: GuestAgentDispatchAuthorizationProof,
) -> dict[str, object]:
    if not isinstance(proof, GuestAgentDispatchAuthorizationProof):
        raise ResearchError("Guest-agent dispatch proof is invalid.")
    return {
        "metadata": guest_agent_dispatch_proof_metadata_document(proof.metadata),
        "signature_hex": proof.signature_hex,
    }


def _proof_from_document(document: object) -> GuestAgentDispatchAuthorizationProof:
    fields = _require_object_with_keys(
        document, _PROOF_REQUIRED_KEYS, _PROOF_REQUIRED_KEYS, "dispatch proof"
    )
    metadata = _metadata_from_document(fields["metadata"])
    signature_hex = _require_str(fields["signature_hex"], "signature")
    return GuestAgentDispatchAuthorizationProof(
        metadata=metadata, signature_hex=signature_hex
    )


def _metadata_from_document(document: object) -> GuestAgentDispatchProofMetadata:
    fields = _require_object_with_keys(
        document,
        _METADATA_REQUIRED_KEYS,
        _METADATA_REQUIRED_KEYS,
        "dispatch proof metadata",
    )
    return GuestAgentDispatchProofMetadata(
        proof_version=_parse_proof_version(fields["proof_version"], "proof version"),
        request_sha256=_require_str(fields["request_sha256"], "request digest"),
        issuer_identity=_require_str(fields["issuer_identity"], "issuer identity"),
        audience_identity=_require_str(
            fields["audience_identity"], "audience identity"
        ),
        issued_at=_parse_timestamp(fields["issued_at"], "issued-at time"),
        expires_at=_parse_timestamp(fields["expires_at"], "expires-at time"),
    )


def _canonical_bytes(document: dict[str, object]) -> bytes:
    return json.dumps(
        document,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _parse_json(data: bytes) -> object:
    if not isinstance(data, bytes):
        raise ResearchError("Guest-agent signed dispatch bytes must be bytes.")
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ResearchError(
            "Guest-agent signed dispatch bytes are not valid JSON."
        ) from error


def _require_object_with_keys(
    document: object,
    required_keys: frozenset[str],
    allowed_keys: frozenset[str],
    label: str,
) -> dict[str, object]:
    if not isinstance(document, dict):
        raise ResearchError(f"Guest-agent {label} document must be an object.")
    present = set(document.keys())
    # Deliberately a fixed sentence, never one built from the untrusted key
    # names themselves -- same discipline as
    # `GuestAgentProtocolSerialization._require_object_with_keys`.
    if present - allowed_keys:
        raise ResearchError(f"Guest-agent {label} document has unknown field(s).")
    if required_keys - present:
        raise ResearchError(f"Guest-agent {label} document is missing field(s).")
    return document


def _require_str(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ResearchError(f"Guest-agent signed dispatch {label} must be text.")
    return value


def _parse_proof_version(value: object, label: str) -> GuestAgentDispatchProofVersion:
    if not isinstance(value, str):
        raise ResearchError(f"Guest-agent signed dispatch {label} must be text.")
    try:
        return GuestAgentDispatchProofVersion(value)
    except ValueError as error:
        raise ResearchError(
            f"Guest-agent signed dispatch {label} is not recognized."
        ) from error


def _parse_timestamp(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise ResearchError(f"Guest-agent signed dispatch {label} is invalid.")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ResearchError(
            f"Guest-agent signed dispatch {label} is invalid."
        ) from error
    if parsed.utcoffset() is None:
        raise ResearchError(
            f"Guest-agent signed dispatch {label} must be timezone-aware."
        )
    return parsed


__all__ = [
    "canonical_guest_agent_signed_dispatch_envelope_bytes",
    "guest_agent_signed_dispatch_envelope_document",
    "guest_agent_signed_dispatch_envelope_from_bytes",
    "guest_agent_signed_dispatch_envelope_from_document",
]
