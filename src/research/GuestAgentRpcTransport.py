"""A real, authenticated, loopback-only, one-request/one-response RPC transport.

TRANSPORT DELIVERY != EXECUTION AUTHORITY. This module only answers "can this
already-typed `GuestAgentRequest`/`GuestAgentResponse` be carried between the
expected authenticated peers over a real mTLS TLS 1.3 loopback socket" --
never "may the requested operation execute." It is the first bounded
implementation of roadmap step 4 (Guest-Agent RPC transport), not the real
Kali Guest Agent, not VMware/SSH/WSL, and not any capability dispatcher.
Nothing here is wired into `KaliToolGateway`, the tool execution layer,
`Bootstrap`, `CognitiveEngine`, chat, or the desktop; this module has zero
production callers today.

Every security-relevant building block is reused unmodified, never
duplicated: strict mTLS context construction
(`research.GuestAgentMtlsContext.build_host_client_tls_context`/
`build_guest_server_tls_context`), real peer-certificate identity extraction
(`research.GuestAgentPeerCertificateIdentity.parse_peer_certificate_identity`),
application-identity enforcement
(`research.GuestAgentPeerAuthenticator.authenticate_peer`), the role-
direction-bound authenticated channel wrappers
(`research.GuestAgentAuthenticatedChannel.GuestAgentAuthenticatedHostChannel`/
`GuestAgentAuthenticatedGuestChannel` -- which themselves reuse the existing
canonical codec in `research.GuestAgentProtocolSerialization`, never
reimplemented here), and the bounded wire framing in
`research.GuestAgentRpcFraming`.

Ordering is load-bearing and structurally enforced, never merely assumed: on
both the client and the server side, `_authenticate_tls_peer` -- the one
shared helper both roles call -- must return a real
`GuestAgentAuthenticatedPeer` before either side ever reads a length-
prefixed application frame off the socket. Peer authentication failure
raises before any `read_guest_agent_rpc_frame` call is reached.

This transport performs replay-identity consumption for NOBODY: it never
imports or calls `research.GuestAgentReplayProtector.GuestAgentReplayProtector
.consume_once`, or anything from the replay nonce store modules. A received
request's one-time replay identity is left exactly as unconsumed as before
transport delivery -- consuming it remains a decision for whatever future
layer actually holds execution authority, never this transport's job.

Loopback-only by construction: `GUEST_AGENT_RPC_LOOPBACK_HOST` is the one
literal host either side may ever use, and it is never exposed as a
caller-configurable parameter anywhere in this module's public API --
`GuestAgentRpcClient` takes only a `port`, `GuestAgentRpcServer.bind` always
binds `(GUEST_AGENT_RPC_LOOPBACK_HOST, 0)` (an OS-assigned ephemeral port,
never a fixed one). This structurally forecloses wildcard, LAN, or external
binding.

`GuestAgentRpcServer.serve_one_request` is genuinely one-shot, not merely
convention: it accepts exactly one connection and immediately closes the
listening socket (so this server instance can structurally never accept a
second connection), and contains no loop of any kind -- it reads exactly one
request frame and, on success, sends exactly one response frame, then
returns. `GuestAgentRpcClient.send_request` contains no retry loop either: a
failed call simply raises; the caller decides whether, and how, to try
again, and this milestone builds no such retry policy.

Error hygiene: every exception this module raises on a failure path is
`GuestAgentRpcTransportError`, carrying a closed `GuestAgentRpcFailureKind`
and one of this module's own fixed, code-owned sentences -- never
certificate contents, private key paths, SAN values, nonce values, operation
digests, raw protocol payload bytes, or `str(handler_exception)`. A request
handler's own exception is caught and converted to a fixed `HANDLER_FAILED`
error; its text is never sent to the peer and never appears in the raised
error's own message.
"""

from __future__ import annotations

