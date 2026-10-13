"""GUEST-side pure verification of one signed dispatch-authorization proof.

VERIFIED DISPATCH PROOF != EXECUTION AUTHORITY. VERIFIED DISPATCH PROOF !=
REPLAY ACCEPTANCE. VERIFIED DISPATCH PROOF != CAPABILITY ADMISSION.
VERIFIED DISPATCH PROOF != RUNTIME READINESS. A successful
`verify_signed_dispatch_envelope` call means only "the trusted HOST
dispatch-signing key validly signed this exact request and proof
metadata" -- nothing about whether the carried `GuestAgentRequest` may
execute, whether its replay identity has been (or may be) consumed,
whether its logical inputs are admissible, or whether any runtime is
ready. This module spawns no process, opens no socket, performs no
DNS/HTTP, and calls neither
`research.GuestAgentReplayProtector.consume_once` nor
`research.GuestAgentCore.admit_guest_agent_request` -- composing this
verification with those later, in the correct order (verify -> admit ->
replay-consume -> ... -> dispatch), is explicitly future, separately-
authorized work.

The verifier never loads, needs, or references the HOST's private
dispatch-signing key -- it is handed only a public
`cryptography.hazmat.primitives.asymmetric.ed25519.Ed25519PublicKey`
(real asymmetric verification, never a shared secret: a GUEST that could
forge a valid proof would defeat the entire point of proving HOST
authorization). It also never imports
`research.GuestAgentMtlsContext`/`GuestAgentMtlsTrustConfiguration`'s
private-key-path field: TLS IDENTITY KEY != DISPATCH AUTHORIZATION
SIGNING KEY remains true on this side too.

Verification independently recomputes everything it can rather than
trusting the envelope's own pairing: the exact SHA-256 of the carried
request's own canonical bytes (reusing
`research.GuestAgentProtocolSerialization.canonical_guest_agent_request_bytes`,
never a second canonicalizer) must exactly equal the signed
`request_sha256`; the signed `issuer_identity`/`audience_identity` must
exactly equal the two fixed constants (no prefix, substring, or
case-folding); the current time must fall inside the signed, bounded
`[issued_at, expires_at)` window; and only then is the real Ed25519
signature checked against the trusted verification key. Any failure --
including a merely cosmetically-different metadata field whose change
alone wouldn't trip an earlier check -- still invalidates the signature,
because every signed field is covered by the canonical bytes that were
actually signed.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from core.Exceptions import ResearchError
from research.GuestAgentDispatchProof import (
    DISPATCH_PROOF_GUEST_AUDIENCE_IDENTITY,
    DISPATCH_PROOF_HOST_ISSUER_IDENTITY,
    GuestAgentDispatchProofVersion,
    GuestAgentSignedDispatchEnvelope,
    canonical_guest_agent_dispatch_proof_metadata_bytes,
)
from research.GuestAgentProtocol import GuestAgentRequest
from research.GuestAgentProtocolSerialization import (
    canonical_guest_agent_request_bytes,
)

#: Module-private capability token. Never exported, never re-derivable
#: from public data: the only code path that can supply this exact
#: object to `GuestAgentVerifiedDispatch.__init__` is
#: `verify_signed_dispatch_envelope`, below, after every cryptographic
#: and binding check has already succeeded. Mirrors
#: `research.GuestAgentPeerAuthenticator`'s own `_AUTHENTICATION_CAPABILITY`
#: pattern exactly.
_VERIFIED_DISPATCH_CAPABILITY = object()


class GuestAgentDispatchVerificationStage(StrEnum):
    """Name which bounded verification step failed; never a trust claim."""

    SHAPE = "shape"
    PROOF_VERSION = "proof_version"
    REQUEST_DIGEST = "request_digest"
    ISSUER = "issuer"
    AUDIENCE = "audience"
    VALIDITY_WINDOW = "validity_window"
    SIGNATURE = "signature"


_REASON_BY_STAGE: dict[GuestAgentDispatchVerificationStage, str] = {
    GuestAgentDispatchVerificationStage.SHAPE: (
        "Guest-agent dispatch envelope shape is invalid."
    ),
    GuestAgentDispatchVerificationStage.PROOF_VERSION: (
        "Guest-agent dispatch proof version is not supported."
    ),
    GuestAgentDispatchVerificationStage.REQUEST_DIGEST: (
        "Guest-agent dispatch proof request digest does not match."
    ),
    GuestAgentDispatchVerificationStage.ISSUER: (
        "Guest-agent dispatch proof issuer is not the trusted host identity."
    ),
    GuestAgentDispatchVerificationStage.AUDIENCE: (
        "Guest-agent dispatch proof audience is not the expected guest identity."
    ),
    GuestAgentDispatchVerificationStage.VALIDITY_WINDOW: (
        "Guest-agent dispatch proof is not currently within its validity window."
    ),
    GuestAgentDispatchVerificationStage.SIGNATURE: (
        "Guest-agent dispatch proof signature is invalid."
    ),
}


@dataclass(frozen=True, slots=True)
class GuestAgentDispatchVerificationFailure:
    """Stage-owned facts; never a key, signature, or request-content leak."""

    stage: GuestAgentDispatchVerificationStage
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.stage, GuestAgentDispatchVerificationStage):
            raise ResearchError(
                "Guest-agent dispatch verification failure stage is invalid."
            )
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ResearchError(
                "Guest-agent dispatch verification failure reason is invalid."
            )


class GuestAgentDispatchVerificationError(ResearchError):
    """Carry descriptive failure facts back to the caller; never a verified value."""

    def __init__(self, failure: GuestAgentDispatchVerificationFailure) -> None:
        super().__init__(failure.reason)
        self.failure = failure


@dataclass(frozen=True, slots=True, kw_only=True)
class GuestAgentVerifiedDispatch:
    """The trusted HOST dispatch-signing key validly signed this exact request.

    VERIFIED DISPATCH PROOF != EXECUTION AUTHORITY -- see the module
    docstring. Not publicly constructible: `__post_init__` rejects any
    `_capability_token` other than this module's own private sentinel,
    which only `verify_signed_dispatch_envelope` ever supplies, and only
    after every cryptographic and binding check has already succeeded. A
    caller cannot forge one merely by copying a `GuestAgentRequest` into
    this dataclass.
    """

    request: GuestAgentRequest
    _capability_token: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._capability_token is not _VERIFIED_DISPATCH_CAPABILITY:
            raise ResearchError(
                "Guest-agent verified dispatch may only be constructed by "
                "research.GuestAgentDispatchVerification"
                ".verify_signed_dispatch_envelope."
            )
        if not isinstance(self.request, GuestAgentRequest):
            raise ResearchError("Guest-agent verified dispatch request is invalid.")


def verify_signed_dispatch_envelope(
    envelope: GuestAgentSignedDispatchEnvelope,
    *,
    verification_key: Ed25519PublicKey,
    now: datetime,
) -> GuestAgentVerifiedDispatch:
    """Independently verify every binding fact and the real Ed25519 signature.

    Checks, in order, each one fully independent of trusting the
    envelope's own pairing: shape -> proof version -> exact request
    digest match (recomputed from `envelope.request` itself, never
    trusted from the signed metadata alone) -> exact issuer match ->
    exact audience match -> current time inside the signed validity
    window -> real Ed25519 signature verification against
    `verification_key`. Raises `GuestAgentDispatchVerificationError` on
    the first failure, naming only which bounded stage failed -- never
    the raw request contents, hostname, resolved address, DNS record
    type, nonce, operation digest, signature bytes, or any
    verification-key material.
    """
    stage = GuestAgentDispatchVerificationStage.SHAPE
    try:
        if not isinstance(envelope, GuestAgentSignedDispatchEnvelope):
            raise ResearchError("Guest-agent signed dispatch envelope is invalid.")
        if not isinstance(verification_key, Ed25519PublicKey):
            raise ResearchError(
                "Guest-agent dispatch verification requires a real Ed25519 "
                "public key."
            )
        if not isinstance(now, datetime) or now.utcoffset() is None:
            raise ResearchError(
                "Guest-agent dispatch verification requires a timezone-aware "
                "current time."
            )

        metadata = envelope.proof.metadata

        stage = GuestAgentDispatchVerificationStage.PROOF_VERSION
        if metadata.proof_version is not GuestAgentDispatchProofVersion.V1:
            raise ResearchError(_REASON_BY_STAGE[stage])

        stage = GuestAgentDispatchVerificationStage.REQUEST_DIGEST
        recomputed_sha256 = hashlib.sha256(
            canonical_guest_agent_request_bytes(envelope.request)
        ).hexdigest()
        if recomputed_sha256 != metadata.request_sha256:
            raise ResearchError(_REASON_BY_STAGE[stage])

        stage = GuestAgentDispatchVerificationStage.ISSUER
        if metadata.issuer_identity != DISPATCH_PROOF_HOST_ISSUER_IDENTITY:
            raise ResearchError(_REASON_BY_STAGE[stage])

        stage = GuestAgentDispatchVerificationStage.AUDIENCE
        if metadata.audience_identity != DISPATCH_PROOF_GUEST_AUDIENCE_IDENTITY:
            raise ResearchError(_REASON_BY_STAGE[stage])

        stage = GuestAgentDispatchVerificationStage.VALIDITY_WINDOW
        if now < metadata.issued_at or now >= metadata.expires_at:
            raise ResearchError(_REASON_BY_STAGE[stage])

        stage = GuestAgentDispatchVerificationStage.SIGNATURE
        signature_bytes = bytes.fromhex(envelope.proof.signature_hex)
        try:
            verification_key.verify(
                signature_bytes,
                canonical_guest_agent_dispatch_proof_metadata_bytes(metadata),
            )
        except InvalidSignature as error:
            raise ResearchError(_REASON_BY_STAGE[stage]) from error
    except ResearchError as error:
        reason = _REASON_BY_STAGE.get(stage, str(error))
        raise GuestAgentDispatchVerificationError(
            GuestAgentDispatchVerificationFailure(stage=stage, reason=reason)
        ) from error

    return GuestAgentVerifiedDispatch(
        request=envelope.request, _capability_token=_VERIFIED_DISPATCH_CAPABILITY
    )
