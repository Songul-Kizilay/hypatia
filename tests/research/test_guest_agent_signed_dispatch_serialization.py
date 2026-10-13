"""Deterministic wire (de)serialization for one signed dispatch envelope.

Mirrors `tests.research.test_guest_agent_protocol_serialization`'s own
proof style for the sibling plain-request/response codec: round-trip
equality, exact closed-key-set enforcement at every nesting level, and
fail-closed decoding on anything malformed. This module performs no
cryptographic verification -- that remains
`research.GuestAgentDispatchVerification.verify_signed_dispatch_envelope`'s
job -- so these tests prove shape and reuse only, never trust.
"""

from __future__ import annotations

import ast
import json
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
    guest_agent_dispatch_proof_metadata_document,
)
from research.GuestAgentProtocol import (  # noqa: E402
    GuestAgentProtocolVersion,
    GuestAgentRequest,
)
from research.GuestAgentProtocolSerialization import (  # noqa: E402
    guest_agent_request_document,
)
from research.GuestAgentSignedDispatchSerialization import (  # noqa: E402
    canonical_guest_agent_signed_dispatch_envelope_bytes,
    guest_agent_signed_dispatch_envelope_document,
    guest_agent_signed_dispatch_envelope_from_bytes,
    guest_agent_signed_dispatch_envelope_from_document,
)
from research.ResearchKaliOperationPreview import (  # noqa: E402
    ResearchKaliOperationKind,
)

SERIALIZATION_MODULE_FILE = (
    SRC_DIR / "research" / "GuestAgentSignedDispatchSerialization.py"
)
THIS_FILE = Path(__file__).resolve()

NOW = datetime(2026, 9, 7, 12, tzinfo=UTC)


def _sample_request() -> GuestAgentRequest:
    return GuestAgentRequest(
        protocol_version=GuestAgentProtocolVersion.V1,
        request_id="request-0001",
        nonce="nonce-0001",
        operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
        operation_digest="a" * 64,
        logical_inputs=(("hostname", "example.com"), ("dns_record_type", "A")),
    )


def _sample_metadata(**overrides: object) -> GuestAgentDispatchProofMetadata:
    fields: dict[str, object] = dict(
        proof_version=GuestAgentDispatchProofVersion.V1,
        request_sha256="b" * 64,
        issuer_identity=DISPATCH_PROOF_HOST_ISSUER_IDENTITY,
        audience_identity=DISPATCH_PROOF_GUEST_AUDIENCE_IDENTITY,
        issued_at=NOW,
        expires_at=NOW + timedelta(seconds=MAX_DISPATCH_PROOF_VALIDITY_SECONDS),
    )
    fields.update(overrides)
    return GuestAgentDispatchProofMetadata(**fields)  # type: ignore[arg-type]


def _sample_envelope() -> GuestAgentSignedDispatchEnvelope:
    proof = GuestAgentDispatchAuthorizationProof(
        metadata=_sample_metadata(), signature_hex="c" * 128
    )
    return GuestAgentSignedDispatchEnvelope(request=_sample_request(), proof=proof)