import socket
import ssl
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

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
from research.GuestAgentPeerCertificateIdentity import parse_peer_certificate_identity
from research.GuestAgentProtocol import GuestAgentRequest, GuestAgentResponse
from research.GuestAgentRpcFraming import (
    GuestAgentRpcFramingError,
    read_guest_agent_rpc_frame,
    write_guest_agent_rpc_frame,
)

#: The one literal loopback host either role may ever use. Never exposed as
#: a configurable parameter anywhere in this module's public API.
GUEST_AGENT_RPC_LOOPBACK_HOST = "127.0.0.1"

_MAX_TIMEOUT_SECONDS = 30.0


class GuestAgentRpcFailureKind(StrEnum):
    """The smallest closed set of ways one RPC call can fail.

    Never a raw string compare anywhere a caller decides what went wrong --
    always this enum, carried on `GuestAgentRpcTransportError.kind`.
    """

    CONNECTION_FAILED = "connection_failed"
    HANDSHAKE_FAILED = "handshake_failed"
    PEER_AUTHENTICATION_FAILED = "peer_authentication_failed"
    FRAME_INVALID = "frame_invalid"
    PROTOCOL_DECODE_INVALID = "protocol_decode_invalid"
    CORRELATION_FAILED = "correlation_failed"
    HANDLER_FAILED = "handler_failed"


_FAILURE_MESSAGES: dict[GuestAgentRpcFailureKind, str] = {
    GuestAgentRpcFailureKind.CONNECTION_FAILED: (
        "Guest-agent RPC connection could not be established."
    ),
    GuestAgentRpcFailureKind.HANDSHAKE_FAILED: (
        "Guest-agent RPC TLS handshake failed."
    ),
    GuestAgentRpcFailureKind.PEER_AUTHENTICATION_FAILED: (
        "Guest-agent RPC peer authentication failed."
    ),
    GuestAgentRpcFailureKind.FRAME_INVALID: ("Guest-agent RPC frame was invalid."),
    GuestAgentRpcFailureKind.PROTOCOL_DECODE_INVALID: (
        "Guest-agent RPC protocol payload could not be decoded."
    ),
    GuestAgentRpcFailureKind.CORRELATION_FAILED: (
        "Guest-agent RPC response did not correlate with its request."
    ),
    GuestAgentRpcFailureKind.HANDLER_FAILED: (
        "Guest-agent RPC request handler failed."
    ),
}


class GuestAgentRpcTransportError(ResearchError):
    """One RPC transport failure. Carries a closed `kind`, never raw detail.

    The exception message is always one of this module's own fixed, code-
    owned sentences (`_FAILURE_MESSAGES`) -- never built from, or including,
    certificate contents, private key paths, raw protocol payload bytes, SAN
    values, nonce values, operation digests, or `str(handler_exception)`.
    """

    def __init__(self, kind: GuestAgentRpcFailureKind) -> None:
        super().__init__(_FAILURE_MESSAGES[kind])
        self.kind = kind


@dataclass(frozen=True, slots=True)
class GuestAgentRpcTransportTimeouts:
    """Explicit, positive, bounded timeouts for every blocking socket step.

    `write_seconds` bounds both this transport's write operations AND the
    server's `accept()` wait -- the one shared "waiting on the other side to
    act" timeout the milestone's own write/accept grouping names, rather
    than inventing a fifth, separately-tunable field for a wait that is not
    materially different in kind. No field may exceed `30.0`, matching this
    project's own existing loopback-handshake test precedent
    (`tests/research/test_guest_agent_loopback_mtls_handshake.py`'s bounded-
    timeout assertion); no field may be zero or negative -- there is no
    infinite wait anywhere this type's values are used.
    """

    connect_seconds: float = 5.0
    handshake_seconds: float = 5.0
    read_seconds: float = 5.0
    write_seconds: float = 5.0

    def __post_init__(self) -> None:
        for value, label in (
            (self.connect_seconds, "connect timeout"),
            (self.handshake_seconds, "handshake timeout"),
            (self.read_seconds, "read timeout"),
            (self.write_seconds, "write/accept timeout"),
        ):
            self._require_bounded_timeout(value, label)

    @staticmethod
    def _require_bounded_timeout(value: object, label: str) -> None:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ResearchError(f"Guest-agent RPC {label} must be a number.")
        if not (0.0 < float(value) <= _MAX_TIMEOUT_SECONDS):
            raise ResearchError(
                f"Guest-agent RPC {label} must be positive and bounded."
            )


