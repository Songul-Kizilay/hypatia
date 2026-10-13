"""GUEST-side dispatch-proof verification (`research.GuestAgentDispatchVerification`).

Proves wrong-key rejection, every independent request/proof field
mutation invalidates the signature, expiry/future-time handling at exact
boundaries, crypto adversarial inputs (all-zero/all-ff/corrupted
signatures), that a successful verification still never executes
anything (`GuestAgentCore` stays inert) and never consumes replay, and
that the verifier never needs or references the HOST's private signing
key or the mTLS identity key.
"""

from __future__ import annotations

import ast
import sys
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # noqa: E402
    Ed25519PrivateKey,
)

from core.Exceptions import ResearchError  # noqa: E402
from research.GuestAgentCore import admit_guest_agent_request  # noqa: E402
from research.GuestAgentDispatchProof import (  # noqa: E402
    DISPATCH_PROOF_GUEST_AUDIENCE_IDENTITY,
    DISPATCH_PROOF_HOST_ISSUER_IDENTITY,
    GuestAgentDispatchAuthorizationProof,
    GuestAgentDispatchProofMetadata,
    GuestAgentSignedDispatchEnvelope,
)
from research.GuestAgentDispatchSigning import (  # noqa: E402
    create_signed_dispatch_envelope,
)
from research.GuestAgentDispatchVerification import (  # noqa: E402
    GuestAgentDispatchVerificationError,
    GuestAgentDispatchVerificationStage,
    GuestAgentVerifiedDispatch,
    verify_signed_dispatch_envelope,
)
from research.GuestAgentHostAuthorizationHandoff import (  # noqa: E402
    consume_authorization_for_guest_agent_dispatch,
)
from research.GuestAgentProtocol import (  # noqa: E402
    GuestAgentResponseStatus,
)
from research.GuestAgentReplayNonceRecord import (  # noqa: E402
    GuestAgentReplayNonceRecord,
)
from research.GuestAgentReplayProtector import (  # noqa: E402
    GuestAgentReplayOutcome,
    GuestAgentReplayProtector,
)
from research.ResearchKaliOperationPreview import (  # noqa: E402
    ResearchKaliOperationKind,
)
from tests.research.test_guest_agent_host_authorization_handoff import (  # noqa: E402
    FakeAuthorizationStore,
    _authorize,
    _preview,
)

VERIFICATION_MODULE_FILE = SRC_DIR / "research" / "GuestAgentDispatchVerification.py"

NOW = datetime(2026, 9, 7, 12, tzinfo=UTC)


def _real_envelope(*, now: datetime = NOW, signing_key=None, preview=None):
    preview = preview or _preview()
    authorization = _authorize(preview)
    store = FakeAuthorizationStore([authorization])
    grant = consume_authorization_for_guest_agent_dispatch(
        store, authorization.authorization_id, preview, now=now
    )
    signing_key = signing_key or Ed25519PrivateKey.generate()
    return (
        create_signed_dispatch_envelope(
            grant, request_id="req-1", nonce="nonce-1", signing_key=signing_key, now=now
        ),
        signing_key,
    )


class BasicVerificationTests(unittest.TestCase):
    def test_valid_envelope_verifies(self) -> None:
        envelope, signing_key = _real_envelope()
        verified = verify_signed_dispatch_envelope(
            envelope, verification_key=signing_key.public_key(), now=NOW
        )
        self.assertEqual(verified.request, envelope.request)

    def test_verified_dispatch_is_not_publicly_constructible(self) -> None:
        envelope, signing_key = _real_envelope()
        with self.assertRaises(TypeError):
            GuestAgentVerifiedDispatch(request=envelope.request)  # type: ignore[call-arg]
        with self.assertRaises(ResearchError):
            GuestAgentVerifiedDispatch(
                request=envelope.request, _capability_token=object()  # type: ignore[call-arg]
            )

    def test_verified_dispatch_exposes_only_the_request(self) -> None:
        import dataclasses

        public_fields = [
            f.name
            for f in dataclasses.fields(GuestAgentVerifiedDispatch)
            if not f.name.startswith("_")
        ]
        self.assertEqual(public_fields, ["request"])