class RoundTripTests(unittest.TestCase):
    def test_envelope_bytes_round_trip_equal(self) -> None:
        envelope = _sample_envelope()
        data = canonical_guest_agent_signed_dispatch_envelope_bytes(envelope)
        self.assertEqual(
            guest_agent_signed_dispatch_envelope_from_bytes(data), envelope
        )

    def test_envelope_document_round_trip_equal(self) -> None:
        envelope = _sample_envelope()
        document = guest_agent_signed_dispatch_envelope_document(envelope)
        self.assertEqual(
            guest_agent_signed_dispatch_envelope_from_document(document), envelope
        )

    def test_envelope_document_has_exactly_request_and_proof_keys(self) -> None:
        document = guest_agent_signed_dispatch_envelope_document(_sample_envelope())
        self.assertEqual(set(document.keys()), {"request", "proof"})

    def test_proof_document_has_exactly_metadata_and_signature_keys(self) -> None:
        document = guest_agent_signed_dispatch_envelope_document(_sample_envelope())
        self.assertEqual(set(document["proof"].keys()), {"metadata", "signature_hex"})  # type: ignore[union-attr]

    def test_metadata_document_has_exactly_six_keys(self) -> None:
        document = guest_agent_signed_dispatch_envelope_document(_sample_envelope())
        metadata_doc = document["proof"]["metadata"]  # type: ignore[index]
        self.assertEqual(
            set(metadata_doc.keys()),  # type: ignore[union-attr]
            {
                "proof_version",
                "request_sha256",
                "issuer_identity",
                "audience_identity",
                "issued_at",
                "expires_at",
            },
        )

    def test_envelope_request_sub_document_matches_reused_function(self) -> None:
        envelope = _sample_envelope()
        document = guest_agent_signed_dispatch_envelope_document(envelope)
        self.assertEqual(
            document["request"], guest_agent_request_document(envelope.request)
        )

    def test_envelope_metadata_sub_document_matches_reused_function(self) -> None:
        envelope = _sample_envelope()
        document = guest_agent_signed_dispatch_envelope_document(envelope)
        self.assertEqual(
            document["proof"]["metadata"],  # type: ignore[index]
            guest_agent_dispatch_proof_metadata_document(envelope.proof.metadata),
        )

    def test_canonical_bytes_are_deterministic(self) -> None:
        envelope = _sample_envelope()
        first = canonical_guest_agent_signed_dispatch_envelope_bytes(envelope)
        second = canonical_guest_agent_signed_dispatch_envelope_bytes(envelope)
        self.assertEqual(first, second)

    def test_canonical_bytes_use_the_one_repository_convention(self) -> None:
        envelope = _sample_envelope()
        data = canonical_guest_agent_signed_dispatch_envelope_bytes(envelope)
        expected = json.dumps(
            guest_agent_signed_dispatch_envelope_document(envelope),
            sort_keys=True,
            ensure_ascii=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        self.assertEqual(data, expected)


class FailClosedEnvelopeShapeTests(unittest.TestCase):
    def _document(self) -> dict[str, object]:
        return guest_agent_signed_dispatch_envelope_document(_sample_envelope())

    def test_non_dict_document_rejected(self) -> None:
        for bad in (None, "not a document", 123, [1, 2, 3]):
            with self.subTest(value=bad):
                with self.assertRaises(ResearchError):
                    guest_agent_signed_dispatch_envelope_from_document(bad)

    def test_unknown_top_level_key_rejected(self) -> None:
        document = self._document()
        document["extra"] = "x"
        with self.assertRaises(ResearchError):
            guest_agent_signed_dispatch_envelope_from_document(document)

    def test_missing_request_key_rejected(self) -> None:
        document = self._document()
        del document["request"]
        with self.assertRaises(ResearchError):
            guest_agent_signed_dispatch_envelope_from_document(document)

    def test_missing_proof_key_rejected(self) -> None:
        document = self._document()
        del document["proof"]
        with self.assertRaises(ResearchError):
            guest_agent_signed_dispatch_envelope_from_document(document)

    def test_non_bytes_input_to_from_bytes_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            guest_agent_signed_dispatch_envelope_from_bytes("not bytes")  # type: ignore[arg-type]

    def test_invalid_json_bytes_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            guest_agent_signed_dispatch_envelope_from_bytes(b"{not json")

    def test_invalid_utf8_bytes_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            guest_agent_signed_dispatch_envelope_from_bytes(b"\xff\xfe\x00")


class FailClosedProofShapeTests(unittest.TestCase):
    def _document(self) -> dict[str, object]:
        return guest_agent_signed_dispatch_envelope_document(_sample_envelope())

    def test_unknown_proof_key_rejected(self) -> None:
        document = self._document()
        document["proof"]["extra"] = "x"  # type: ignore[index]
        with self.assertRaises(ResearchError):
            guest_agent_signed_dispatch_envelope_from_document(document)

    def test_missing_metadata_key_rejected(self) -> None:
        document = self._document()
        del document["proof"]["metadata"]  # type: ignore[arg-type]
        with self.assertRaises(ResearchError):
            guest_agent_signed_dispatch_envelope_from_document(document)

    def test_missing_signature_hex_key_rejected(self) -> None:
        document = self._document()
        del document["proof"]["signature_hex"]  # type: ignore[arg-type]
        with self.assertRaises(ResearchError):
            guest_agent_signed_dispatch_envelope_from_document(document)

    def test_non_dict_proof_rejected(self) -> None:
        document = self._document()
        document["proof"] = "not a proof"
        with self.assertRaises(ResearchError):
            guest_agent_signed_dispatch_envelope_from_document(document)

    def test_signature_hex_wrong_length_rejected(self) -> None:
        document = self._document()
        document["proof"]["signature_hex"] = "ab"  # type: ignore[index]
        with self.assertRaises(ResearchError):
            guest_agent_signed_dispatch_envelope_from_document(document)


class FailClosedMetadataShapeTests(unittest.TestCase):
    _REQUIRED_KEYS = (
        "proof_version",
        "request_sha256",
        "issuer_identity",
        "audience_identity",
        "issued_at",
        "expires_at",
    )

    def _document(self) -> dict[str, object]:
        return guest_agent_signed_dispatch_envelope_document(_sample_envelope())

    def test_unknown_metadata_key_rejected(self) -> None:
        document = self._document()
        document["proof"]["metadata"]["extra"] = "x"  # type: ignore[index]
        with self.assertRaises(ResearchError):
            guest_agent_signed_dispatch_envelope_from_document(document)

    def test_non_dict_metadata_rejected(self) -> None:
        document = self._document()
        document["proof"]["metadata"] = "not metadata"  # type: ignore[index]
        with self.assertRaises(ResearchError):
            guest_agent_signed_dispatch_envelope_from_document(document)

    def test_each_required_metadata_key_missing_individually_rejected(self) -> None:
        for key in self._REQUIRED_KEYS:
            with self.subTest(missing=key):
                document = self._document()
                del document["proof"]["metadata"][key]  # type: ignore[arg-type]
                with self.assertRaises(ResearchError):
                    guest_agent_signed_dispatch_envelope_from_document(document)

    def test_unrecognized_proof_version_rejected(self) -> None:
        document = self._document()
        document["proof"]["metadata"]["proof_version"] = (  # type: ignore[index]
            "hypatia-kali-guest-agent/dispatch-proof/999"
        )
        with self.assertRaises(ResearchError):
            guest_agent_signed_dispatch_envelope_from_document(document)

    def test_non_string_proof_version_rejected(self) -> None:
        document = self._document()
        document["proof"]["metadata"]["proof_version"] = 123  # type: ignore[index]
        with self.assertRaises(ResearchError):
            guest_agent_signed_dispatch_envelope_from_document(document)

    def test_malformed_issued_at_timestamp_rejected(self) -> None:
        document = self._document()
        document["proof"]["metadata"]["issued_at"] = "not-a-timestamp"  # type: ignore[index]
        with self.assertRaises(ResearchError):
            guest_agent_signed_dispatch_envelope_from_document(document)

    def test_naive_issued_at_timestamp_rejected(self) -> None:
        document = self._document()
        document["proof"]["metadata"]["issued_at"] = "2026-01-01T00:00:00"  # type: ignore[index]
        with self.assertRaises(ResearchError):
            guest_agent_signed_dispatch_envelope_from_document(document)

    def test_naive_expires_at_timestamp_rejected(self) -> None:
        document = self._document()
        document["proof"]["metadata"]["expires_at"] = "2026-01-01T00:01:00"  # type: ignore[index]
        with self.assertRaises(ResearchError):
            guest_agent_signed_dispatch_envelope_from_document(document)

    def test_non_string_timestamp_rejected(self) -> None:
        document = self._document()
        document["proof"]["metadata"]["issued_at"] = 12345  # type: ignore[index]
        with self.assertRaises(ResearchError):
            guest_agent_signed_dispatch_envelope_from_document(document)

    def test_expiry_not_after_issued_at_rejected_via_validated_type(self) -> None:
        document = self._document()
        document["proof"]["metadata"]["expires_at"] = document["proof"]["metadata"][  # type: ignore[index]
            "issued_at"
        ]
        with self.assertRaises(ResearchError):
            guest_agent_signed_dispatch_envelope_from_document(document)


class StructuralSecurityTests(unittest.TestCase):
    """AST-based proof that this is pure data-shape plumbing only."""

    def setUp(self) -> None:
        self.tree = ast.parse(
            SERIALIZATION_MODULE_FILE.read_text(encoding="utf-8"),
            filename=str(SERIALIZATION_MODULE_FILE),
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

    def test_no_network_process_or_crypto_reference(self) -> None:
        forbidden = {
            "socket",
            "ssl",
            "subprocess",
            "Ed25519PrivateKey",
            "Ed25519PublicKey",
            "verify_signed_dispatch_envelope",
            "consume_once",
            "admit_guest_agent_request",
        }
        self.assertEqual(self._referenced_names(self.tree) & forbidden, set())

    def test_no_pickle_eval_or_yaml_reference(self) -> None:
        forbidden = {"pickle", "eval", "yaml", "exec", "__import__"}
        self.assertEqual(self._referenced_names(self.tree) & forbidden, set())


if __name__ == "__main__":
    unittest.main()