#: The one shared default timeouts instance both `GuestAgentRpcClient` and
#: `GuestAgentRpcServer` use when a caller supplies none -- a module-level
#: singleton rather than a per-call constructor call in an argument
#: default, since `GuestAgentRpcTransportTimeouts` is frozen and immutable
#: and sharing one instance carries no risk of accidental cross-call state.
_DEFAULT_TIMEOUTS = GuestAgentRpcTransportTimeouts()


#: This handler is NOT a capability dispatcher: it receives only an already-
#: validated typed `GuestAgentRequest` and must return a typed
#: `GuestAgentResponse`. It is injected by the caller (tests, or later inert
#: composition); this module never names, shapes, or calls it like `run`,
#: `execute`, `dispatch_shell`, or `invoke_tool`.
GuestAgentRpcRequestHandler = Callable[[GuestAgentRequest], GuestAgentResponse]


def _authenticate_tls_peer(
    tls_conn: ssl.SSLSocket,
    trust_configuration: GuestAgentMtlsTrustConfiguration,
) -> GuestAgentAuthenticatedPeer:
    """Authenticate the already-handshaken peer; the ONLY gate before framing.

    This function's result is the only thing that may unlock calling
    `research.GuestAgentRpcFraming.read_guest_agent_rpc_frame` -- application
    bytes must never be read from the socket before this succeeds. Reuses
    `parse_peer_certificate_identity`/`authenticate_peer` unmodified; never
    duplicates identity-matching logic.
    """
    cert_dict = tls_conn.getpeercert()
    der_bytes = tls_conn.getpeercert(binary_form=True)
    try:
        observation = parse_peer_certificate_identity(cert_dict, der_bytes=der_bytes)  # type: ignore[arg-type]
    except ResearchError as error:
        raise GuestAgentRpcTransportError(
            GuestAgentRpcFailureKind.PEER_AUTHENTICATION_FAILED
        ) from error
    result = authenticate_peer(observation, trust_configuration)
    if not result.authenticated or result.authenticated_peer is None:
        raise GuestAgentRpcTransportError(
            GuestAgentRpcFailureKind.PEER_AUTHENTICATION_FAILED
        )
    return result.authenticated_peer


