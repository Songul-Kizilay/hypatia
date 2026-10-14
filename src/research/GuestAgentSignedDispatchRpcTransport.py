"""The first real transport composing verify -> admit -> replay-consume.

Carries one real `research.GuestAgentDispatchProof.GuestAgentSignedDispatchEnvelope`
across the existing real loopback mTLS TLS 1.3 socket
(`research.GuestAgentRpcTransport`'s own TLS context construction, peer
authentication, and bounded framing -- reused, never duplicated, never
modified: this module makes zero edits to that file), and, strictly on the
GUEST side and strictly in this order:

    1. real TLS 1.3 mTLS handshake
    2. authenticated expected peer identity
       (`research.GuestAgentRpcTransport._authenticate_tls_peer`, the same
       function the plain transport already calls -- imported, not
       duplicated or modified)
    3. read one bounded application frame
       (`research.GuestAgentRpcFraming.read_guest_agent_rpc_frame`)
    4. strict signed-envelope decode
       (`research.GuestAgentSignedDispatchSerialization
       .guest_agent_signed_dispatch_envelope_from_bytes`)
    5. verify the real Ed25519 dispatch proof
       (`research.GuestAgentDispatchVerification
       .verify_signed_dispatch_envelope`, unmodified)
    6. inert `research.GuestAgentCore.admit_guest_agent_request` admission
       (unmodified)
    7. `research.GuestAgentReplayProtector.GuestAgentReplayProtector
       .consume_once` (unmodified)
    8. one inert, typed `GuestAgentResponse`, and -- only for an
       execution-bound V2 request whose replay identity was just freshly
       accepted -- a discarded `GuestAgentPreparedInvocation`

REPLAY CONSUMPTION MUST NEVER OCCUR BEFORE SIGNATURE VERIFICATION: step 7
is reached only after step 5 has already succeeded, so forged or
unauthenticated traffic can never spend a replay identity. Admission (step
6) happens before replay consumption (step 7) because admission is pure
and side-effect-free -- a request this guest would not admit anyway never
spends a replay identity for it. Neither property is merely a code-review
convention here: `serve_one_signed_dispatch` below calls
`verify_signed_dispatch_envelope` before it calls
`research.GuestAgentInvocationPreparation.prepare_guest_agent_invocation`
(which itself calls `admit_guest_agent_request` before its one
`replay_protector.consume_once` call site, in that literal source order)
-- see that module's own docstring for the full admit -> replay-consume
-> prepare composition, reused here rather than duplicated inline.

v0.3.466 note: step 8 may also produce a `GuestAgentPreparedInvocation`
for a `GuestAgentProtocolVersion.V2` request once replay is
`ACCEPTED` -- PREPARED INVOCATION != EXECUTION AUTHORITY, != RUNTIME
READINESS, != PROCESS CREATION, != EXECUTION SUCCESS. No process is
spawned by preparing one.

v0.3.467 note: when step 8 does produce a prepared invocation, this
server now also calls `research.GuestAgentRuntimeReadiness
.check_guest_agent_runtime_readiness` with it and its own injected
`research.GuestAgentLocalReadiness.GuestAgentLocalReadinessProbe`
-- strictly after replay `ACCEPTED`, strictly before responding. RUNTIME
READY != EXECUTION AUTHORITY: both the resulting readiness receipt and any
`GuestAgentRuntimeReadyInvocation` are discarded exactly like the prepared
invocation already was -- never stored as instance state, never logged,
never passed anywhere else -- and the wire response is unaffected either
way: still `DECLINED` for a first-seen admitted dispatch, regardless of
whether the local probe reports `READY` or `UNAVAILABLE`. This server
holds no "run after ready" callback and gains no generic execution
hook; the default `local_runtime_probe`
(`research.GuestAgentLocalReadiness.UnavailableGuestAgentLocalReadinessProbe`)
fails closed with zero subprocess attempts, exactly like the default
`research.ResearchKaliRuntimeEnvironment.UnavailableResearchKaliRuntimeProbe`
used elsewhere in this repository.

WHY DECLINED REMAINS THE SUCCESSFUL FOUNDATION RESULT: `admit_guest_agent_request`
never returns `SUCCESS` -- no capability executor exists anywhere this
module reaches, by design (see `research.GuestAgentCore`'s own module
docstring). A first-seen, valid, admitted signed dispatch therefore always
produces a `DECLINED` wire response; this module does not, and must not,
invent one that claims otherwise. `UNSUPPORTED_CAPABILITY`/
`INVALID_REQUEST` admission outcomes are returned exactly as
`admit_guest_agent_request` produced them, with zero replay-consumption
call for either, since this milestone must not spend a request's one-time
replay identity on a request this guest would not have admitted anyway.
Only a `DECLINED` admission outcome reaches `replay_protector.consume_once`;
`ACCEPTED` there returns that same `DECLINED` response unchanged,
`ALREADY_CONSUMED` there returns a freshly built `REPLAY_REJECTED`
response instead, with the same `request_id` and empty `output_lines`,
using one fixed, code-owned detail sentence.

DO NOT GENERICIZE THE TRANSPORT: there is no `send_bytes`, `send_payload`,
`serve_bytes`, `dispatch_raw`, or `handle_blob` method anywhere in this
module, no generic serializer registry, and no dynamic message-type
dispatch. `GuestAgentSignedDispatchRpcServer` is constructed with a fixed,
non-overridable processing chain -- unlike the plain
`research.GuestAgentRpcTransport.GuestAgentRpcServer`, it takes no
injectable `handler` callback at all, because this milestone hardcodes
exactly one chain: verify, then admit, then replay-consume, then respond.
There is no capability executor anywhere in this module either: no
`GuestAgentCapabilityExecutor`, no DNS/HTTPS executor, no subprocess/dig/
curl/nmap adapter, and no call to
`research.ResearchKaliOperationProcessAdapter.run` or
`cognition.KaliToolGateway.run`.

Error hygiene mirrors `GuestAgentRpcTransportError` exactly: every
exception this module raises carries a closed
`GuestAgentSignedDispatchRpcFailureKind` and one of this module's own
fixed, code-owned sentences -- never certificate contents, private key
paths, raw envelope bytes, nonce values, operation digests, signature
bytes, or verification-failure detail text. On any failure before step 8
produces a response (handshake, peer authentication, frame, envelope
decode, dispatch verification, or a replay-store failure), the connection
is aborted with no wire response sent at all -- exactly the existing
`GuestAgentRpcServer.serve_one_request` discipline of never sending
partial or defensive response bytes on a failure path.

Loopback-only, one-shot, no retry: reuses
`research.GuestAgentRpcTransport.GUEST_AGENT_RPC_LOOPBACK_HOST`,
`GuestAgentRpcTransportTimeouts`, and
`research.GuestAgentRpcFraming.MAX_GUEST_AGENT_RPC_FRAME_SIZE` unchanged.
`GuestAgentSignedDispatchRpcServer.bind` always binds an OS-assigned
ephemeral loopback port, never a fixed or caller-configurable one;
`serve_one_signed_dispatch` is genuinely one-shot (the listening socket is
closed immediately after `accept()`, before any TLS or application
processing begins); `GuestAgentSignedDispatchRpcClient.send_signed_dispatch`
contains no retry loop.
"""

