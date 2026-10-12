"""Pure in-memory, role-direction-bound Guest-Agent protocol channel wrapper.

AUTHENTICATED CHANNEL != EXECUTION AUTHORITY. AUTHENTICATED CHANNEL !=
OPERATION AUTHORIZATION. PROTOCOL REQUEST != EXECUTION AUTHORITY. This
module only governs which protocol objects may cross an already-
authenticated application identity boundary, and in which direction. A
message crossing that boundary is never execution permission: neither
channel type here is wired into the Kali tool gateway, the tool execution
layer, cognition, chat, or the desktop, and no method on either channel
can cause an operation to run.

There is no network transport here. No `socket.socket`, no
`ssl.SSLSocket`, no file descriptor, and no handshake of any kind appears
anywhere in this module; both channel types only ever accept and return
`bytes` or the existing in-memory `GuestAgentRequest`/`GuestAgentResponse`
protocol objects (reusing
`research.GuestAgentProtocolSerialization`'s existing codec functions,
never reimplementing them).

Each channel type can only be constructed from a real
`research.GuestAgentPeerAuthenticator.GuestAgentAuthenticatedPeer` --
which itself can only be produced by a successful `authenticate_peer`
call -- so an unauthenticated caller has no way to obtain one. A channel
constructed with a peer whose `own_role` does not match the channel type
also fails closed at construction, never at first use.

The two roles are deliberately asymmetric, not one general bidirectional
pipe: a host-side channel can only encode an outgoing
`GuestAgentRequest` (host -> guest) and decode an incoming
`GuestAgentResponse` (guest -> host); the reverse operations simply do not
exist as methods on it. A guest-side channel is the mirror image. This
makes wrong-direction protocol objects a structural impossibility rather
than a runtime check that could be forgotten.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.GuestAgentMtlsTrustConfiguration import GuestAgentPeerRole
from research.GuestAgentPeerAuthenticator import GuestAgentAuthenticatedPeer
from research.GuestAgentProtocol import GuestAgentRequest, GuestAgentResponse
from research.GuestAgentProtocolSerialization import (
    canonical_guest_agent_request_bytes,
    canonical_guest_agent_response_bytes,
    guest_agent_request_from_bytes,
    guest_agent_response_from_bytes,
)


@dataclass(frozen=True, slots=True)
class GuestAgentAuthenticatedHostChannel:
    """Host-side channel: encode outgoing requests, decode incoming responses.

    Not execution authority; see module docstring. Requires a peer
    authenticated with `own_role == HOST`.
    """

    authenticated_peer: GuestAgentAuthenticatedPeer

    def __post_init__(self) -> None:
        if not isinstance(self.authenticated_peer, GuestAgentAuthenticatedPeer):
            raise ResearchError(
                "Guest-agent host channel requires an authenticated peer."
            )
        if self.authenticated_peer.own_role is not GuestAgentPeerRole.HOST:
            raise ResearchError(
                "Guest-agent host channel requires a host-authenticated peer."
            )

    def encode_request(self, request: GuestAgentRequest) -> bytes:
        """Serialize an outgoing host -> guest request. Not execution authority."""
        if not isinstance(request, GuestAgentRequest):
            raise ResearchError(
                "Guest-agent host channel requires a request to encode."
            )
        return canonical_guest_agent_request_bytes(request)

    def decode_response(self, data: bytes) -> GuestAgentResponse:
        """Parse an incoming guest -> host response. Not execution authority."""
        return guest_agent_response_from_bytes(data)


@dataclass(frozen=True, slots=True)
class GuestAgentAuthenticatedGuestChannel:
    """Guest-side channel: decode incoming requests, encode outgoing responses.

    Not execution authority; see module docstring. Requires a peer
    authenticated with `own_role == GUEST`.
    """

    authenticated_peer: GuestAgentAuthenticatedPeer

    def __post_init__(self) -> None:
        if not isinstance(self.authenticated_peer, GuestAgentAuthenticatedPeer):
            raise ResearchError(
                "Guest-agent guest channel requires an authenticated peer."
            )
        if self.authenticated_peer.own_role is not GuestAgentPeerRole.GUEST:
            raise ResearchError(
                "Guest-agent guest channel requires a guest-authenticated peer."
            )

    def decode_request(self, data: bytes) -> GuestAgentRequest:
        """Parse an incoming host -> guest request. Not execution authority."""
        return guest_agent_request_from_bytes(data)

    def encode_response(self, response: GuestAgentResponse) -> bytes:
        """Serialize an outgoing guest -> host response. Not execution authority."""
        if not isinstance(response, GuestAgentResponse):
            raise ResearchError(
                "Guest-agent guest channel requires a response to encode."
            )
        return canonical_guest_agent_response_bytes(response)
