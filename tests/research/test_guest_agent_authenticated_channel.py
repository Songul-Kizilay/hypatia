"""The in-memory, role-direction-bound authenticated channel wrapper, v0.3.459.

AUTHENTICATED CHANNEL != EXECUTION AUTHORITY. AUTHENTICATED CHANNEL !=
OPERATION AUTHORIZATION. A protocol message crossing the identity boundary
is never execution permission. Every test below proves that structurally:
no socket/handshake appears anywhere, the channel cannot be constructed
without a real authenticated peer, and wrong-direction protocol objects are
a structural impossibility rather than a runtime check that could be
forgotten.
"""

from __future__ import annotations

import dataclasses
import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError
from research.GuestAgentAuthenticatedChannel import (
    GuestAgentAuthenticatedGuestChannel,
    GuestAgentAuthenticatedHostChannel,
)
from research.GuestAgentMtlsTrustConfiguration import (
    GuestAgentMtlsTrustConfiguration,
    GuestAgentPeerRole,
)
from research.GuestAgentPeerAuthenticator import (
    GuestAgentAuthenticatedPeer,
    authenticate_peer,
)
from research.GuestAgentPeerCertificateIdentity import (
    GuestAgentPeerCertificateIdentityObservation,
)
from research.GuestAgentProtocol import (
    GuestAgentProtocolVersion,
    GuestAgentRequest,
    GuestAgentResponse,
    GuestAgentResponseStatus,
)
from research.ResearchKaliOperationPreview import ResearchKaliOperationKind

VALID_DIGEST = "a" * 64


def _now() -> datetime:
    """Real current time; `currently_valid` checks genuine wall-clock time."""
    return datetime.now(UTC)


def _observation(
    uri_names: tuple[str, ...],
) -> GuestAgentPeerCertificateIdentityObservation:
    return GuestAgentPeerCertificateIdentityObservation(
        dns_names=(),
        uri_names=uri_names,
        not_before=_now() - timedelta(days=1),
        not_after=_now() + timedelta(days=1),
        fingerprint_sha256=None,
    )


def _trust(own_role: GuestAgentPeerRole) -> GuestAgentMtlsTrustConfiguration:
    return GuestAgentMtlsTrustConfiguration(
        own_role=own_role,
        trusted_ca_certificate_path="/trusted/ca.pem",
        own_certificate_path="/trusted/own.pem",
        own_private_key_path="/trusted/own.key",
    )


def _authenticated_host_peer() -> GuestAgentAuthenticatedPeer:
    result = authenticate_peer(
        _observation(("hypatia-kali-guest-agent/guest/1",)),
        _trust(GuestAgentPeerRole.HOST),
    )
    assert result.authenticated_peer is not None
    return result.authenticated_peer


def _authenticated_guest_peer() -> GuestAgentAuthenticatedPeer:
    result = authenticate_peer(
        _observation(("hypatia-kali-guest-agent/host/1",)),
        _trust(GuestAgentPeerRole.GUEST),
    )
    assert result.authenticated_peer is not None
    return result.authenticated_peer


def _request() -> GuestAgentRequest:
    return GuestAgentRequest(
        protocol_version=GuestAgentProtocolVersion.V1,
        request_id="req-1",
        nonce="nonce-1",
        operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
        operation_digest=VALID_DIGEST,
    )


def _response() -> GuestAgentResponse:
    return GuestAgentResponse(
        protocol_version=GuestAgentProtocolVersion.V1,
        request_id="req-1",
        status=GuestAgentResponseStatus.SUCCESS,
        detail="Completed the reviewed operation.",
    )