from __future__ import annotations

import socket
import ssl
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from core.Exceptions import ResearchError
from research.GuestAgentAuthenticatedSignedDispatchChannel import (
    GuestAgentAuthenticatedSignedDispatchGuestChannel,
    GuestAgentAuthenticatedSignedDispatchHostChannel,
)
from research.GuestAgentDispatchProof import GuestAgentSignedDispatchEnvelope
from research.GuestAgentDispatchVerification import (
    GuestAgentDispatchVerificationError,
    verify_signed_dispatch_envelope,
)
from research.GuestAgentInvocationPreparation import prepare_guest_agent_invocation
from research.GuestAgentLocalReadiness import (
    GuestAgentLocalReadinessProbe,
    UnavailableGuestAgentLocalReadinessProbe,
)
from research.GuestAgentMtlsTrustConfiguration import (
    GuestAgentMtlsTrustConfiguration,
    GuestAgentPeerRole,
)
from research.GuestAgentProtocol import GuestAgentResponse
from research.GuestAgentReplayProtector import GuestAgentReplayProtector
from research.GuestAgentRpcFraming import (
    GuestAgentRpcFramingError,
    read_guest_agent_rpc_frame,
    write_guest_agent_rpc_frame,
)
from research.GuestAgentRpcTransport import (
    GUEST_AGENT_RPC_LOOPBACK_HOST,
    GuestAgentRpcTransportTimeouts,
    _authenticate_tls_peer,
)
from research.GuestAgentRuntimeReadiness import check_guest_agent_runtime_readiness