class GuestAgentRpcClient:
    """HOST-role client: one authenticated request, one authenticated response.

    Not execution authority; see module docstring. No retry loop anywhere in
    `send_request` or around it.
    """

    def __init__(
        self,
        tls_context: ssl.SSLContext,
        trust_configuration: GuestAgentMtlsTrustConfiguration,
        port: int,
        *,
        timeouts: GuestAgentRpcTransportTimeouts = _DEFAULT_TIMEOUTS,
    ) -> None:
        if not isinstance(tls_context, ssl.SSLContext):
            raise ResearchError(
                "Guest-agent RPC client requires a bounded TLS context."
            )
        if not isinstance(trust_configuration, GuestAgentMtlsTrustConfiguration):
            raise ResearchError(
                "Guest-agent RPC client requires a bounded trust configuration."
            )
        if trust_configuration.own_role is not GuestAgentPeerRole.HOST:
            raise ResearchError(
                "Guest-agent RPC client requires a host-role trust configuration."
            )
        if (
            not isinstance(port, int)
            or isinstance(port, bool)
            or not (0 < port <= 65535)
        ):
            raise ResearchError("Guest-agent RPC client port is invalid.")
        if not isinstance(timeouts, GuestAgentRpcTransportTimeouts):
            raise ResearchError("Guest-agent RPC client timeouts are invalid.")
        self._tls_context = tls_context
        self._trust_configuration = trust_configuration
        self._port = port
        self._timeouts = timeouts

    def send_request(self, request: GuestAgentRequest) -> GuestAgentResponse:
        """Send one request, wait for one response, and return it.

        Opens a fresh loopback socket to `(GUEST_AGENT_RPC_LOOPBACK_HOST,
        port)` every call; never reuses a connection across calls, and never
        retries internally. Always closes the socket before returning or
        raising.
        """
        if not isinstance(request, GuestAgentRequest):
            raise ResearchError("Guest-agent RPC client requires a request to send.")
        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tls_conn: ssl.SSLSocket | None = None
        try:
            raw_sock.settimeout(self._timeouts.connect_seconds)
            try:
                raw_sock.connect((GUEST_AGENT_RPC_LOOPBACK_HOST, self._port))
            except OSError as error:
                raise GuestAgentRpcTransportError(
                    GuestAgentRpcFailureKind.CONNECTION_FAILED
                ) from error

            raw_sock.settimeout(self._timeouts.handshake_seconds)
            try:
                tls_conn = self._tls_context.wrap_socket(raw_sock, server_hostname=None)
            except (ssl.SSLError, OSError) as error:
                raise GuestAgentRpcTransportError(
                    GuestAgentRpcFailureKind.HANDSHAKE_FAILED
                ) from error

            authenticated_peer = _authenticate_tls_peer(
                tls_conn, self._trust_configuration
            )
            channel = GuestAgentAuthenticatedHostChannel(
                authenticated_peer=authenticated_peer
            )
            payload = channel.encode_request(request)

            tls_conn.settimeout(self._timeouts.write_seconds)
            try:
                write_guest_agent_rpc_frame(tls_conn, payload)
            except (GuestAgentRpcFramingError, OSError) as error:
                raise GuestAgentRpcTransportError(
                    GuestAgentRpcFailureKind.FRAME_INVALID
                ) from error

            tls_conn.settimeout(self._timeouts.read_seconds)
            try:
                response_bytes = read_guest_agent_rpc_frame(tls_conn)
            except (GuestAgentRpcFramingError, OSError) as error:
                raise GuestAgentRpcTransportError(
                    GuestAgentRpcFailureKind.FRAME_INVALID
                ) from error

            try:
                response = channel.decode_response(response_bytes)
            except ResearchError as error:
                raise GuestAgentRpcTransportError(
                    GuestAgentRpcFailureKind.PROTOCOL_DECODE_INVALID
                ) from error

            if response.request_id != request.request_id:
                raise GuestAgentRpcTransportError(
                    GuestAgentRpcFailureKind.CORRELATION_FAILED
                )
            return response
        finally:
            (tls_conn or raw_sock).close()


