"""The execution-bound V2 protocol generation: `GuestAgentExecutionLimits`
and `GuestAgentRequest.execution_limits`.

V1 REQUEST != EXECUTION-BOUND REQUEST. EXECUTION LIMIT PRESENT != EXECUTION
AUTHORITY. EXECUTION LIMIT VALID != EXECUTION AUTHORITY. SIGNED EXECUTION
LIMIT != EXECUTION SUCCESS. Every test below either proves V1 is completely
unaffected by this addition (same bytes, same decode behavior, same
construction rules), or proves V2's execution-limit binding is exact,
fail-closed, deterministic, and cryptographically load-bearing (a changed
limit changes the canonical bytes and therefore the signed digest).
"""

from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError  # noqa: E402
from research.GuestAgentProtocol import (  # noqa: E402
    GuestAgentExecutionLimits,
    GuestAgentProtocolVersion,
    GuestAgentRequest,
)
from research.GuestAgentProtocolSerialization import (  # noqa: E402
    canonical_guest_agent_request_bytes,
    guest_agent_execution_limits_document,
    guest_agent_execution_limits_from_document,
    guest_agent_request_document,
    guest_agent_request_from_bytes,
    guest_agent_request_from_document,
)
from research.ResearchKaliOperationPreview import (  # noqa: E402
    ResearchKaliOperationKind,
)

VALID_DIGEST = hashlib.sha256(b"example-preview").hexdigest()


def _v1_request(**overrides: object) -> GuestAgentRequest:
    base: dict[str, object] = dict(
        protocol_version=GuestAgentProtocolVersion.V1,
        request_id="req-1",
        nonce="nonce-1",
        operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
        operation_digest=VALID_DIGEST,
        logical_inputs=(("hostname", "example.com"), ("dns_record_type", "A")),
    )
    base.update(overrides)
    return GuestAgentRequest(**base)  # type: ignore[arg-type]


def _v2_request(*, max_seconds: float = 5.0, **overrides: object) -> GuestAgentRequest:
    base: dict[str, object] = dict(
        protocol_version=GuestAgentProtocolVersion.V2,
        request_id="req-1",
        nonce="nonce-1",
        operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
        operation_digest=VALID_DIGEST,
        logical_inputs=(("hostname", "example.com"), ("dns_record_type", "A")),
        execution_limits=GuestAgentExecutionLimits(max_seconds=max_seconds),
    )
    base.update(overrides)
    return GuestAgentRequest(**base)  # type: ignore[arg-type]