#: Reusing the one shared default timeouts type, never a second one: this
#: module's own timing needs (connect/handshake/read/write bounds) are
#: identical in kind to the plain transport's.
_DEFAULT_TIMEOUTS = GuestAgentRpcTransportTimeouts()

#: Fails closed with zero subprocess attempts until a real local adapter is
#: explicitly injected -- mirrors `research.ResearchKaliRuntimeEnvironment
#: .UnavailableResearchKaliRuntimeProbe`'s own default-instance pattern.
_DEFAULT_LOCAL_RUNTIME_PROBE = UnavailableGuestAgentLocalReadinessProbe()


class GuestAgentSignedDispatchRpcFailureKind(StrEnum):
    """The smallest closed set of ways one signed-dispatch RPC call can fail.

    A separate, fully self-contained error model from
    `research.GuestAgentRpcTransport.GuestAgentRpcFailureKind` -- not an
    extension of that enum -- so the tested plain-transport module and its
    existing exhaustiveness are never touched by this milestone.
    """

    CONNECTION_FAILED = "connection_failed"
    HANDSHAKE_FAILED = "handshake_failed"
    PEER_AUTHENTICATION_FAILED = "peer_authentication_failed"
    FRAME_INVALID = "frame_invalid"
    ENVELOPE_DECODE_INVALID = "envelope_decode_invalid"
    DISPATCH_VERIFICATION_FAILED = "dispatch_verification_failed"
    REPLAY_CONSUMPTION_FAILED = "replay_consumption_failed"
    PROTOCOL_DECODE_INVALID = "protocol_decode_invalid"
    CORRELATION_FAILED = "correlation_failed"


_FAILURE_MESSAGES: dict[GuestAgentSignedDispatchRpcFailureKind, str] = {
    GuestAgentSignedDispatchRpcFailureKind.CONNECTION_FAILED: (
        "Guest-agent signed dispatch RPC connection could not be established."
    ),
    GuestAgentSignedDispatchRpcFailureKind.HANDSHAKE_FAILED: (
        "Guest-agent signed dispatch RPC TLS handshake failed."
    ),
    GuestAgentSignedDispatchRpcFailureKind.PEER_AUTHENTICATION_FAILED: (
        "Guest-agent signed dispatch RPC peer authentication failed."
    ),
    GuestAgentSignedDispatchRpcFailureKind.FRAME_INVALID: (
        "Guest-agent signed dispatch RPC frame was invalid."
    ),
    GuestAgentSignedDispatchRpcFailureKind.ENVELOPE_DECODE_INVALID: (
        "Guest-agent signed dispatch envelope could not be decoded."
    ),
    GuestAgentSignedDispatchRpcFailureKind.DISPATCH_VERIFICATION_FAILED: (
        "Guest-agent signed dispatch proof could not be verified."
    ),
    GuestAgentSignedDispatchRpcFailureKind.REPLAY_CONSUMPTION_FAILED: (
        "Guest-agent signed dispatch replay consumption failed."
    ),
    GuestAgentSignedDispatchRpcFailureKind.PROTOCOL_DECODE_INVALID: (
        "Guest-agent signed dispatch RPC response could not be decoded."
    ),
    GuestAgentSignedDispatchRpcFailureKind.CORRELATION_FAILED: (
        "Guest-agent signed dispatch RPC response did not correlate with "
        "its request."
    ),
}


