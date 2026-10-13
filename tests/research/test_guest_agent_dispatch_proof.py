"""The pure dispatch-proof/envelope type contract, in isolation.

No signing, no verification, no cryptography import at all -- just
construction, validation, and canonical-encoding determinism for
`research.GuestAgentDispatchProof`'s types. Signing/verification behavior
lives in `test_guest_agent_dispatch_signing.py`/
`test_guest_agent_dispatch_verification.py`.
"""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError  # noqa: E402
from research.GuestAgentDispatchProof import (  # noqa: E402
    DISPATCH_PROOF_GUEST_AUDIENCE_IDENTITY,
    DISPATCH_PROOF_HOST_ISSUER_IDENTITY,
    MAX_DISPATCH_PROOF_VALIDITY_SECONDS,
    GuestAgentDispatchAuthorizationProof,
    GuestAgentDispatchProofMetadata,
    GuestAgentDispatchProofVersion,
    GuestAgentSignedDispatchEnvelope,
    canonical_guest_agent_dispatch_proof_metadata_bytes,
    guest_agent_dispatch_proof_metadata_document,
)
from research.GuestAgentProtocol import (  # noqa: E402
    GuestAgentProtocolVersion,
    GuestAgentRequest,
)
from research.ResearchKaliOperationPreview import (  # noqa: E402
    ResearchKaliOperationKind,
)

NOW = datetime(2026, 9, 7, 12, tzinfo=UTC)
VALID_SHA256 = "a" * 64
VALID_SIGNATURE_HEX = "b" * 128


def _metadata(**overrides: object) -> GuestAgentDispatchProofMetadata:
    base: dict[str, object] = dict(
        proof_version=GuestAgentDispatchProofVersion.V1,
        request_sha256=VALID_SHA256,
        issuer_identity=DISPATCH_PROOF_HOST_ISSUER_IDENTITY,
        audience_identity=DISPATCH_PROOF_GUEST_AUDIENCE_IDENTITY,
        issued_at=NOW,
        expires_at=NOW + timedelta(seconds=30),
    )
    base.update(overrides)
    return GuestAgentDispatchProofMetadata(**base)  # type: ignore[arg-type]


def _sample_request() -> GuestAgentRequest:
    return GuestAgentRequest(
        protocol_version=GuestAgentProtocolVersion.V1,
        request_id="req-1",
        nonce="nonce-1",
        operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
        operation_digest="c" * 64,
        logical_inputs=(("hostname", "example.com"), ("dns_record_type", "A")),
    )


class ProofVersionTests(unittest.TestCase):
    def test_proof_version_is_separate_from_protocol_version(self) -> None:
        self.assertNotEqual(
            GuestAgentDispatchProofVersion.V1.value, GuestAgentProtocolVersion.V1.value
        )

    def test_proof_version_value_is_fixed(self) -> None:
        self.assertEqual(
            GuestAgentDispatchProofVersion.V1.value,
            "hypatia-kali-guest-agent/dispatch-proof/1",
        )


class FixedIdentityTests(unittest.TestCase):
    def test_issuer_is_the_fixed_host_identity(self) -> None:
        self.assertEqual(
            DISPATCH_PROOF_HOST_ISSUER_IDENTITY, "hypatia-kali-guest-agent/host/1"
        )

    def test_audience_is_the_fixed_guest_identity(self) -> None:
        self.assertEqual(
            DISPATCH_PROOF_GUEST_AUDIENCE_IDENTITY, "hypatia-kali-guest-agent/guest/1"
        )

    def test_issuer_and_audience_are_distinct(self) -> None:
        self.assertNotEqual(
            DISPATCH_PROOF_HOST_ISSUER_IDENTITY, DISPATCH_PROOF_GUEST_AUDIENCE_IDENTITY
        )


class MetadataConstructionTests(unittest.TestCase):
    def test_valid_metadata_constructs(self) -> None:
        metadata = _metadata()
        self.assertEqual(metadata.request_sha256, VALID_SHA256)

    def test_wrong_proof_version_type_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            _metadata(proof_version="hypatia-kali-guest-agent/dispatch-proof/2")

    def test_malformed_request_sha256_rejected(self) -> None:
        for bad in ("", "not-hex", "a" * 63, "A" * 64, "a" * 65, None, 12345):
            with self.subTest(value=bad):
                with self.assertRaises(ResearchError):
                    _metadata(request_sha256=bad)

    def test_wrong_issuer_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            _metadata(issuer_identity="hypatia-kali-guest-agent/guest/1")

    def test_wrong_audience_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            _metadata(audience_identity="hypatia-kali-guest-agent/host/1")

    def test_arbitrary_issuer_string_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            _metadata(issuer_identity="totally-untrusted-issuer")

    def test_arbitrary_audience_string_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            _metadata(audience_identity="totally-untrusted-audience")

    def test_naive_issued_at_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            _metadata(issued_at=datetime(2026, 9, 7, 12))

    def test_naive_expires_at_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            _metadata(expires_at=datetime(2026, 9, 7, 13))

    def test_malformed_timestamp_type_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            _metadata(issued_at="2026-09-07T12:00:00Z")

    def test_expires_at_before_issued_at_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            _metadata(issued_at=NOW, expires_at=NOW - timedelta(seconds=1))

    def test_expires_at_equal_to_issued_at_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            _metadata(issued_at=NOW, expires_at=NOW)

    def test_validity_window_exceeding_ceiling_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            _metadata(
                issued_at=NOW,
                expires_at=NOW
                + timedelta(seconds=MAX_DISPATCH_PROOF_VALIDITY_SECONDS + 1),
            )

    def test_validity_window_at_exact_ceiling_is_accepted(self) -> None:
        metadata = _metadata(
            issued_at=NOW,
            expires_at=NOW + timedelta(seconds=MAX_DISPATCH_PROOF_VALIDITY_SECONDS),
        )
        self.assertEqual(
            (metadata.expires_at - metadata.issued_at).total_seconds(),
            MAX_DISPATCH_PROOF_VALIDITY_SECONDS,
        )

    def test_no_arbitrary_extra_fields_exist(self) -> None:
        import dataclasses

        field_names = {
            f.name for f in dataclasses.fields(GuestAgentDispatchProofMetadata)
        }
        self.assertEqual(
            field_names,
            {
                "proof_version",
                "request_sha256",
                "issuer_identity",
                "audience_identity",
                "issued_at",
                "expires_at",
            },
        )


