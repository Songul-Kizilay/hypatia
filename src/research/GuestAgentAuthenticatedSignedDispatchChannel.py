"""Pure in-memory, role-direction-bound signed-dispatch channel wrapper.

Sibling to `research.GuestAgentAuthenticatedChannel`, not a replacement for
it: that module remains byte-for-byte unmodified and still governs the
plain `GuestAgentRequest`/`GuestAgentResponse` pair. This module governs a
different, strictly more constrained pair -- a HOST -> GUEST
`GuestAgentSignedDispatchEnvelope` and the unchanged GUEST -> HOST
`GuestAgentResponse` -- because the milestone that introduces signed
dispatch never widens what a plain `GuestAgentAuthenticatedHostChannel`/
`GuestAgentAuthenticatedGuestChannel` may carry.

AUTHENTICATED CHANNEL != EXECUTION AUTHORITY. AUTHENTICATED CHANNEL !=
VERIFIED DISPATCH. AUTHENTICATED CHANNEL != OPERATION AUTHORIZATION. This
module only governs which protocol objects may cross an already-
authenticated application identity boundary, and in which direction;
decoding a `GuestAgentSignedDispatchEnvelope` off this channel proves
nothing about whether its proof is cryptographically valid -- that is
`research.GuestAgentDispatchVerification.verify_signed_dispatch_envelope`'s
job alone, called separately by whoever holds a decoded envelope.

There is no network transport here, exactly like its sibling module: no
`socket.socket`, no `ssl.SSLSocket`, no file descriptor, no handshake.
Both channel types only accept and return `bytes` or the existing
in-memory `GuestAgentSignedDispatchEnvelope`/`GuestAgentResponse`
objects, reusing `research.GuestAgentSignedDispatchSerialization` and
`research.GuestAgentProtocolSerialization`'s existing codec functions,
never reimplementing either.

Each channel type can only be constructed from a real
`research.GuestAgentPeerAuthenticator.GuestAgentAuthenticatedPeer`, and a
channel constructed with a peer whose `own_role` does not match the
channel type fails closed at construction -- the exact same guarantee
`GuestAgentAuthenticatedHostChannel`/`GuestAgentAuthenticatedGuestChannel`
already make. The two roles are asymmetric: a host-side channel can only
encode an outgoing envelope and decode an incoming response; a guest-side
channel is the mirror image. There is no bidirectional method on either.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.GuestAgentDispatchProof import GuestAgentSignedDispatchEnvelope
from research.GuestAgentMtlsTrustConfiguration import GuestAgentPeerRole
from research.GuestAgentPeerAuthenticator import GuestAgentAuthenticatedPeer
from research.GuestAgentProtocol import GuestAgentResponse
from research.GuestAgentProtocolSerialization import (
    canonical_guest_agent_response_bytes,
    guest_agent_response_from_bytes,
)
from research.GuestAgentSignedDispatchSerialization import (
    canonical_guest_agent_signed_dispatch_envelope_bytes,
    guest_agent_signed_dispatch_envelope_from_bytes,
)


@dataclass(frozen=True, slots=True)
class GuestAgentAuthenticatedSignedDispatchHostChannel:
    """Host-side channel: encode outgoing envelopes, decode incoming responses.

    Not execution authority; see module docstring. Requires a peer
    authenticated with `own_role == HOST`.
    """

    authenticated_peer: GuestAgentAuthenticatedPeer

    def __post_init__(self) -> None:
        if not isinstance(self.authenticated_peer, GuestAgentAuthenticatedPeer):
            raise ResearchError(
                "Guest-agent signed dispatch host channel requires an "
                "authenticated peer."
            )
        if self.authenticated_peer.own_role is not GuestAgentPeerRole.HOST:
            raise ResearchError(
                "Guest-agent signed dispatch host channel requires a "
                "host-authenticated peer."
            )

    def encode_signed_dispatch(
        self, envelope: GuestAgentSignedDispatchEnvelope
    ) -> bytes:
        """Serialize an outgoing host -> guest signed dispatch envelope.

        Not execution authority; not a signature check -- see module
        docstring.
        """
        if not isinstance(envelope, GuestAgentSignedDispatchEnvelope):
            raise ResearchError(
                "Guest-agent signed dispatch host channel requires an "
                "envelope to encode."
            )
        return canonical_guest_agent_signed_dispatch_envelope_bytes(envelope)

    def decode_response(self, data: bytes) -> GuestAgentResponse:
        """Parse an incoming guest -> host response. Not execution authority."""
        return guest_agent_response_from_bytes(data)


@dataclass(frozen=True, slots=True)
class GuestAgentAuthenticatedSignedDispatchGuestChannel:
    """Guest-side channel: decode incoming envelopes, encode outgoing responses.

    Not execution authority; see module docstring. Requires a peer
    authenticated with `own_role == GUEST`.
    """

    authenticated_peer: GuestAgentAuthenticatedPeer

    def __post_init__(self) -> None:
        if not isinstance(self.authenticated_peer, GuestAgentAuthenticatedPeer):
            raise ResearchError(
                "Guest-agent signed dispatch guest channel requires an "
                "authenticated peer."
            )
        if self.authenticated_peer.own_role is not GuestAgentPeerRole.GUEST:
            raise ResearchError(
                "Guest-agent signed dispatch guest channel requires a "
                "guest-authenticated peer."
            )

    def decode_signed_dispatch(self, data: bytes) -> GuestAgentSignedDispatchEnvelope:
        """Parse an incoming host -> guest signed dispatch envelope.

        Not execution authority; not a signature check -- see module
        docstring. The returned envelope has not been cryptographically
        verified; that remains a separate, later step a caller must
        perform before trusting anything about it.
        """
        return guest_agent_signed_dispatch_envelope_from_bytes(data)

    def encode_response(self, response: GuestAgentResponse) -> bytes:
        """Serialize an outgoing guest -> host response. Not execution authority."""
        if not isinstance(response, GuestAgentResponse):
            raise ResearchError(
                "Guest-agent signed dispatch guest channel requires a "
                "response to encode."
            )
        return canonical_guest_agent_response_bytes(response)