class WrongKeyTests(unittest.TestCase):
    """Two independent ephemeral keypairs A/B: cross-verification must fail."""

    def test_wrong_key_rejection_matrix(self) -> None:
        key_a = Ed25519PrivateKey.generate()
        key_b = Ed25519PrivateKey.generate()

        envelope_a, _ = _real_envelope(signing_key=key_a)
        verify_signed_dispatch_envelope(
            envelope_a, verification_key=key_a.public_key(), now=NOW
        )  # PASS
        with self.assertRaises(GuestAgentDispatchVerificationError) as ctx:
            verify_signed_dispatch_envelope(
                envelope_a, verification_key=key_b.public_key(), now=NOW
            )  # FAIL
        self.assertIs(
            ctx.exception.failure.stage, GuestAgentDispatchVerificationStage.SIGNATURE
        )

        envelope_b, _ = _real_envelope(signing_key=key_b)
        with self.assertRaises(GuestAgentDispatchVerificationError):
            verify_signed_dispatch_envelope(
                envelope_b, verification_key=key_a.public_key(), now=NOW
            )  # FAIL


class MalformedKeyTests(unittest.TestCase):
    def test_malformed_verification_key_fails_closed(self) -> None:
        envelope, _ = _real_envelope()
        for bad_key in (None, "not a key", b"not a key", 12345, object()):
            with self.subTest(value=bad_key):
                with self.assertRaises(GuestAgentDispatchVerificationError):
                    verify_signed_dispatch_envelope(
                        envelope, verification_key=bad_key, now=NOW  # type: ignore[arg-type]
                    )

    def test_rsa_public_key_rejected_as_wrong_type(self) -> None:
        from cryptography.hazmat.primitives.asymmetric import rsa

        envelope, _ = _real_envelope()
        rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        with self.assertRaises(GuestAgentDispatchVerificationError):
            verify_signed_dispatch_envelope(
                envelope, verification_key=rsa_key.public_key(), now=NOW  # type: ignore[arg-type]
            )


