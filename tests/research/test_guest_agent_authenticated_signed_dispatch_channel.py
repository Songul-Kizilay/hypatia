"""Role-direction-bound signed-dispatch channel wrapper tests.

Mirrors `tests.research.test_guest_agent_authenticated_channel`'s own
proof style for the sibling plain-request/response channel: construction
fails closed on a wrong-role or non-peer value, each direction only
exposes its own two methods, and round-tripping an encoded value through
the opposite channel returns the exact original value. AUTHENTICATED
CHANNEL != EXECUTION AUTHORITY, != VERIFIED DISPATCH -- these tests prove
only shape and direction, never trust.
"""

from __future__ import annotations

import ast
import sys
import unittest
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

import research.GuestAgentPeerAuthenticator as peer_authenticator_module  # noqa: E402
from core.Exceptions import ResearchError  # noqa: E402
from research.GuestAgentAuthenticatedSignedDispatchChannel import (  # noqa: E402
    GuestAgentAuthenticatedSignedDispatchGuestChannel,
    GuestAgentAuthenticatedSignedDispatchHostChannel,
)
from research.GuestAgentDispatchProof import (  # noqa: E402
    DISPATCH_PROOF_GUEST_AUDIENCE_IDENTITY,
    DISPATCH_PROOF_HOST_ISSUER_IDENTITY,
    MAX_DISPATCH_PROOF_VALIDITY_SECONDS,
    GuestAgentDispatchAuthorizationProof,
    GuestAgentDispatchProofMetadata,
    GuestAgentDispatchProofVersion,
    GuestAgentSignedDispatchEnvelope,
)
from research.GuestAgentMtlsTrustConfiguration import (  # noqa: E402
    GuestAgentPeerIdentity,
    GuestAgentPeerRole,
)
from research.GuestAgentPeerAuthenticator import (  # noqa: E402
    GuestAgentAuthenticatedPeer,
)
from research.GuestAgentProtocol import (  # noqa: E402
    GuestAgentProtocolVersion,
    GuestAgentRequest,
    GuestAgentResponse,
    GuestAgentResponseStatus,
)
from research.ResearchKaliOperationPreview import (  # noqa: E402
    ResearchKaliOperationKind,
)

CHANNEL_MODULE_FILE = (
    SRC_DIR / "research" / "GuestAgentAuthenticatedSignedDispatchChannel.py"
)

NOW = datetime(2026, 9, 7, 12, tzinfo=UTC)


def _authenticated_peer(role: GuestAgentPeerRole) -> GuestAgentAuthenticatedPeer:
    token = peer_authenticator_module._AUTHENTICATION_CAPABILITY
    other = (
        GuestAgentPeerRole.GUEST
        if role is GuestAgentPeerRole.HOST
        else (GuestAgentPeerRole.HOST)
    )
    return GuestAgentAuthenticatedPeer(
        own_role=role,
        peer_identity=GuestAgentPeerIdentity.for_role(other),
        _authentication_token=token,
    )


def _sample_request() -> GuestAgentRequest:
    return GuestAgentRequest(
        protocol_version=GuestAgentProtocolVersion.V1,
        request_id="request-0001",
        nonce="nonce-0001",
        operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
        operation_digest="a" * 64,
        logical_inputs=(("hostname", "example.com"), ("dns_record_type", "A")),
    )


def _sample_envelope() -> GuestAgentSignedDispatchEnvelope:
    metadata = GuestAgentDispatchProofMetadata(
        proof_version=GuestAgentDispatchProofVersion.V1,
        request_sha256="b" * 64,
        issuer_identity=DISPATCH_PROOF_HOST_ISSUER_IDENTITY,
        audience_identity=DISPATCH_PROOF_GUEST_AUDIENCE_IDENTITY,
        issued_at=NOW,
        expires_at=NOW + timedelta(seconds=MAX_DISPATCH_PROOF_VALIDITY_SECONDS),
    )
    proof = GuestAgentDispatchAuthorizationProof(
        metadata=metadata, signature_hex="c" * 128
    )
    return GuestAgentSignedDispatchEnvelope(request=_sample_request(), proof=proof)


def _sample_response() -> GuestAgentResponse:
    return GuestAgentResponse(
        protocol_version=GuestAgentProtocolVersion.V1,
        request_id="request-0001",
        status=GuestAgentResponseStatus.DECLINED,
        detail="A fixed detail sentence.",
        output_lines=(),
    )


class ConstructionTests(unittest.TestCase):
    def test_host_channel_requires_host_authenticated_peer(self) -> None:
        peer = _authenticated_peer(GuestAgentPeerRole.HOST)
        channel = GuestAgentAuthenticatedSignedDispatchHostChannel(
            authenticated_peer=peer
        )
        self.assertIs(channel.authenticated_peer, peer)

    def test_guest_channel_requires_guest_authenticated_peer(self) -> None:
        peer = _authenticated_peer(GuestAgentPeerRole.GUEST)
        channel = GuestAgentAuthenticatedSignedDispatchGuestChannel(
            authenticated_peer=peer
        )
        self.assertIs(channel.authenticated_peer, peer)

    def test_host_channel_rejects_guest_role_peer(self) -> None:
        peer = _authenticated_peer(GuestAgentPeerRole.GUEST)
        with self.assertRaises(ResearchError):
            GuestAgentAuthenticatedSignedDispatchHostChannel(authenticated_peer=peer)

    def test_guest_channel_rejects_host_role_peer(self) -> None:
        peer = _authenticated_peer(GuestAgentPeerRole.HOST)
        with self.assertRaises(ResearchError):
            GuestAgentAuthenticatedSignedDispatchGuestChannel(authenticated_peer=peer)

    def test_host_channel_rejects_non_peer_value(self) -> None:
        for bad in (None, "not a peer", object(), 123):
            with self.subTest(value=bad):
                with self.assertRaises(ResearchError):
                    GuestAgentAuthenticatedSignedDispatchHostChannel(
                        authenticated_peer=bad  # type: ignore[arg-type]
                    )

    def test_guest_channel_rejects_non_peer_value(self) -> None:
        for bad in (None, "not a peer", object(), 123):
            with self.subTest(value=bad):
                with self.assertRaises(ResearchError):
                    GuestAgentAuthenticatedSignedDispatchGuestChannel(
                        authenticated_peer=bad  # type: ignore[arg-type]
                    )

    def test_channels_are_frozen(self) -> None:
        host_channel = GuestAgentAuthenticatedSignedDispatchHostChannel(
            authenticated_peer=_authenticated_peer(GuestAgentPeerRole.HOST)
        )
        with self.assertRaises(FrozenInstanceError):
            host_channel.authenticated_peer = _authenticated_peer(  # type: ignore[misc]
                GuestAgentPeerRole.HOST
            )