class ChannelConstructionRequiresAuthenticatedPeerTests(unittest.TestCase):
    """Requirement: the channel wrapper refuses use without authenticated
    peer state -- it cannot be constructed from anything else."""

    def test_host_channel_accepts_a_host_authenticated_peer(self) -> None:
        channel = GuestAgentAuthenticatedHostChannel(
            authenticated_peer=_authenticated_host_peer()
        )
        self.assertIsInstance(channel, GuestAgentAuthenticatedHostChannel)

    def test_guest_channel_accepts_a_guest_authenticated_peer(self) -> None:
        channel = GuestAgentAuthenticatedGuestChannel(
            authenticated_peer=_authenticated_guest_peer()
        )
        self.assertIsInstance(channel, GuestAgentAuthenticatedGuestChannel)

    def test_host_channel_rejects_a_guest_authenticated_peer(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentAuthenticatedHostChannel(
                authenticated_peer=_authenticated_guest_peer()
            )

    def test_guest_channel_rejects_a_host_authenticated_peer(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentAuthenticatedGuestChannel(
                authenticated_peer=_authenticated_host_peer()
            )

    def test_host_channel_rejects_none(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentAuthenticatedHostChannel(authenticated_peer=None)  # type: ignore[arg-type]

    def test_host_channel_rejects_a_plain_object_impersonating_a_peer(self) -> None:
        class _Forged:
            own_role = GuestAgentPeerRole.HOST

        with self.assertRaises(ResearchError):
            GuestAgentAuthenticatedHostChannel(
                authenticated_peer=_Forged()  # type: ignore[arg-type]
            )

    def test_host_channel_rejects_a_bare_protocol_object_as_a_peer(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentAuthenticatedHostChannel(
                authenticated_peer=_request()  # type: ignore[arg-type]
            )


class ChannelDirectionIsStructurallyEnforcedTests(unittest.TestCase):
    """Requirement: wrong-direction protocol objects are a structural
    impossibility -- the wrong-direction method simply does not exist."""

    def test_host_channel_has_only_the_host_direction_methods(self) -> None:
        channel = GuestAgentAuthenticatedHostChannel(
            authenticated_peer=_authenticated_host_peer()
        )
        self.assertTrue(hasattr(channel, "encode_request"))
        self.assertTrue(hasattr(channel, "decode_response"))
        self.assertFalse(hasattr(channel, "decode_request"))
        self.assertFalse(hasattr(channel, "encode_response"))

    def test_guest_channel_has_only_the_guest_direction_methods(self) -> None:
        channel = GuestAgentAuthenticatedGuestChannel(
            authenticated_peer=_authenticated_guest_peer()
        )
        self.assertTrue(hasattr(channel, "decode_request"))
        self.assertTrue(hasattr(channel, "encode_response"))
        self.assertFalse(hasattr(channel, "encode_request"))
        self.assertFalse(hasattr(channel, "decode_response"))

    def test_host_and_guest_channels_are_not_a_general_bidirectional_pipe(self) -> None:
        """There is no single type offering all four directions; the two
        roles are genuinely separate types, not one type with every
        method available regardless of role."""
        self.assertFalse(
            issubclass(
                GuestAgentAuthenticatedHostChannel, GuestAgentAuthenticatedGuestChannel
            )
        )
        self.assertFalse(
            issubclass(
                GuestAgentAuthenticatedGuestChannel, GuestAgentAuthenticatedHostChannel
            )
        )


class ChannelRoundTripTests(unittest.TestCase):
    """Requirement: pure in-memory encode/decode, reusing existing codecs."""

    def test_host_encoded_request_bytes_decode_back_on_the_guest_side(self) -> None:
        host_channel = GuestAgentAuthenticatedHostChannel(
            authenticated_peer=_authenticated_host_peer()
        )
        guest_channel = GuestAgentAuthenticatedGuestChannel(
            authenticated_peer=_authenticated_guest_peer()
        )
        request = _request()
        encoded = host_channel.encode_request(request)
        self.assertIsInstance(encoded, bytes)
        decoded = guest_channel.decode_request(encoded)
        self.assertEqual(decoded, request)

    def test_guest_encoded_response_bytes_decode_back_on_the_host_side(self) -> None:
        host_channel = GuestAgentAuthenticatedHostChannel(
            authenticated_peer=_authenticated_host_peer()
        )
        guest_channel = GuestAgentAuthenticatedGuestChannel(
            authenticated_peer=_authenticated_guest_peer()
        )
        response = _response()
        encoded = guest_channel.encode_response(response)
        self.assertIsInstance(encoded, bytes)
        decoded = host_channel.decode_response(encoded)
        self.assertEqual(decoded, response)

    def test_host_channel_rejects_a_non_request_object_to_encode(self) -> None:
        host_channel = GuestAgentAuthenticatedHostChannel(
            authenticated_peer=_authenticated_host_peer()
        )
        with self.assertRaises(ResearchError):
            host_channel.encode_request(_response())  # type: ignore[arg-type]

    def test_guest_channel_rejects_a_non_response_object_to_encode(self) -> None:
        guest_channel = GuestAgentAuthenticatedGuestChannel(
            authenticated_peer=_authenticated_guest_peer()
        )
        with self.assertRaises(ResearchError):
            guest_channel.encode_response(_request())  # type: ignore[arg-type]

    def test_decode_of_malformed_bytes_fails_closed(self) -> None:
        host_channel = GuestAgentAuthenticatedHostChannel(
            authenticated_peer=_authenticated_host_peer()
        )
        guest_channel = GuestAgentAuthenticatedGuestChannel(
            authenticated_peer=_authenticated_guest_peer()
        )
        with self.assertRaises(ResearchError):
            host_channel.decode_response(b"not json at all")
        with self.assertRaises(ResearchError):
            guest_channel.decode_request(b"{}")


class ChannelCarriesNoExecutionAuthorityTests(unittest.TestCase):
    """Requirement: a message crossing the boundary is never execution
    permission -- neither channel type has any authority-granting surface."""

    def test_neither_channel_type_has_a_kali_authorization_method(self) -> None:
        forbidden_method_substrings = (
            "authoriz",
            "execute",
            "run_operation",
            "dispatch",
        )
        for channel_type in (
            GuestAgentAuthenticatedHostChannel,
            GuestAgentAuthenticatedGuestChannel,
        ):
            method_names = {
                name for name in dir(channel_type) if not name.startswith("__")
            }
            for forbidden in forbidden_method_substrings:
                with self.subTest(channel_type=channel_type.__name__, token=forbidden):
                    self.assertFalse(any(forbidden in name for name in method_names))

    def test_channel_field_set_contains_only_the_authenticated_peer(self) -> None:
        for channel_type in (
            GuestAgentAuthenticatedHostChannel,
            GuestAgentAuthenticatedGuestChannel,
        ):
            field_names = {field.name for field in dataclasses.fields(channel_type)}
            with self.subTest(channel_type=channel_type.__name__):
                self.assertEqual(field_names, {"authenticated_peer"})

    def test_channels_are_frozen(self) -> None:
        host_channel = GuestAgentAuthenticatedHostChannel(
            authenticated_peer=_authenticated_host_peer()
        )
        with self.assertRaises(dataclasses.FrozenInstanceError):
            host_channel.authenticated_peer = _authenticated_host_peer()  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