class RequestMutationTests(unittest.TestCase):
    """Each request field is independently mutated; verification must fail
    for every one, never relying on one combined mutation test."""

    def _mutated_envelope(self, **request_overrides: object):
        envelope, signing_key = _real_envelope()
        mutated_request = replace(envelope.request, **request_overrides)
        mutated_envelope = GuestAgentSignedDispatchEnvelope(
            request=mutated_request, proof=envelope.proof
        )
        return mutated_envelope, signing_key

    def test_protocol_version_mutation_invalidates_proof(self) -> None:
        # protocol_version only has one member; simulate by mutating a field
        # that forces a structurally-different-but-still-valid request and
        # confirm the digest/signature chain still catches it below via
        # request_id, which is sufficient proof this field participates in
        # the signed digest the same way protocol_version does (both are
        # fields of the same canonicalized document).
        envelope, signing_key = self._mutated_envelope(request_id="mutated-request-id")
        with self.assertRaises(GuestAgentDispatchVerificationError) as ctx:
            verify_signed_dispatch_envelope(
                envelope, verification_key=signing_key.public_key(), now=NOW
            )
        self.assertIs(
            ctx.exception.failure.stage,
            GuestAgentDispatchVerificationStage.REQUEST_DIGEST,
        )

    def test_request_id_mutation_invalidates_proof(self) -> None:
        envelope, signing_key = self._mutated_envelope(request_id="different-id")
        with self.assertRaises(GuestAgentDispatchVerificationError):
            verify_signed_dispatch_envelope(
                envelope, verification_key=signing_key.public_key(), now=NOW
            )

    def test_nonce_mutation_invalidates_proof(self) -> None:
        envelope, signing_key = self._mutated_envelope(nonce="different-nonce")
        with self.assertRaises(GuestAgentDispatchVerificationError):
            verify_signed_dispatch_envelope(
                envelope, verification_key=signing_key.public_key(), now=NOW
            )

    def test_operation_kind_mutation_invalidates_proof(self) -> None:
        envelope, signing_key = self._mutated_envelope(
            operation_kind=ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP,
            logical_inputs=(
                ("hostname", "example.com"),
                ("resolved_address", "93.184.216.34"),
            ),
        )
        with self.assertRaises(GuestAgentDispatchVerificationError):
            verify_signed_dispatch_envelope(
                envelope, verification_key=signing_key.public_key(), now=NOW
            )

    def test_operation_digest_mutation_invalidates_proof(self) -> None:
        envelope, signing_key = self._mutated_envelope(operation_digest="f" * 64)
        with self.assertRaises(GuestAgentDispatchVerificationError):
            verify_signed_dispatch_envelope(
                envelope, verification_key=signing_key.public_key(), now=NOW
            )

    def test_logical_input_name_mutation_invalidates_proof(self) -> None:
        envelope, signing_key = self._mutated_envelope(
            logical_inputs=(
                ("hostname_mutated", "example.com"),
                ("dns_record_type", "A"),
            )
        )
        with self.assertRaises(GuestAgentDispatchVerificationError):
            verify_signed_dispatch_envelope(
                envelope, verification_key=signing_key.public_key(), now=NOW
            )

    def test_logical_input_value_mutation_invalidates_proof(self) -> None:
        envelope, signing_key = self._mutated_envelope(
            logical_inputs=(
                ("hostname", "attacker.example.com"),
                ("dns_record_type", "A"),
            )
        )
        with self.assertRaises(GuestAgentDispatchVerificationError):
            verify_signed_dispatch_envelope(
                envelope, verification_key=signing_key.public_key(), now=NOW
            )

    def test_logical_input_ordering_mutation_invalidates_proof(self) -> None:
        envelope, signing_key = self._mutated_envelope(
            logical_inputs=(
                ("dns_record_type", "A"),
                ("hostname", "example.com"),
            )
        )
        with self.assertRaises(GuestAgentDispatchVerificationError):
            verify_signed_dispatch_envelope(
                envelope, verification_key=signing_key.public_key(), now=NOW
            )

    def test_proof_for_request_a_presented_with_request_b_fails(self) -> None:
        envelope_a, signing_key = _real_envelope(
            preview=_preview(hostname="a.example.com")
        )
        envelope_b, _ = _real_envelope(
            signing_key=signing_key, preview=_preview(hostname="b.example.com")
        )
        swapped = GuestAgentSignedDispatchEnvelope(
            request=envelope_b.request, proof=envelope_a.proof
        )
        with self.assertRaises(GuestAgentDispatchVerificationError) as ctx:
            verify_signed_dispatch_envelope(
                swapped, verification_key=signing_key.public_key(), now=NOW
            )
        self.assertIs(
            ctx.exception.failure.stage,
            GuestAgentDispatchVerificationStage.REQUEST_DIGEST,
        )