class GuestAgentRpcServer:
    """GUEST-role server: one authenticated connection, one request, one response.

    Not execution authority; see module docstring. Contains no loop of any
    kind in `serve_one_request` -- it reads exactly one request frame and
    sends exactly one response frame, by construction.
    """

    def __init__(
        self,
        tls_context: ssl.SSLContext,
        trust_configuration: GuestAgentMtlsTrustConfiguration,
        handler: GuestAgentRpcRequestHandler,
        *,
        timeouts: GuestAgentRpcTransportTimeouts = _DEFAULT_TIMEOUTS,
    ) -> None:
        if not isinstance(tls_context, ssl.SSLContext):
            raise ResearchError(
                "Guest-agent RPC server requires a bounded TLS context."
            )
        if not isinstance(trust_configuration, GuestAgentMtlsTrustConfiguration):
            raise ResearchError(
                "Guest-agent RPC server requires a bounded trust configuration."
            )
        if trust_configuration.own_role is not GuestAgentPeerRole.GUEST:
            raise ResearchError(
                "Guest-agent RPC server requires a guest-role trust configuration."
            )
        if not callable(handler):
            raise ResearchError("Guest-agent RPC server requires a callable handler.")
        if not isinstance(timeouts, GuestAgentRpcTransportTimeouts):
            raise ResearchError("Guest-agent RPC server timeouts are invalid.")
        self._tls_context = tls_context
        self._trust_configuration = trust_configuration
        self._handler = handler
        self._timeouts = timeouts
        self._listen_sock: socket.socket | None = None
        self._has_bound = False

    def bind(self) -> int:
        """Bind an OS-assigned ephemeral loopback port, exactly once.

        Always binds `(GUEST_AGENT_RPC_LOOPBACK_HOST, 0)` -- never a fixed
        port, never a caller-supplied host. A second `bind()` call on the
        same instance always raises, never silently rebinding.
        """
        if self._has_bound:
            raise ResearchError("Guest-agent RPC server may only bind once.")
        self._has_bound = True
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind((GUEST_AGENT_RPC_LOOPBACK_HOST, 0))
        sock.listen(1)
        self._listen_sock = sock
        assigned_port: int = sock.getsockname()[1]
        return assigned_port

    def serve_one_request(self) -> GuestAgentResponse:
        """Accept exactly one connection, serve exactly one request, return.

        Immediately closes the listening socket after `accept()` returns
        (success or failure) -- this server instance can structurally never
        accept a second connection. On any failure before a response is
        sent (including a handler exception, or the handler returning a
        response whose `request_id` does not match the request), the
        connection is closed WITHOUT sending any response bytes.
        """
        if self._listen_sock is None:
            raise ResearchError(
                "Guest-agent RPC server has not been bound, or has already "
                "served its one request."
            )
        listen_sock = self._listen_sock
        self._listen_sock = None
        listen_sock.settimeout(self._timeouts.write_seconds)
        try:
            raw_conn, _peer_address = listen_sock.accept()
        except OSError as error:
            raise GuestAgentRpcTransportError(
                GuestAgentRpcFailureKind.CONNECTION_FAILED
            ) from error
        finally:
            listen_sock.close()

        tls_conn: ssl.SSLSocket | None = None
        try:
            raw_conn.settimeout(self._timeouts.handshake_seconds)
            try:
                tls_conn = self._tls_context.wrap_socket(raw_conn, server_side=True)
            except (ssl.SSLError, OSError) as error:
                raise GuestAgentRpcTransportError(
                    GuestAgentRpcFailureKind.HANDSHAKE_FAILED
                ) from error

            authenticated_peer = _authenticate_tls_peer(
                tls_conn, self._trust_configuration
            )
            channel = GuestAgentAuthenticatedGuestChannel(
                authenticated_peer=authenticated_peer
            )

            tls_conn.settimeout(self._timeouts.read_seconds)
            try:
                request_bytes = read_guest_agent_rpc_frame(tls_conn)
            except (GuestAgentRpcFramingError, OSError) as error:
                raise GuestAgentRpcTransportError(
                    GuestAgentRpcFailureKind.FRAME_INVALID
                ) from error

            try:
                request = channel.decode_request(request_bytes)
            except ResearchError as error:
                raise GuestAgentRpcTransportError(
                    GuestAgentRpcFailureKind.PROTOCOL_DECODE_INVALID
                ) from error

            try:
                response = self._handler(request)
            except Exception as error:  # noqa: BLE001 - handler text must never leak
                raise GuestAgentRpcTransportError(
                    GuestAgentRpcFailureKind.HANDLER_FAILED
                ) from error
            if (
                not isinstance(response, GuestAgentResponse)
                or response.request_id != request.request_id
            ):
                raise GuestAgentRpcTransportError(
                    GuestAgentRpcFailureKind.HANDLER_FAILED
                )

            payload = channel.encode_response(response)
            tls_conn.settimeout(self._timeouts.write_seconds)
            try:
                write_guest_agent_rpc_frame(tls_conn, payload)
            except (GuestAgentRpcFramingError, OSError) as error:
                raise GuestAgentRpcTransportError(
                    GuestAgentRpcFailureKind.FRAME_INVALID
                ) from error
            return response
        finally:
            (tls_conn or raw_conn).close()