class RoundTripTests(unittest.TestCase):
    def test_host_encodes_and_guest_decodes_the_same_envelope(self) -> None:
        host_channel = GuestAgentAuthenticatedSignedDispatchHostChannel(
            authenticated_peer=_authenticated_peer(GuestAgentPeerRole.HOST)
        )
        guest_channel = GuestAgentAuthenticatedSignedDispatchGuestChannel(
            authenticated_peer=_authenticated_peer(GuestAgentPeerRole.GUEST)
        )
        envelope = _sample_envelope()
        payload = host_channel.encode_signed_dispatch(envelope)
        self.assertIsInstance(payload, bytes)
        self.assertEqual(guest_channel.decode_signed_dispatch(payload), envelope)

    def test_guest_encodes_and_host_decodes_the_same_response(self) -> None:
        host_channel = GuestAgentAuthenticatedSignedDispatchHostChannel(
            authenticated_peer=_authenticated_peer(GuestAgentPeerRole.HOST)
        )
        guest_channel = GuestAgentAuthenticatedSignedDispatchGuestChannel(
            authenticated_peer=_authenticated_peer(GuestAgentPeerRole.GUEST)
        )
        response = _sample_response()
        payload = guest_channel.encode_response(response)
        self.assertIsInstance(payload, bytes)
        self.assertEqual(host_channel.decode_response(payload), response)


class FailClosedMethodInputTests(unittest.TestCase):
    def test_host_encode_rejects_non_envelope(self) -> None:
        host_channel = GuestAgentAuthenticatedSignedDispatchHostChannel(
            authenticated_peer=_authenticated_peer(GuestAgentPeerRole.HOST)
        )
        for bad in (None, "not an envelope", _sample_request(), 123):
            with self.subTest(value=bad):
                with self.assertRaises(ResearchError):
                    host_channel.encode_signed_dispatch(bad)  # type: ignore[arg-type]

    def test_guest_encode_response_rejects_non_response(self) -> None:
        guest_channel = GuestAgentAuthenticatedSignedDispatchGuestChannel(
            authenticated_peer=_authenticated_peer(GuestAgentPeerRole.GUEST)
        )
        for bad in (None, "not a response", _sample_request(), 123):
            with self.subTest(value=bad):
                with self.assertRaises(ResearchError):
                    guest_channel.encode_response(bad)  # type: ignore[arg-type]

    def test_guest_decode_signed_dispatch_rejects_malformed_bytes(self) -> None:
        guest_channel = GuestAgentAuthenticatedSignedDispatchGuestChannel(
            authenticated_peer=_authenticated_peer(GuestAgentPeerRole.GUEST)
        )
        with self.assertRaises(ResearchError):
            guest_channel.decode_signed_dispatch(b"not json at all")

    def test_host_decode_response_rejects_malformed_bytes(self) -> None:
        host_channel = GuestAgentAuthenticatedSignedDispatchHostChannel(
            authenticated_peer=_authenticated_peer(GuestAgentPeerRole.HOST)
        )
        with self.assertRaises(ResearchError):
            host_channel.decode_response(b"not json at all")


class DirectionalityStructuralTests(unittest.TestCase):
    """Wrong-direction methods are structurally absent, not merely unused."""

    def test_host_channel_has_no_guest_direction_methods(self) -> None:
        host_methods = {
            name
            for name in dir(GuestAgentAuthenticatedSignedDispatchHostChannel)
            if not name.startswith("_")
        }
        self.assertNotIn("decode_signed_dispatch", host_methods)
        self.assertNotIn("encode_response", host_methods)

    def test_guest_channel_has_no_host_direction_methods(self) -> None:
        guest_methods = {
            name
            for name in dir(GuestAgentAuthenticatedSignedDispatchGuestChannel)
            if not name.startswith("_")
        }
        self.assertNotIn("encode_signed_dispatch", guest_methods)
        self.assertNotIn("decode_response", guest_methods)


class StructuralSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tree = ast.parse(
            CHANNEL_MODULE_FILE.read_text(encoding="utf-8"),
            filename=str(CHANNEL_MODULE_FILE),
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

    def test_no_network_or_process_reference(self) -> None:
        forbidden = {"socket", "ssl", "subprocess"}
        self.assertEqual(self._referenced_names(self.tree) & forbidden, set())

    def test_no_verification_or_execution_authority_reference(self) -> None:
        forbidden = {
            "verify_signed_dispatch_envelope",
            "admit_guest_agent_request",
            "consume_once",
            "KaliToolGateway",
        }
        self.assertEqual(self._referenced_names(self.tree) & forbidden, set())


if __name__ == "__main__":
    unittest.main()