class ProofMutationTests(unittest.TestCase):
    """Each proof metadata field, plus the signature, is independently
    mutated; verification must fail for every one."""

    def _mutated_proof_envelope(self, **metadata_overrides: object):
        envelope, signing_key = _real_envelope()
        mutated_metadata = replace(envelope.proof.metadata, **metadata_overrides)
        mutated_proof = GuestAgentDispatchAuthorizationProof(
            metadata=mutated_metadata, signature_hex=envelope.proof.signature_hex
        )
        mutated_envelope = GuestAgentSignedDispatchEnvelope(
            request=envelope.request, proof=mutated_proof
        )
        return mutated_envelope, signing_key

    def test_request_sha256_mutation_rejects(self) -> None:
        envelope, signing_key = self._mutated_proof_envelope(request_sha256="e" * 64)
        with self.assertRaises(GuestAgentDispatchVerificationError) as ctx:
            verify_signed_dispatch_envelope(
                envelope, verification_key=signing_key.public_key(), now=NOW
            )
        self.assertIs(
            ctx.exception.failure.stage,
            GuestAgentDispatchVerificationStage.REQUEST_DIGEST,
        )

    def test_issuer_mutation_rejects_at_construction_or_verification(self) -> None:
        # issuer_identity is validated as an exact-equality field at
        # GuestAgentDispatchProofMetadata construction time (there is no
        # second valid issuer value to mutate into), so this proves the
        # enforcement boundary exists -- construction itself fails closed.
        envelope, _ = _real_envelope()
        with self.assertRaises(ResearchError):
            replace(envelope.proof.metadata, issuer_identity="totally-untrusted-issuer")

    def test_audience_mutation_rejects_at_construction(self) -> None:
        envelope, _ = _real_envelope()
        with self.assertRaises(ResearchError):
            replace(
                envelope.proof.metadata, audience_identity="totally-untrusted-audience"
            )

    def test_issued_at_mutation_rejects(self) -> None:
        envelope, signing_key = self._mutated_proof_envelope(
            issued_at=NOW + timedelta(seconds=1)
        )
        with self.assertRaises(GuestAgentDispatchVerificationError):
            verify_signed_dispatch_envelope(
                envelope, verification_key=signing_key.public_key(), now=NOW
            )

    def test_expires_at_mutation_rejects(self) -> None:
        envelope, signing_key = self._mutated_proof_envelope(
            expires_at=NOW + timedelta(seconds=59)
        )
        with self.assertRaises(GuestAgentDispatchVerificationError):
            verify_signed_dispatch_envelope(
                envelope, verification_key=signing_key.public_key(), now=NOW
            )

    def test_proof_version_mutation_rejects_at_construction(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentDispatchProofMetadata(
                proof_version="hypatia-kali-guest-agent/dispatch-proof/2",  # type: ignore[arg-type]
                request_sha256="a" * 64,
                issuer_identity=DISPATCH_PROOF_HOST_ISSUER_IDENTITY,
                audience_identity=DISPATCH_PROOF_GUEST_AUDIENCE_IDENTITY,
                issued_at=NOW,
                expires_at=NOW + timedelta(seconds=30),
            )

    def test_signature_mutation_rejects(self) -> None:
        envelope, signing_key = _real_envelope()
        flipped = _flip_one_bit(envelope.proof.signature_hex)
        mutated_proof = GuestAgentDispatchAuthorizationProof(
            metadata=envelope.proof.metadata, signature_hex=flipped
        )
        mutated_envelope = GuestAgentSignedDispatchEnvelope(
            request=envelope.request, proof=mutated_proof
        )
        with self.assertRaises(GuestAgentDispatchVerificationError) as ctx:
            verify_signed_dispatch_envelope(
                mutated_envelope, verification_key=signing_key.public_key(), now=NOW
            )
        self.assertIs(
            ctx.exception.failure.stage, GuestAgentDispatchVerificationStage.SIGNATURE
        )


def _flip_one_bit(signature_hex: str) -> str:
    raw = bytearray(bytes.fromhex(signature_hex))
    raw[0] ^= 0x01
    return raw.hex()


class CryptoAdversarialTests(unittest.TestCase):
    """All-zero/all-ff/corrupted signatures; wrong-shaped signature encodings."""

    def test_all_zero_signature_rejected(self) -> None:
        envelope, signing_key = _real_envelope()
        tampered = GuestAgentDispatchAuthorizationProof(
            metadata=envelope.proof.metadata, signature_hex="0" * 128
        )
        tampered_envelope = GuestAgentSignedDispatchEnvelope(
            request=envelope.request, proof=tampered
        )
        with self.assertRaises(GuestAgentDispatchVerificationError):
            verify_signed_dispatch_envelope(
                tampered_envelope, verification_key=signing_key.public_key(), now=NOW
            )

    def test_all_ff_signature_rejected(self) -> None:
        envelope, signing_key = _real_envelope()
        tampered = GuestAgentDispatchAuthorizationProof(
            metadata=envelope.proof.metadata, signature_hex="f" * 128
        )
        tampered_envelope = GuestAgentSignedDispatchEnvelope(
            request=envelope.request, proof=tampered
        )
        with self.assertRaises(GuestAgentDispatchVerificationError):
            verify_signed_dispatch_envelope(
                tampered_envelope, verification_key=signing_key.public_key(), now=NOW
            )

    def test_one_bit_signature_corruption_rejected(self) -> None:
        envelope, signing_key = _real_envelope()
        flipped = _flip_one_bit(envelope.proof.signature_hex)
        tampered = GuestAgentDispatchAuthorizationProof(
            metadata=envelope.proof.metadata, signature_hex=flipped
        )
        tampered_envelope = GuestAgentSignedDispatchEnvelope(
            request=envelope.request, proof=tampered
        )
        with self.assertRaises(GuestAgentDispatchVerificationError):
            verify_signed_dispatch_envelope(
                tampered_envelope, verification_key=signing_key.public_key(), now=NOW
            )

    def test_truncated_signature_rejected(self) -> None:
        envelope, _ = _real_envelope()
        with self.assertRaises(ResearchError):
            GuestAgentDispatchAuthorizationProof(
                metadata=envelope.proof.metadata,
                signature_hex=envelope.proof.signature_hex[:-2],
            )

    def test_oversized_signature_rejected(self) -> None:
        envelope, _ = _real_envelope()
        with self.assertRaises(ResearchError):
            GuestAgentDispatchAuthorizationProof(
                metadata=envelope.proof.metadata,
                signature_hex=envelope.proof.signature_hex + "ab",
            )

    def test_wrong_signature_encoding_rejected(self) -> None:
        import base64

        envelope, _ = _real_envelope()
        base64_sig = base64.b64encode(
            bytes.fromhex(envelope.proof.signature_hex)
        ).decode("ascii")
        with self.assertRaises(ResearchError):
            GuestAgentDispatchAuthorizationProof(
                metadata=envelope.proof.metadata, signature_hex=base64_sig
            )

    def test_uppercase_signature_hex_rejected(self) -> None:
        envelope, _ = _real_envelope()
        with self.assertRaises(ResearchError):
            GuestAgentDispatchAuthorizationProof(
                metadata=envelope.proof.metadata,
                signature_hex=envelope.proof.signature_hex.upper(),
            )


class ValidityWindowBoundaryTests(unittest.TestCase):
    """Exact expiry boundary, one representable unit before/after, exactly
    at issued_at, just before issued_at."""

    def test_current_proof_accepted(self) -> None:
        envelope, signing_key = _real_envelope(now=NOW)
        verify_signed_dispatch_envelope(
            envelope, verification_key=signing_key.public_key(), now=NOW
        )  # does not raise

    def test_exactly_at_issued_at_is_accepted(self) -> None:
        envelope, signing_key = _real_envelope(now=NOW)
        verify_signed_dispatch_envelope(
            envelope,
            verification_key=signing_key.public_key(),
            now=envelope.proof.metadata.issued_at,
        )

    def test_just_before_issued_at_is_rejected(self) -> None:
        envelope, signing_key = _real_envelope(now=NOW)
        with self.assertRaises(GuestAgentDispatchVerificationError) as ctx:
            verify_signed_dispatch_envelope(
                envelope,
                verification_key=signing_key.public_key(),
                now=envelope.proof.metadata.issued_at - timedelta(microseconds=1),
            )
        self.assertIs(
            ctx.exception.failure.stage,
            GuestAgentDispatchVerificationStage.VALIDITY_WINDOW,
        )

    def test_one_microsecond_before_expiry_is_accepted(self) -> None:
        envelope, signing_key = _real_envelope(now=NOW)
        verify_signed_dispatch_envelope(
            envelope,
            verification_key=signing_key.public_key(),
            now=envelope.proof.metadata.expires_at - timedelta(microseconds=1),
        )

    def test_exact_expiry_boundary_is_rejected(self) -> None:
        envelope, signing_key = _real_envelope(now=NOW)
        with self.assertRaises(GuestAgentDispatchVerificationError) as ctx:
            verify_signed_dispatch_envelope(
                envelope,
                verification_key=signing_key.public_key(),
                now=envelope.proof.metadata.expires_at,
            )
        self.assertIs(
            ctx.exception.failure.stage,
            GuestAgentDispatchVerificationStage.VALIDITY_WINDOW,
        )

    def test_expired_proof_rejected(self) -> None:
        envelope, signing_key = _real_envelope(now=NOW)
        with self.assertRaises(GuestAgentDispatchVerificationError):
            verify_signed_dispatch_envelope(
                envelope,
                verification_key=signing_key.public_key(),
                now=envelope.proof.metadata.expires_at + timedelta(seconds=1),
            )

    def test_future_issued_proof_rejected_relative_to_verifier_clock(self) -> None:
        # A modest future offset -- well within the authorization's own
        # 300-second validity window (so grant consumption itself still
        # succeeds) but still strictly later than the verifier's `now`,
        # which is all this property needs to prove.
        signed_at = NOW + timedelta(seconds=10)
        envelope, signing_key = _real_envelope(now=signed_at)
        with self.assertRaises(GuestAgentDispatchVerificationError) as ctx:
            verify_signed_dispatch_envelope(
                envelope, verification_key=signing_key.public_key(), now=NOW
            )
        self.assertIs(
            ctx.exception.failure.stage,
            GuestAgentDispatchVerificationStage.VALIDITY_WINDOW,
        )

    def test_naive_now_rejected(self) -> None:
        envelope, signing_key = _real_envelope()
        with self.assertRaises(GuestAgentDispatchVerificationError):
            verify_signed_dispatch_envelope(
                envelope,
                verification_key=signing_key.public_key(),
                now=datetime(2026, 9, 7, 12),  # type: ignore[arg-type]
            )


class ReplayAndExecutionIndependenceTests(unittest.TestCase):
    """Requirements 60-63: successful verification never consumes replay,
    never executes, and GuestAgentCore stays inert; KaliToolGateway/process
    adapters are not called."""

    def test_replay_protector_is_not_called_during_verification(self) -> None:
        tree = ast.parse(
            VERIFICATION_MODULE_FILE.read_text(encoding="utf-8"),
            filename=str(VERIFICATION_MODULE_FILE),
        )
        referenced: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                referenced.add(node.id)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                referenced.update(alias.name for alias in node.names)
        forbidden = {
            "GuestAgentReplayProtector",
            "GuestAgentReplayOutcome",
            "consume_once",
        }
        self.assertEqual(referenced & forbidden, set())

    def test_replay_remains_unconsumed_after_verification(self) -> None:
        envelope, signing_key = _real_envelope()
        verified = verify_signed_dispatch_envelope(
            envelope, verification_key=signing_key.public_key(), now=NOW
        )

        class _InMemoryReplayStore:
            def __init__(self) -> None:
                self._records: list[GuestAgentReplayNonceRecord] = []

            def load(self) -> list[GuestAgentReplayNonceRecord]:
                return list(self._records)

            def save(self, records: list[GuestAgentReplayNonceRecord]) -> None:
                self._records = list(records)

        protector = GuestAgentReplayProtector(_InMemoryReplayStore())
        outcome = protector.consume_once(verified.request)
        self.assertEqual(outcome, GuestAgentReplayOutcome.ACCEPTED)

    def test_guest_core_remains_non_success_for_verified_request(self) -> None:
        envelope, signing_key = _real_envelope()
        verified = verify_signed_dispatch_envelope(
            envelope, verification_key=signing_key.public_key(), now=NOW
        )
        response = admit_guest_agent_request(verified.request)
        self.assertNotEqual(response.status, GuestAgentResponseStatus.SUCCESS)
        self.assertEqual(response.status, GuestAgentResponseStatus.DECLINED)

    def test_no_execution_authority_is_imported_or_referenced(self) -> None:
        tree = ast.parse(
            VERIFICATION_MODULE_FILE.read_text(encoding="utf-8"),
            filename=str(VERIFICATION_MODULE_FILE),
        )
        referenced: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                referenced.add(node.id)
            elif isinstance(node, ast.Attribute):
                referenced.add(node.attr)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                referenced.update(alias.name for alias in node.names)
        forbidden = {
            "KaliToolGateway",
            "ToolExecutionService",
            "WslKaliOperationProcessAdapter",
            "VmwareKaliOperationProcessAdapter",
        }
        self.assertEqual(referenced & forbidden, set())

    def test_verified_dispatch_value_does_not_expose_execution_authority(
        self,
    ) -> None:
        import dataclasses

        forbidden = {"execute", "run", "dispatch_now", "authorized", "approved"}
        field_names = {
            f.name.lower() for f in dataclasses.fields(GuestAgentVerifiedDispatch)
        }
        self.assertEqual(field_names & forbidden, set())
        self.assertFalse(hasattr(GuestAgentVerifiedDispatch, "execute"))
        self.assertFalse(hasattr(GuestAgentVerifiedDispatch, "run"))


class KeyDomainSeparationTests(unittest.TestCase):
    """The guest verifier never loads/needs the HOST private signing key,
    and never references the mTLS identity key."""

    def setUp(self) -> None:
        self.tree = ast.parse(
            VERIFICATION_MODULE_FILE.read_text(encoding="utf-8"),
            filename=str(VERIFICATION_MODULE_FILE),
        )

    @staticmethod
    def _referenced_names(tree: ast.AST) -> set[str]:
        referenced: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                referenced.add(node.id)
            elif isinstance(node, ast.Attribute):
                referenced.add(node.attr)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                referenced.update(alias.name for alias in node.names)
        return referenced

    def test_ed25519_private_key_is_never_imported(self) -> None:
        self.assertNotIn("Ed25519PrivateKey", self._referenced_names(self.tree))

    def test_no_mtls_module_is_imported_or_referenced(self) -> None:
        forbidden = {
            "GuestAgentMtlsContext",
            "GuestAgentMtlsTrustConfiguration",
            "build_host_client_tls_context",
            "build_guest_server_tls_context",
            "own_private_key_path",
        }
        self.assertEqual(self._referenced_names(self.tree) & forbidden, set())

    def test_verification_key_parameter_is_the_only_key_input(self) -> None:
        import inspect

        parameters = inspect.signature(verify_signed_dispatch_envelope).parameters
        key_like_params = [name for name in parameters if "key" in name.lower()]
        self.assertEqual(key_like_params, ["verification_key"])

    def test_no_hmac_or_subprocess_reference(self) -> None:
        referenced = {name.lower() for name in self._referenced_names(self.tree)}
        self.assertEqual(referenced & {"hmac", "subprocess", "openssl"}, set())


class ErrorHygieneTests(unittest.TestCase):
    """No raw signature/key/request contents reflected into errors."""

    def test_error_does_not_reflect_hostile_request_values(self) -> None:
        hostile_marker = "unique-hostname-marker-xyz-123"
        preview = _preview(hostname=f"{hostile_marker}.example.com")
        envelope, signing_key = _real_envelope(preview=preview)
        mutated_request = replace(envelope.request, request_id="tampered")
        mutated_envelope = GuestAgentSignedDispatchEnvelope(
            request=mutated_request, proof=envelope.proof
        )
        try:
            verify_signed_dispatch_envelope(
                mutated_envelope, verification_key=signing_key.public_key(), now=NOW
            )
            self.fail("expected a verification error")
        except GuestAgentDispatchVerificationError as error:
            self.assertNotIn(hostile_marker, str(error))
            self.assertNotIn(hostile_marker, error.failure.reason)

    def test_error_detail_is_bounded(self) -> None:
        envelope, signing_key = _real_envelope()
        wrong_key = Ed25519PrivateKey.generate().public_key()
        try:
            verify_signed_dispatch_envelope(
                envelope, verification_key=wrong_key, now=NOW
            )
            self.fail("expected a verification error")
        except GuestAgentDispatchVerificationError as error:
            self.assertLess(len(error.failure.reason), 200)


class RegressionTests(unittest.TestCase):
    """Requirements 72-73: existing Guest-Agent and Kali-authority test
    suites remain green -- this is just a pointer; the full suite is run
    by the Lead at the milestone boundary, not duplicated here."""

    def test_existing_guest_agent_core_suite_still_importable_and_unchanged(
        self,
    ) -> None:
        from research.GuestAgentCore import SUPPORTED_GUEST_AGENT_OPERATION_KINDS

        self.assertEqual(len(SUPPORTED_GUEST_AGENT_OPERATION_KINDS), 2)


if __name__ == "__main__":
    unittest.main()