class GuestAgentSignedDispatchRpcTransportError(ResearchError):
    """One signed-dispatch RPC transport failure. Carries a closed `kind`.

    The exception message is always one of this module's own fixed,
    code-owned sentences -- never certificate contents, private key paths,
    raw envelope bytes, nonce values, operation digests, or signature
    bytes.
    """

    def __init__(self, kind: GuestAgentSignedDispatchRpcFailureKind) -> None:
        super().__init__(_FAILURE_MESSAGES[kind])
        self.kind = kind


class GuestAgentSignedDispatchRpcClient:
    """HOST-role client: send one signed dispatch envelope, get one response.

    Accepts only a real, already-signed `GuestAgentSignedDispatchEnvelope`
    -- this client performs no signing, loads no signing key, and contains
    no retry loop anywhere in `send_signed_dispatch` or around it.
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
                "Guest-agent signed dispatch RPC client requires a bounded "
                "TLS context."
            )
        if not isinstance(trust_configuration, GuestAgentMtlsTrustConfiguration):
            raise ResearchError(
                "Guest-agent signed dispatch RPC client requires a bounded "
                "trust configuration."
            )
        if trust_configuration.own_role is not GuestAgentPeerRole.HOST:
            raise ResearchError(
                "Guest-agent signed dispatch RPC client requires a "
                "host-role trust configuration."
            )
        if (
            not isinstance(port, int)
            or isinstance(port, bool)
            or not (0 < port <= 65535)
        ):
            raise ResearchError(
                "Guest-agent signed dispatch RPC client port is invalid."
            )
        if not isinstance(timeouts, GuestAgentRpcTransportTimeouts):
            raise ResearchError(
                "Guest-agent signed dispatch RPC client timeouts are invalid."
            )
        self._tls_context = tls_context
        self._trust_configuration = trust_configuration
        self._port = port
        self._timeouts = timeouts

    def send_signed_dispatch(
        self, envelope: GuestAgentSignedDispatchEnvelope
    ) -> GuestAgentResponse:
        """Send one signed dispatch envelope, wait for one response, return it.

        Opens a fresh loopback socket every call; never reuses a
        connection across calls, and never retries internally. Always
        closes the socket before returning or raising.
        """
        if not isinstance(envelope, GuestAgentSignedDispatchEnvelope):
            raise ResearchError(
                "Guest-agent signed dispatch RPC client requires an "
                "envelope to send."
            )
        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tls_conn: ssl.SSLSocket | None = None
        try:
            raw_sock.settimeout(self._timeouts.connect_seconds)
            try:
                raw_sock.connect((GUEST_AGENT_RPC_LOOPBACK_HOST, self._port))
            except OSError as error:
                raise GuestAgentSignedDispatchRpcTransportError(
                    GuestAgentSignedDispatchRpcFailureKind.CONNECTION_FAILED
                ) from error

            raw_sock.settimeout(self._timeouts.handshake_seconds)
            try:
                tls_conn = self._tls_context.wrap_socket(raw_sock, server_hostname=None)
            except (ssl.SSLError, OSError) as error:
                raise GuestAgentSignedDispatchRpcTransportError(
                    GuestAgentSignedDispatchRpcFailureKind.HANDSHAKE_FAILED
                ) from error

            try:
                authenticated_peer = _authenticate_tls_peer(
                    tls_conn, self._trust_configuration
                )
            except ResearchError as error:
                raise GuestAgentSignedDispatchRpcTransportError(
                    GuestAgentSignedDispatchRpcFailureKind.PEER_AUTHENTICATION_FAILED
                ) from error
            channel = GuestAgentAuthenticatedSignedDispatchHostChannel(
                authenticated_peer=authenticated_peer
            )
            payload = channel.encode_signed_dispatch(envelope)

            tls_conn.settimeout(self._timeouts.write_seconds)
            try:
                write_guest_agent_rpc_frame(tls_conn, payload)
            except (GuestAgentRpcFramingError, OSError) as error:
                raise GuestAgentSignedDispatchRpcTransportError(
                    GuestAgentSignedDispatchRpcFailureKind.FRAME_INVALID
                ) from error

            tls_conn.settimeout(self._timeouts.read_seconds)
            try:
                response_bytes = read_guest_agent_rpc_frame(tls_conn)
            except (GuestAgentRpcFramingError, OSError) as error:
                raise GuestAgentSignedDispatchRpcTransportError(
                    GuestAgentSignedDispatchRpcFailureKind.FRAME_INVALID
                ) from error

            try:
                response = channel.decode_response(response_bytes)
            except ResearchError as error:
                raise GuestAgentSignedDispatchRpcTransportError(
                    GuestAgentSignedDispatchRpcFailureKind.PROTOCOL_DECODE_INVALID
                ) from error

            if response.request_id != envelope.request.request_id:
                raise GuestAgentSignedDispatchRpcTransportError(
                    GuestAgentSignedDispatchRpcFailureKind.CORRELATION_FAILED
                )
            return response
        finally:
            (tls_conn or raw_sock).close()


class GuestAgentSignedDispatchRpcServer:
    """GUEST-role server: verify -> admit -> replay-consume -> respond.

    Not execution authority; see module docstring. Takes no injectable
    `handler` -- the processing chain is fixed and non-overridable.
    Contains no loop of any kind in `serve_one_signed_dispatch`: it reads
    exactly one frame and, on success, sends exactly one response frame,
    then returns.
    """

    def __init__(
        self,
        tls_context: ssl.SSLContext,
        trust_configuration: GuestAgentMtlsTrustConfiguration,
        *,
        verification_key: Ed25519PublicKey,
        replay_protector: GuestAgentReplayProtector,
        timeouts: GuestAgentRpcTransportTimeouts = _DEFAULT_TIMEOUTS,
        clock: Callable[[], datetime] | None = None,
        local_runtime_probe: (
            GuestAgentLocalReadinessProbe
        ) = _DEFAULT_LOCAL_RUNTIME_PROBE,
    ) -> None:
        if not isinstance(tls_context, ssl.SSLContext):
            raise ResearchError(
                "Guest-agent signed dispatch RPC server requires a bounded "
                "TLS context."
            )
        if not isinstance(trust_configuration, GuestAgentMtlsTrustConfiguration):
            raise ResearchError(
                "Guest-agent signed dispatch RPC server requires a bounded "
                "trust configuration."
            )
        if trust_configuration.own_role is not GuestAgentPeerRole.GUEST:
            raise ResearchError(
                "Guest-agent signed dispatch RPC server requires a "
                "guest-role trust configuration."
            )
        if not isinstance(verification_key, Ed25519PublicKey):
            raise ResearchError(
                "Guest-agent signed dispatch RPC server requires a real "
                "Ed25519 public key."
            )
        if not isinstance(replay_protector, GuestAgentReplayProtector):
            raise ResearchError(
                "Guest-agent signed dispatch RPC server requires a bounded "
                "replay protector."
            )
        if not isinstance(timeouts, GuestAgentRpcTransportTimeouts):
            raise ResearchError(
                "Guest-agent signed dispatch RPC server timeouts are invalid."
            )
        if not isinstance(local_runtime_probe, GuestAgentLocalReadinessProbe):
            raise ResearchError(
                "Guest-agent signed dispatch RPC server requires a bounded "
                "local runtime readiness probe."
            )
        self._tls_context = tls_context
        self._trust_configuration = trust_configuration
        self._verification_key = verification_key
        self._replay_protector = replay_protector
        self._timeouts = timeouts
        self._clock = clock or (lambda: datetime.now(UTC))
        self._local_runtime_probe = local_runtime_probe
        self._listen_sock: socket.socket | None = None
        self._has_bound = False

    def bind(self) -> int:
        """Bind an OS-assigned ephemeral loopback port, exactly once."""
        if self._has_bound:
            raise ResearchError(
                "Guest-agent signed dispatch RPC server may only bind once."
            )
        self._has_bound = True
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind((GUEST_AGENT_RPC_LOOPBACK_HOST, 0))
        sock.listen(1)
        self._listen_sock = sock
        assigned_port: int = sock.getsockname()[1]
        return assigned_port

    def serve_one_signed_dispatch(self) -> GuestAgentResponse:
        """Accept exactly one connection, process exactly one dispatch, return.

        Immediately closes the listening socket after `accept()` returns
        (success or failure). On any failure before step 8 (handshake,
        peer authentication, frame, envelope decode, dispatch
        verification, or a replay-store failure), the connection is
        closed WITHOUT sending any response bytes -- replay consumption is
        never reached before verification succeeds, by source order.
        """
        if self._listen_sock is None:
            raise ResearchError(
                "Guest-agent signed dispatch RPC server has not been "
                "bound, or has already served its one request."
            )
        listen_sock = self._listen_sock
        self._listen_sock = None
        listen_sock.settimeout(self._timeouts.write_seconds)
        try:
            raw_conn, _peer_address = listen_sock.accept()
        except OSError as error:
            raise GuestAgentSignedDispatchRpcTransportError(
                GuestAgentSignedDispatchRpcFailureKind.CONNECTION_FAILED
            ) from error
        finally:
            listen_sock.close()

        tls_conn: ssl.SSLSocket | None = None
        try:
            raw_conn.settimeout(self._timeouts.handshake_seconds)
            try:
                tls_conn = self._tls_context.wrap_socket(raw_conn, server_side=True)
            except (ssl.SSLError, OSError) as error:
                raise GuestAgentSignedDispatchRpcTransportError(
                    GuestAgentSignedDispatchRpcFailureKind.HANDSHAKE_FAILED
                ) from error

            try:
                authenticated_peer = _authenticate_tls_peer(
                    tls_conn, self._trust_configuration
                )
            except ResearchError as error:
                raise GuestAgentSignedDispatchRpcTransportError(
                    GuestAgentSignedDispatchRpcFailureKind.PEER_AUTHENTICATION_FAILED
                ) from error
            channel = GuestAgentAuthenticatedSignedDispatchGuestChannel(
                authenticated_peer=authenticated_peer
            )

            tls_conn.settimeout(self._timeouts.read_seconds)
            try:
                envelope_bytes = read_guest_agent_rpc_frame(tls_conn)
            except (GuestAgentRpcFramingError, OSError) as error:
                raise GuestAgentSignedDispatchRpcTransportError(
                    GuestAgentSignedDispatchRpcFailureKind.FRAME_INVALID
                ) from error

            try:
                envelope = channel.decode_signed_dispatch(envelope_bytes)
            except ResearchError as error:
                raise GuestAgentSignedDispatchRpcTransportError(
                    GuestAgentSignedDispatchRpcFailureKind.ENVELOPE_DECODE_INVALID
                ) from error

            try:
                verified = verify_signed_dispatch_envelope(
                    envelope,
                    verification_key=self._verification_key,
                    now=self._clock(),
                )
            except GuestAgentDispatchVerificationError as error:
                raise GuestAgentSignedDispatchRpcTransportError(
                    GuestAgentSignedDispatchRpcFailureKind.DISPATCH_VERIFICATION_FAILED
                ) from error

            try:
                final_response, _prepared_invocation = prepare_guest_agent_invocation(
                    verified.request, self._replay_protector
                )
            except ResearchError as error:
                raise GuestAgentSignedDispatchRpcTransportError(
                    GuestAgentSignedDispatchRpcFailureKind.REPLAY_CONSUMPTION_FAILED
                ) from error
            if _prepared_invocation is not None:
                _receipt, _ready_invocation = check_guest_agent_runtime_readiness(
                    _prepared_invocation, self._local_runtime_probe
                )
                # `_receipt`/`_ready_invocation` are discarded unconditionally,
                # exactly like `_prepared_invocation` itself: this server
                # holds no durable execution authority after the request
                # ends and never invokes a process from either. See the
                # module docstring's v0.3.467 note -- the wire response
                # below is unaffected by readiness either way.
            # `_prepared_invocation` is discarded unconditionally: this
            # server holds no durable execution authority after the
            # request ends and never invokes a process. See the module
            # docstring's v0.3.466 note.

            payload = channel.encode_response(final_response)
            tls_conn.settimeout(self._timeouts.write_seconds)
            try:
                write_guest_agent_rpc_frame(tls_conn, payload)
            except (GuestAgentRpcFramingError, OSError) as error:
                raise GuestAgentSignedDispatchRpcTransportError(
                    GuestAgentSignedDispatchRpcFailureKind.FRAME_INVALID
                ) from error
            return final_response
        finally:
            (tls_conn or raw_conn).close()
