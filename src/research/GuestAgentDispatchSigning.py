"""HOST-side signing of exactly one dispatch-authorization proof per grant.

DISPATCH SIGNING KEY != GENERAL SIGNING ORACLE. The one production entry
point here, `create_signed_dispatch_envelope`, does not accept an
arbitrary `research.GuestAgentProtocol.GuestAgentRequest`, and there is no
lower-level function anywhere in this module that signs caller-supplied
bytes on request. It accepts only an already-successfully-consumed,
one-shot `research.GuestAgentHostAuthorizationHandoff.GuestAgentHostDispatchGrant`
-- a caller holding signing access cannot bypass that grant's binding to
the exact human-authorized preview, because `operation_kind`,
`operation_digest`, and `logical_inputs` are never parameters of this
function at all; they come only from the grant's own already-validated
facts, exactly as that module's own docstring requires.

Signing materializes the grant's one `GuestAgentRequest`
(`grant.materialize_request`, which is itself one-shot and lock-guarded),
hashes it with the existing canonical request encoder
(`research.GuestAgentProtocolSerialization.canonical_guest_agent_request_bytes`),
builds the fixed-shape, fixed-issuer/audience, bounded-validity proof
metadata (`research.GuestAgentDispatchProof.GuestAgentDispatchProofMetadata`),
and signs that metadata's own canonical bytes with a real Ed25519 private
key (`cryptography.hazmat.primitives.asymmetric.ed25519.Ed25519PrivateKey`
-- no home-grown elliptic-curve arithmetic, no HMAC/shared-secret scheme,
no OpenSSL CLI subprocess; the `cryptography` package calls directly into
its own compiled backend in-process). One grant yields at most one signed
envelope: materializing the grant is itself the one-shot consumption
event, guarded by the grant's own lock, so two concurrent signing
attempts against the same grant can never both succeed.

TLS IDENTITY KEY != DISPATCH AUTHORIZATION SIGNING KEY. This module never
imports `research.GuestAgentMtlsContext` or
`research.GuestAgentMtlsTrustConfiguration`'s private-key-path field, and
never derives, reads, or reuses the mTLS identity key in any way: the
`signing_key` parameter is always a separately-provisioned
`Ed25519PrivateKey`, a completely different security domain. This
milestone does not provision a production signing key at all -- callers
must supply an already-loaded key (in tests, an ephemeral one generated
and discarded within the test); safe production key-at-rest custody
remains explicitly unsolved and out of scope here, not pretended to be
solved.

Replay consumption (`research.GuestAgentReplayProtector.consume_once`) is
never called here: HOST AUTHORIZATION CONSUMED != GUEST REPLAY CONSUMED,
and this milestone establishes cryptographic authenticity/binding only.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.Exceptions import ResearchError
from research.GuestAgentDispatchProof import (
    DISPATCH_PROOF_GUEST_AUDIENCE_IDENTITY,
    DISPATCH_PROOF_HOST_ISSUER_IDENTITY,
    MAX_DISPATCH_PROOF_VALIDITY_SECONDS,
    GuestAgentDispatchAuthorizationProof,
    GuestAgentDispatchProofMetadata,
    GuestAgentDispatchProofVersion,
    GuestAgentSignedDispatchEnvelope,
    canonical_guest_agent_dispatch_proof_metadata_bytes,
)
from research.GuestAgentHostAuthorizationHandoff import GuestAgentHostDispatchGrant
from research.GuestAgentProtocolSerialization import (
    canonical_guest_agent_request_bytes,
)


class GuestAgentDispatchSigningStage(StrEnum):
    """Name which bounded signing step failed; never a trust claim."""

    REQUEST = "request"
    GRANT_MATERIALIZATION = "grant_materialization"
    SIGNING = "signing"


@dataclass(frozen=True, slots=True)
class GuestAgentDispatchSigningFailure:
    """Stage-owned facts; never a key, signature, or request-content leak."""

    stage: GuestAgentDispatchSigningStage
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.stage, GuestAgentDispatchSigningStage):
            raise ResearchError(
                "Guest-agent dispatch signing failure stage is invalid."
            )
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ResearchError(
                "Guest-agent dispatch signing failure reason is invalid."
            )


class GuestAgentDispatchSigningError(ResearchError):
    """Carry descriptive failure facts back to the caller; never an envelope."""

    def __init__(self, failure: GuestAgentDispatchSigningFailure) -> None:
        super().__init__(failure.reason)
        self.failure = failure


def create_signed_dispatch_envelope(
    grant: GuestAgentHostDispatchGrant,
    *,
    request_id: str,
    nonce: str,
    signing_key: Ed25519PrivateKey,
    now: datetime,
) -> GuestAgentSignedDispatchEnvelope:
    """Materialize `grant`'s one request and sign exactly one dispatch proof.

    `grant` must be a real, not-yet-materialized
    `GuestAgentHostDispatchGrant` -- there is no parameter here through
    which a caller could supply `operation_kind`, `operation_digest`,
    `logical_inputs`, `hostname`, `dns_record_type`, or
    `resolved_address` directly; all of those come only from the grant's
    own already-validated facts. `request_id`/`nonce` are supplied here
    because they are transport/replay identity, not authorization facts
    (REQUEST ID != AUTHORIZATION, NONCE != AUTHORIZATION), and are
    validated only by `GuestAgentRequest`'s own existing bounds.
    `issued_at`/`expires_at` are never caller-choosable: `issued_at` is
    exactly `now`, and `expires_at` is always `now` plus the fixed
    `MAX_DISPATCH_PROOF_VALIDITY_SECONDS` ceiling.

    Raises `GuestAgentDispatchSigningError` -- and leaves the grant
    unconsumed -- when `grant`/`signing_key`/`now` are not the expected
    types. Once `grant.materialize_request` succeeds, the grant is
    already one-shot-consumed regardless of what happens next; a
    subsequent signing failure (not expected in ordinary operation with a
    well-formed `Ed25519PrivateKey`) still yields no envelope, but the
    grant cannot be used again either way -- it was never safe to treat a
    materialized request as reusable.
    """
    stage = GuestAgentDispatchSigningStage.REQUEST
    try:
        if not isinstance(grant, GuestAgentHostDispatchGrant):
            raise ResearchError(
                "Guest-agent dispatch signing requires a real host dispatch grant."
            )
        if not isinstance(signing_key, Ed25519PrivateKey):
            raise ResearchError(
                "Guest-agent dispatch signing requires a real Ed25519 private key."
            )
        if not isinstance(now, datetime) or now.utcoffset() is None:
            raise ResearchError(
                "Guest-agent dispatch signing requires a timezone-aware current time."
            )

        stage = GuestAgentDispatchSigningStage.GRANT_MATERIALIZATION
        request = grant.materialize_request(request_id=request_id, nonce=nonce)

        stage = GuestAgentDispatchSigningStage.SIGNING
        request_sha256 = hashlib.sha256(
            canonical_guest_agent_request_bytes(request)
        ).hexdigest()
        metadata = GuestAgentDispatchProofMetadata(
            proof_version=GuestAgentDispatchProofVersion.V1,
            request_sha256=request_sha256,
            issuer_identity=DISPATCH_PROOF_HOST_ISSUER_IDENTITY,
            audience_identity=DISPATCH_PROOF_GUEST_AUDIENCE_IDENTITY,
            issued_at=now,
            expires_at=now + timedelta(seconds=MAX_DISPATCH_PROOF_VALIDITY_SECONDS),
        )
        signature = signing_key.sign(
            canonical_guest_agent_dispatch_proof_metadata_bytes(metadata)
        )
        proof = GuestAgentDispatchAuthorizationProof(
            metadata=metadata, signature_hex=signature.hex()
        )
    except ResearchError as error:
        if stage is GuestAgentDispatchSigningStage.SIGNING:
            reason = "Dispatch proof signing could not be completed."
        else:
            reason = str(error)
        raise GuestAgentDispatchSigningError(
            GuestAgentDispatchSigningFailure(stage=stage, reason=reason)
        ) from error

    return GuestAgentSignedDispatchEnvelope(request=request, proof=proof)