class CanonicalEncodingTests(unittest.TestCase):
    def test_canonical_bytes_are_deterministic(self) -> None:
        metadata = _metadata()
        first = canonical_guest_agent_dispatch_proof_metadata_bytes(metadata)
        second = canonical_guest_agent_dispatch_proof_metadata_bytes(metadata)
        self.assertEqual(first, second)

    def test_canonical_bytes_change_with_any_field(self) -> None:
        base = canonical_guest_agent_dispatch_proof_metadata_bytes(_metadata())
        variants = [
            _metadata(request_sha256="f" * 64),
            _metadata(
                issued_at=NOW + timedelta(seconds=1),
                expires_at=NOW + timedelta(seconds=31),
            ),
            _metadata(expires_at=NOW + timedelta(seconds=45)),
        ]
        for variant in variants:
            with self.subTest(variant=variant):
                self.assertNotEqual(
                    canonical_guest_agent_dispatch_proof_metadata_bytes(variant), base
                )

    def test_document_has_no_unexpected_keys(self) -> None:
        document = guest_agent_dispatch_proof_metadata_document(_metadata())
        self.assertEqual(
            set(document.keys()),
            {
                "proof_version",
                "request_sha256",
                "issuer_identity",
                "audience_identity",
                "issued_at",
                "expires_at",
            },
        )

    def test_no_pickle_eval_or_yaml_involved(self) -> None:
        import ast

        module_file = SRC_DIR / "research" / "GuestAgentDispatchProof.py"
        tree = ast.parse(
            module_file.read_text(encoding="utf-8"), filename=str(module_file)
        )
        referenced: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                referenced.add(node.id)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                referenced.update(alias.name for alias in node.names)
        self.assertEqual(referenced & {"pickle", "eval", "yaml", "marshal"}, set())


class ProofConstructionTests(unittest.TestCase):
    def test_valid_proof_constructs(self) -> None:
        proof = GuestAgentDispatchAuthorizationProof(
            metadata=_metadata(), signature_hex=VALID_SIGNATURE_HEX
        )
        self.assertEqual(len(proof.signature_hex), 128)

    def test_non_metadata_object_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentDispatchAuthorizationProof(
                metadata={"not": "a metadata object"}, signature_hex=VALID_SIGNATURE_HEX  # type: ignore[arg-type]
            )

    def test_malformed_signature_hex_rejected(self) -> None:
        for bad in (
            "",
            "0" * 127,
            "0" * 129,
            "F" * 128,
            "g" * 128,
            None,
            b"\x00" * 64,
        ):
            with self.subTest(value=bad):
                with self.assertRaises(ResearchError):
                    GuestAgentDispatchAuthorizationProof(
                        metadata=_metadata(), signature_hex=bad  # type: ignore[arg-type]
                    )

    def test_all_zero_signature_shape_is_structurally_acceptable(
        self,
    ) -> None:
        """Shape validation alone cannot and must not try to detect a
        cryptographically weak signature -- that is entirely
        `verify_signed_dispatch_envelope`'s job. This only proves the
        all-zero/all-ff adversarial shapes are not rejected for the wrong
        reason (malformed hex) before verification gets a chance to
        reject them for the right reason (invalid signature)."""
        for value in ("0" * 128, "f" * 128):
            with self.subTest(value=value):
                proof = GuestAgentDispatchAuthorizationProof(
                    metadata=_metadata(), signature_hex=value
                )
                self.assertEqual(proof.signature_hex, value)


class EnvelopeConstructionTests(unittest.TestCase):
    def test_valid_envelope_constructs(self) -> None:
        envelope = GuestAgentSignedDispatchEnvelope(
            request=_sample_request(),
            proof=GuestAgentDispatchAuthorizationProof(
                metadata=_metadata(), signature_hex=VALID_SIGNATURE_HEX
            ),
        )
        self.assertIsInstance(envelope.request, GuestAgentRequest)

    def test_non_request_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentSignedDispatchEnvelope(
                request="not a request",  # type: ignore[arg-type]
                proof=GuestAgentDispatchAuthorizationProof(
                    metadata=_metadata(), signature_hex=VALID_SIGNATURE_HEX
                ),
            )

    def test_non_proof_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentSignedDispatchEnvelope(
                request=_sample_request(), proof="not a proof"  # type: ignore[arg-type]
            )

    def test_guest_agent_request_type_has_no_signature_field(self) -> None:
        """TYPED REQUEST PROTOCOL != AUTHORIZATION PROOF LAYER -- the
        protocol type itself must never gain a signature-shaped field."""
        import dataclasses

        field_names = {f.name.lower() for f in dataclasses.fields(GuestAgentRequest)}
        forbidden = {"signature", "proof", "signed", "authorized", "approved"}
        self.assertEqual(field_names & forbidden, set())


if __name__ == "__main__":
    unittest.main()
