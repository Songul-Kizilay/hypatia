"""The typed, signable dispatch-authorization proof contract.

Closes the gap `research.GuestAgentHostAuthorizationHandoff`'s own module
docstring named honestly: a plain serialized `GuestAgentRequest` cannot by
itself prove that host authorization was consumed. This module defines the
SHAPE of a separate cryptographic proof that can -- `GuestAgentDispatchProofMetadata`
(the facts an Ed25519 signature will cover),
`GuestAgentDispatchAuthorizationProof` (those facts plus the signature),
and `GuestAgentSignedDispatchEnvelope` (one typed request paired with one
proof). Nothing here signs or verifies anything -- that is
`research.GuestAgentDispatchSigning`/`GuestAgentDispatchVerification`'s job
-- and nothing here imports the `cryptography` library at all. This module
is pure data: construction, canonicalization, and validation only.

`GuestAgentRequest` itself is never modified and never gains a signature
field: TYPED REQUEST PROTOCOL != AUTHORIZATION PROOF LAYER. Bumping
`research.GuestAgentProtocol.GuestAgentProtocolVersion` to add this proof
would conflate two separate facts -- what the wire message contract is,
and whether a host authorization was cryptographically proven -- so this
module defines its own separate `GuestAgentDispatchProofVersion` instead.

The proof payload carries only the minimum facts needed to bind authority
to one exact request and one expected destination: `proof_version`,
`request_sha256`, `issuer_identity`, `audience_identity`, `issued_at`,
`expires_at`. It never carries arbitrary host commentary, raw
authorization-store contents, scope documents, human names, secrets, or
private-key material -- there is no field here that could hold any of
those, by construction.

`issuer_identity`/`audience_identity` reuse the existing Guest-Agent peer
identity STRING vocabulary (`research.GuestAgentMtlsTrustConfiguration
.GuestAgentPeerIdentity.for_role`) -- the same fixed
`"hypatia-kali-guest-agent/host/1"`/`"hypatia-kali-guest-agent/guest/1"`
strings that already name the two mTLS roles -- but never the KEY
material behind them: TLS IDENTITY KEY != DISPATCH AUTHORIZATION SIGNING
KEY. This module imports only the peer-identity string constants from
that module, never `GuestAgentMtlsContext`, never
`GuestAgentMtlsTrustConfiguration`'s own private-key-path field, and
never anything that could sign or verify TLS traffic. Matching values are
always exact equality -- no prefix, substring, or case-folding.

`request_sha256` is always `SHA-256(canonical_guest_agent_request_bytes(request))`,
reusing `research.GuestAgentProtocolSerialization`'s existing canonicalizer
rather than inventing a second one -- so the hash is bound to every field
that canonicalizer already covers (`protocol_version`, `request_id`,
`nonce`, `operation_kind`, `operation_digest`, `logical_inputs`); changing
any one of them changes the hash.

Validity is short and code-owned (`MAX_DISPATCH_PROOF_VALIDITY_SECONDS`),
never caller-choosable -- enforced structurally here (the gap between
`issued_at` and `expires_at` can never exceed the fixed ceiling, mirroring
`research.ResearchKaliOperationAuthorization._validate_window`'s own
pattern exactly) and independently re-checked against the current time by
the verifier.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final

from core.Exceptions import ResearchError
from research.GuestAgentMtlsTrustConfiguration import (
    GuestAgentPeerIdentity,
    GuestAgentPeerRole,
)
from research.GuestAgentProtocol import GuestAgentRequest

#: Short and conservative on purpose: this proof is signed and verified
#: entirely in-process, with no network latency to accommodate (nothing
#: in this milestone sends it anywhere) -- repository audit found no
#: finer-grained existing convention for a proof this short-lived, so
#: this is a new, explicit, code-owned ceiling, not an inherited one.
MAX_DISPATCH_PROOF_VALIDITY_SECONDS: Final[int] = 60

#: A real Ed25519 signature is always exactly 64 bytes == 128 lowercase
#: hex characters. One strict encoding only -- never base64, never
#: uppercase, never a variable length.
DISPATCH_PROOF_SIGNATURE_HEX_LENGTH: Final[int] = 128

#: Fixed, code-owned application identities -- never caller-suppliable.
#: Reuses the existing Guest-Agent peer identity STRING vocabulary only;
#: the mTLS KEY material behind these identities is never referenced
#: here. TLS IDENTITY KEY != DISPATCH AUTHORIZATION SIGNING KEY.
DISPATCH_PROOF_HOST_ISSUER_IDENTITY: Final[str] = GuestAgentPeerIdentity.for_role(
    GuestAgentPeerRole.HOST
).uri
DISPATCH_PROOF_GUEST_AUDIENCE_IDENTITY: Final[str] = GuestAgentPeerIdentity.for_role(
    GuestAgentPeerRole.GUEST
).uri

_REQUEST_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_SIGNATURE_HEX_PATTERN = re.compile(r"^[0-9a-f]{128}$")


class GuestAgentDispatchProofVersion(StrEnum):
    """Name one closed, code-owned dispatch-proof generation.

    Deliberately separate from `GuestAgentProtocolVersion`: the wire
    protocol contract and the cryptographic authorization-proof contract
    are two different facts that happen to version independently. Exactly
    one member today, exactly like that sibling enum's own docstring
    explains for itself -- anything that is not `V1`, including a string
    that merely looks like a future version, must fail closed, never
    silently downgrade.
    """

    V1 = "hypatia-kali-guest-agent/dispatch-proof/1"


@dataclass(frozen=True, slots=True)
class GuestAgentDispatchProofMetadata:
    """The exact facts one Ed25519 signature will cover; signs nothing itself.

    Every field is validated; `issuer_identity`/`audience_identity` must
    exactly equal the two fixed constants above (no caller-chosen
    identity reaches this type honestly), and the validity window is
    structurally bounded to `MAX_DISPATCH_PROOF_VALIDITY_SECONDS` --
    defense in depth, since the one production caller
    (`research.GuestAgentDispatchSigning.create_signed_dispatch_envelope`)
    already derives `expires_at` from `issued_at` using that exact fixed
    duration and never accepts a caller-chosen expiry.
    """

    proof_version: GuestAgentDispatchProofVersion
    request_sha256: str
    issuer_identity: str
    audience_identity: str
    issued_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.proof_version, GuestAgentDispatchProofVersion):
            raise ResearchError("Guest-agent dispatch proof version is invalid.")
        if not isinstance(
            self.request_sha256, str
        ) or not _REQUEST_SHA256_PATTERN.fullmatch(self.request_sha256):
            raise ResearchError("Guest-agent dispatch proof request digest is invalid.")
        if self.issuer_identity != DISPATCH_PROOF_HOST_ISSUER_IDENTITY:
            raise ResearchError("Guest-agent dispatch proof issuer is invalid.")
        if self.audience_identity != DISPATCH_PROOF_GUEST_AUDIENCE_IDENTITY:
            raise ResearchError("Guest-agent dispatch proof audience is invalid.")
        for value, label in (
            (self.issued_at, "issued-at time"),
            (self.expires_at, "expires-at time"),
        ):
            if not isinstance(value, datetime) or value.utcoffset() is None:
                raise ResearchError(
                    f"Guest-agent dispatch proof {label} must be timezone-aware."
                )
        if self.expires_at <= self.issued_at:
            raise ResearchError(
                "Guest-agent dispatch proof must expire after it was issued."
            )
        if (
            self.expires_at - self.issued_at
        ).total_seconds() > MAX_DISPATCH_PROOF_VALIDITY_SECONDS:
            raise ResearchError(
                "Guest-agent dispatch proof validity exceeds its hard ceiling."
            )


def guest_agent_dispatch_proof_metadata_document(
    metadata: GuestAgentDispatchProofMetadata,
) -> dict[str, object]:
    """Render the signable metadata as a plain, JSON-safe document."""
    if not isinstance(metadata, GuestAgentDispatchProofMetadata):
        raise ResearchError("Guest-agent dispatch proof metadata is invalid.")
    return {
        "proof_version": metadata.proof_version.value,
        "request_sha256": metadata.request_sha256,
        "issuer_identity": metadata.issuer_identity,
        "audience_identity": metadata.audience_identity,
        "issued_at": metadata.issued_at.isoformat(),
        "expires_at": metadata.expires_at.isoformat(),
    }


def canonical_guest_agent_dispatch_proof_metadata_bytes(
    metadata: GuestAgentDispatchProofMetadata,
) -> bytes:
    """Encode the signable metadata deterministically -- what actually gets signed.

    Reuses this repository's one existing canonical-JSON convention
    (`sort_keys=True, ensure_ascii=True, separators=(",", ":"),
    allow_nan=False`, the same arguments
    `research.ResearchKaliOperationPreview.canonical_kali_operation_preview_bytes`
    and `research.GuestAgentProtocolSerialization`'s own encoder already
    use) rather than inventing a second canonicalization. Never `repr()`,
    never `pickle`, never YAML.
    """
    return json.dumps(
        guest_agent_dispatch_proof_metadata_document(metadata),
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class GuestAgentDispatchAuthorizationProof:
    """Signable metadata plus the one Ed25519 signature covering it.

    `signature_hex` is always exactly 128 lowercase hexadecimal
    characters (one real 64-byte Ed25519 signature, one strict encoding)
    -- never base64, never uppercase, never a different length. This type
    does not itself verify the signature; it only enforces the shape a
    real signature must have. Verification is
    `research.GuestAgentDispatchVerification.verify_signed_dispatch_envelope`'s
    job alone.
    """

    metadata: GuestAgentDispatchProofMetadata
    signature_hex: str

    def __post_init__(self) -> None:
        if not isinstance(self.metadata, GuestAgentDispatchProofMetadata):
            raise ResearchError("Guest-agent dispatch proof metadata is invalid.")
        if not isinstance(
            self.signature_hex, str
        ) or not _SIGNATURE_HEX_PATTERN.fullmatch(self.signature_hex):
            raise ResearchError("Guest-agent dispatch proof signature is invalid.")


@dataclass(frozen=True, slots=True)
class GuestAgentSignedDispatchEnvelope:
    """One typed `GuestAgentRequest` paired with one dispatch-authorization proof.

    `GuestAgentRequest` itself remains completely unmodified -- this is a
    separate outer value, never a new field smuggled onto the protocol
    type. Carrying both together is the only thing this type does; it
    performs no check of its own binding either field to the other --
    that recomputation is `verify_signed_dispatch_envelope`'s job, which
    never trusts this pairing merely because it exists.
    """

    request: GuestAgentRequest
    proof: GuestAgentDispatchAuthorizationProof

    def __post_init__(self) -> None:
        if not isinstance(self.request, GuestAgentRequest):
            raise ResearchError("Guest-agent signed dispatch request is invalid.")
        if not isinstance(self.proof, GuestAgentDispatchAuthorizationProof):
            raise ResearchError("Guest-agent signed dispatch proof is invalid.")