class V1UnaffectedTests(unittest.TestCase):
    """Requirements 1-5: V1 remains byte-for-byte, behaviorally unchanged."""

    def test_v1_remains_constructible_and_valid(self) -> None:
        request = _v1_request()
        self.assertIsNone(request.execution_limits)
        self.assertIs(request.protocol_version, GuestAgentProtocolVersion.V1)

    def test_v1_document_has_no_execution_limits_key(self) -> None:
        document = guest_agent_request_document(_v1_request())
        self.assertNotIn("execution_limits", document)
        self.assertEqual(
            set(document.keys()),
            {
                "protocol_version",
                "request_id",
                "nonce",
                "operation_kind",
                "operation_digest",
                "logical_inputs",
            },
        )

    def test_v1_canonical_bytes_match_the_exact_pre_v2_recipe(self) -> None:
        request = _v1_request()
        data = canonical_guest_agent_request_bytes(request)
        expected = json.dumps(
            {
                "protocol_version": "hypatia-kali-guest-agent/1",
                "request_id": "req-1",
                "nonce": "nonce-1",
                "operation_kind": "dns_record_lookup",
                "operation_digest": VALID_DIGEST,
                "logical_inputs": [
                    ["hostname", "example.com"],
                    ["dns_record_type", "A"],
                ],
            },
            sort_keys=True,
            ensure_ascii=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        self.assertEqual(data, expected)

    def test_v1_decode_behavior_unchanged_round_trip(self) -> None:
        request = _v1_request()
        data = canonical_guest_agent_request_bytes(request)
        restored = guest_agent_request_from_bytes(data)
        self.assertEqual(restored, request)
        self.assertIsNone(restored.execution_limits)

    def test_v1_cannot_carry_execution_limits(self) -> None:
        with self.assertRaises(ResearchError):
            _v1_request(execution_limits=GuestAgentExecutionLimits(max_seconds=5.0))

    def test_v1_wire_document_with_execution_limits_key_is_rejected(self) -> None:
        document = guest_agent_request_document(_v1_request())
        document["execution_limits"] = {"max_seconds": 5.0}
        with self.assertRaises(ResearchError):
            guest_agent_request_from_document(document)

    def test_v1_cannot_create_prepared_invocation(self) -> None:
        from research.GuestAgentInvocationPreparation import (
            prepare_guest_agent_invocation,
        )
        from research.GuestAgentReplayNonceStore import GuestAgentReplayNonceStore
        from research.GuestAgentReplayProtector import GuestAgentReplayProtector

        class _MemoryStore:
            def __init__(self) -> None:
                self._records: list = []

            def load(self):
                return list(self._records)

            def save(self, records):
                self._records = list(records)

        store: GuestAgentReplayNonceStore = _MemoryStore()  # type: ignore[assignment]
        protector = GuestAgentReplayProtector(store)
        response, prepared = prepare_guest_agent_invocation(_v1_request(), protector)
        self.assertIsNone(prepared)


class V2RequiredTests(unittest.TestCase):
    """Requirements 6-7: V2 requires execution limits; shape fails closed."""

    def test_v2_requires_execution_limits(self) -> None:
        with self.assertRaises(ResearchError):
            _v2_request(execution_limits=None)

    def test_v2_execution_limits_must_be_the_real_type(self) -> None:
        for bad in ({"max_seconds": 5.0}, "5.0", 5.0, None):
            with self.subTest(value=bad):
                with self.assertRaises(ResearchError):
                    _v2_request(execution_limits=bad)

    def test_v2_document_carries_execution_limits_key(self) -> None:
        document = guest_agent_request_document(_v2_request())
        self.assertIn("execution_limits", document)
        self.assertEqual(document["execution_limits"], {"max_seconds": 5.0})

    def test_v2_round_trips_through_bytes(self) -> None:
        request = _v2_request()
        data = canonical_guest_agent_request_bytes(request)
        restored = guest_agent_request_from_bytes(data)
        self.assertEqual(restored, request)

    def test_v2_missing_execution_limits_key_fails_closed_at_decode(self) -> None:
        document = guest_agent_request_document(_v2_request())
        del document["execution_limits"]
        with self.assertRaises(ResearchError):
            guest_agent_request_from_document(document)

    def test_v2_unknown_execution_limits_field_fails_closed(self) -> None:
        document = guest_agent_request_document(_v2_request())
        document["execution_limits"]["extra"] = 1  # type: ignore[index]
        with self.assertRaises(ResearchError):
            guest_agent_request_from_document(document)

    def test_v2_missing_max_seconds_key_fails_closed(self) -> None:
        document = guest_agent_request_document(_v2_request())
        del document["execution_limits"]["max_seconds"]  # type: ignore[arg-type]
        with self.assertRaises(ResearchError):
            guest_agent_request_from_document(document)


class NumericSemanticsTests(unittest.TestCase):
    """Requirement set from MAX_SECONDS REPRESENTATION / EXECUTION-LIMIT TESTS."""

    def test_bool_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentExecutionLimits(max_seconds=True)

    def test_string_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentExecutionLimits(max_seconds="5")  # type: ignore[arg-type]

    def test_none_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentExecutionLimits(max_seconds=None)  # type: ignore[arg-type]

    def test_zero_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentExecutionLimits(max_seconds=0)

    def test_negative_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentExecutionLimits(max_seconds=-1.0)

    def test_nan_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentExecutionLimits(max_seconds=float("nan"))

    def test_positive_infinity_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentExecutionLimits(max_seconds=float("inf"))

    def test_negative_infinity_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentExecutionLimits(max_seconds=float("-inf"))

    def test_very_small_positive_value_accepted(self) -> None:
        limits = GuestAgentExecutionLimits(max_seconds=0.001)
        self.assertEqual(limits.max_seconds, 0.001)

    def test_normal_value_accepted(self) -> None:
        limits = GuestAgentExecutionLimits(max_seconds=5.0)
        self.assertEqual(limits.max_seconds, 5.0)

    def test_int_input_normalized_to_float(self) -> None:
        limits = GuestAgentExecutionLimits(max_seconds=5)
        self.assertIsInstance(limits.max_seconds, float)
        self.assertEqual(limits.max_seconds, 5.0)

    def test_whole_number_float_does_not_round_or_truncate(self) -> None:
        limits = GuestAgentExecutionLimits(max_seconds=30)
        self.assertEqual(limits.max_seconds, 30.0)

    def test_fractional_value_is_not_rounded_up(self) -> None:
        limits = GuestAgentExecutionLimits(max_seconds=0.5)
        self.assertEqual(limits.max_seconds, 0.5)
        document = guest_agent_execution_limits_document(limits)
        self.assertEqual(document["max_seconds"], 0.5)
        restored = guest_agent_execution_limits_from_document(document)
        self.assertEqual(restored.max_seconds, 0.5)

    def test_no_upper_ceiling_invented_at_this_type(self) -> None:
        # The exact host-approved value is carried uncapped; the global
        # hard cap (MAX_KALI_OPERATION_TIMEOUT_SECONDS) is applied only
        # later, at prepared-invocation construction -- never here.
        limits = GuestAgentExecutionLimits(max_seconds=3600.0)
        self.assertEqual(limits.max_seconds, 3600.0)

    def test_canonical_bytes_use_a_decimal_point_float_not_an_int(self) -> None:
        request = _v2_request(execution_limits=GuestAgentExecutionLimits(max_seconds=5))
        data = canonical_guest_agent_request_bytes(request)
        self.assertIn(b'"max_seconds":5.0', data)
        self.assertNotIn(b'"max_seconds":5}', data)

    def test_wire_bool_max_seconds_rejected(self) -> None:
        document = guest_agent_request_document(_v2_request())
        document["execution_limits"]["max_seconds"] = True  # type: ignore[index]
        with self.assertRaises(ResearchError):
            guest_agent_request_from_document(document)

    def test_wire_string_max_seconds_rejected(self) -> None:
        document = guest_agent_request_document(_v2_request())
        document["execution_limits"]["max_seconds"] = "5.0"  # type: ignore[index]
        with self.assertRaises(ResearchError):
            guest_agent_request_from_document(document)


class SignedBindingTests(unittest.TestCase):
    """Requirements 10-12: a changed limit changes the canonical bytes, the
    request SHA-256, and therefore breaks Ed25519 proof verification."""

    def test_max_seconds_change_changes_canonical_bytes(self) -> None:
        request_a = _v2_request(max_seconds=5.0)
        request_b = _v2_request(max_seconds=6.0)
        self.assertNotEqual(
            canonical_guest_agent_request_bytes(request_a),
            canonical_guest_agent_request_bytes(request_b),
        )

    def test_max_seconds_change_changes_request_sha256(self) -> None:
        request_a = _v2_request(max_seconds=5.0)
        request_b = _v2_request(max_seconds=6.0)
        digest_a = hashlib.sha256(
            canonical_guest_agent_request_bytes(request_a)
        ).hexdigest()
        digest_b = hashlib.sha256(
            canonical_guest_agent_request_bytes(request_b)
        ).hexdigest()
        self.assertNotEqual(digest_a, digest_b)

    def test_max_seconds_tampering_breaks_ed25519_verification(self) -> None:
        from datetime import UTC, datetime, timedelta

        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
        )

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
        from research.GuestAgentDispatchVerification import (
            GuestAgentDispatchVerificationError,
            verify_signed_dispatch_envelope,
        )

        now = datetime(2026, 9, 7, 12, tzinfo=UTC)
        signing_key = Ed25519PrivateKey.generate()
        request = _v2_request(max_seconds=5.0)
        metadata = GuestAgentDispatchProofMetadata(
            proof_version=GuestAgentDispatchProofVersion.V1,
            request_sha256=hashlib.sha256(
                canonical_guest_agent_request_bytes(request)
            ).hexdigest(),
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
        envelope = GuestAgentSignedDispatchEnvelope(request=request, proof=proof)

        # Sanity: the untampered envelope verifies.
        verify_signed_dispatch_envelope(
            envelope, verification_key=signing_key.public_key(), now=now
        )

        # Tamper only the execution limit, leaving the signature as-is.
        import dataclasses

        tampered_request = dataclasses.replace(
            request,
            execution_limits=GuestAgentExecutionLimits(max_seconds=6.0),
        )
        tampered_envelope = dataclasses.replace(envelope, request=tampered_request)
        with self.assertRaises(GuestAgentDispatchVerificationError):
            verify_signed_dispatch_envelope(
                tampered_envelope,
                verification_key=signing_key.public_key(),
                now=now,
            )


if __name__ == "__main__":
    unittest.main()
