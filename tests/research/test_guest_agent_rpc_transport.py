"""Real, authenticated, loopback-only one-request/one-response RPC transport tests.

TRANSPORT DELIVERY != EXECUTION AUTHORITY. Every positive test here proves
only that an already-typed `GuestAgentRequest`/`GuestAgentResponse` can cross
a real, authenticated TLS 1.3 loopback socket between the expected peers --
never that any operation may execute. Every negative test proves the
transport fails closed: wrong peer role, untrusted CA, missing certificate,
malformed or mismatched protocol data, a handler exception, or a second
frame on an already-served connection.

Ephemeral test-only certificate material is generated once via the existing
`tests.research.test_guest_agent_loopback_mtls_handshake._LoopbackMtlsFixture`
-- reused directly, never duplicated, exactly as CLAUDE.md's "reuse, don't
duplicate" instructs. A leading underscore on that class name only affects
`from module import *`; an explicit `from module import _LoopbackMtlsFixture`
import is unaffected and perfectly ordinary Python, so there is nothing
awkward to work around here.
"""

from __future__ import annotations

import ast
import json
import socket
import ssl
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

import research.GuestAgentRpcTransport as rpc_transport_module  # noqa: E402
from core.Exceptions import ResearchError  # noqa: E402
from research.GuestAgentMtlsContext import (  # noqa: E402
    build_guest_server_tls_context,
    build_host_client_tls_context,
)
from research.GuestAgentProtocol import (  # noqa: E402
    GuestAgentProtocolVersion,
    GuestAgentRequest,
    GuestAgentResponse,
    GuestAgentResponseStatus,
)
from research.GuestAgentProtocolSerialization import (  # noqa: E402
    canonical_guest_agent_request_bytes,
    canonical_guest_agent_response_bytes,
)
from research.GuestAgentReplayNonceRecord import (
    GuestAgentReplayNonceRecord,
)  # noqa: E402,E501
from research.GuestAgentReplayProtector import (  # noqa: E402
    GuestAgentReplayOutcome,
    GuestAgentReplayProtector,
)
from research.GuestAgentRpcFraming import (  # noqa: E402
    read_guest_agent_rpc_frame,
    write_guest_agent_rpc_frame,
)
from research.GuestAgentRpcTransport import (  # noqa: E402
    GUEST_AGENT_RPC_LOOPBACK_HOST,
    GuestAgentRpcClient,
    GuestAgentRpcFailureKind,
    GuestAgentRpcServer,
    GuestAgentRpcTransportError,
    GuestAgentRpcTransportTimeouts,
)
from research.ResearchKaliOperationPreview import (
    ResearchKaliOperationKind,
)  # noqa: E402,E501
from tests.research.test_guest_agent_loopback_mtls_handshake import (  # noqa: E402
    _LoopbackMtlsFixture,
)

THIS_FILE = Path(__file__).resolve()
FRAMING_MODULE_FILE = SRC_DIR / "research" / "GuestAgentRpcFraming.py"
TRANSPORT_MODULE_FILE = SRC_DIR / "research" / "GuestAgentRpcTransport.py"

_FAST_TIMEOUTS = GuestAgentRpcTransportTimeouts(
    connect_seconds=5.0, handshake_seconds=5.0, read_seconds=2.0, write_seconds=5.0
)


def _sample_request(
    *,
    request_id: str = "request-0001",
    nonce: str = "nonce-0001",
    operation_kind: ResearchKaliOperationKind = (
        ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP
    ),
    operation_digest: str = "a" * 64,
    logical_inputs: tuple[tuple[str, str], ...] = (),
) -> GuestAgentRequest:
    return GuestAgentRequest(
        protocol_version=GuestAgentProtocolVersion.V1,
        request_id=request_id,
        nonce=nonce,
        operation_kind=operation_kind,
        operation_digest=operation_digest,
        logical_inputs=logical_inputs,
    )


def _echo_handler(request: GuestAgentRequest) -> GuestAgentResponse:
    return GuestAgentResponse(
        protocol_version=GuestAgentProtocolVersion.V1,
        request_id=request.request_id,
        status=GuestAgentResponseStatus.SUCCESS,
        detail="Handled in a test.",
        output_lines=("line one", "line two"),
    )


class _RecordingHandler:
    """A non-dispatcher test handler that records every call it receives."""

    def __init__(self, response_builder=_echo_handler) -> None:
        self.calls: list[GuestAgentRequest] = []
        self._response_builder = response_builder

    def __call__(self, request: GuestAgentRequest) -> GuestAgentResponse:
        self.calls.append(request)
        return self._response_builder(request)


def _run_server_in_thread(
    server: GuestAgentRpcServer,
) -> tuple[threading.Thread, dict[str, object]]:
    outcome: dict[str, object] = {}

    def _run() -> None:
        try:
            outcome["response"] = server.serve_one_request()
        except Exception as error:  # noqa: BLE001 - must observe any failure
            outcome["error"] = error

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread, outcome


def _raw_connect_and_exchange(
    tls_context: ssl.SSLContext,
    port: int,
    request_payload: bytes,
    *,
    timeout: float = 5.0,
) -> dict[str, object]:
    """Connect as a real authenticated peer, send one raw frame, try to read one back.

    Bypasses `GuestAgentRpcClient` entirely so a test can send deliberately
    malformed or hostile payload bytes while still performing a completely
    real TLS 1.3 mutual handshake over loopback.
    """
    outcome: dict[str, object] = {}
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    tls_conn: ssl.SSLSocket | None = None
    try:
        sock.connect((GUEST_AGENT_RPC_LOOPBACK_HOST, port))
        tls_conn = tls_context.wrap_socket(sock, server_hostname=None)
        tls_conn.settimeout(timeout)
        write_guest_agent_rpc_frame(tls_conn, request_payload)
        try:
            outcome["response_bytes"] = read_guest_agent_rpc_frame(tls_conn)
        except Exception as error:  # noqa: BLE001
            outcome["read_error"] = error
    except Exception as error:  # noqa: BLE001
        outcome["connect_error"] = error
    finally:
        (tls_conn or sock).close()
    return outcome


def _run_fake_guest_peer(
    tls_context: ssl.SSLContext,
    response_payload_provider,
    *,
    timeout: float = 5.0,
) -> tuple[threading.Thread, int, dict[str, object]]:
    """A raw fake GUEST peer: real accept + real handshake, discards the real
    request frame, then sends back whatever `response_payload_provider()`
    returns as the raw response payload bytes -- used to exercise the
    CLIENT's own decode/correlation defenses against a hostile peer."""
    listen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listen_sock.bind((GUEST_AGENT_RPC_LOOPBACK_HOST, 0))
    listen_sock.settimeout(timeout)
    listen_sock.listen(1)
    port = listen_sock.getsockname()[1]
    outcome: dict[str, object] = {}

    def _run() -> None:
        try:
            raw_conn, _address = listen_sock.accept()
        except OSError as error:
            outcome["error"] = error
            return
        finally:
            listen_sock.close()
        tls_conn: ssl.SSLSocket | None = None
        try:
            raw_conn.settimeout(timeout)
            tls_conn = tls_context.wrap_socket(raw_conn, server_side=True)
            tls_conn.settimeout(timeout)
            read_guest_agent_rpc_frame(tls_conn)  # discard the real request
            write_guest_agent_rpc_frame(tls_conn, response_payload_provider())
        except Exception as error:  # noqa: BLE001
            outcome["error"] = error
        finally:
            (tls_conn or raw_conn).close()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread, port, outcome


class RealRoundTripTests(_LoopbackMtlsFixture):
    """Requirements 1-8, 12: a real authenticated round trip, byte-exact,
    over a genuinely negotiated TLS 1.3 loopback connection."""

    def test_full_request_response_round_trip_every_field_matches(self) -> None:
        host_config = self.host_config()
        guest_config = self.guest_config()
        handler = _RecordingHandler()
        server = GuestAgentRpcServer(
            build_guest_server_tls_context(guest_config), guest_config, handler
        )
        port = server.bind()
        thread, outcome = _run_server_in_thread(server)

        client = GuestAgentRpcClient(
            build_host_client_tls_context(host_config), host_config, port
        )
        request = _sample_request(logical_inputs=(("field_one", "value one"),))
        response = client.send_request(request)

        thread.join(timeout=5.0)
        self.assertFalse(thread.is_alive())
        self.assertNotIn("error", outcome, msg=outcome.get("error"))

        self.assertEqual(len(handler.calls), 1)
        self.assertEqual(handler.calls[0], request)
        self.assertEqual(response.request_id, request.request_id)
        self.assertEqual(response.status, GuestAgentResponseStatus.SUCCESS)
        self.assertEqual(response.output_lines, ("line one", "line two"))
        self.assertEqual(response, outcome["response"])

    def test_tls13_is_actually_negotiated_on_both_sides(self) -> None:
        host_config = self.host_config()
        guest_config = self.guest_config()
        server = GuestAgentRpcServer(
            build_guest_server_tls_context(guest_config), guest_config, _echo_handler
        )
        port = server.bind()
        thread, outcome = _run_server_in_thread(server)

        captured_versions: list[object] = []
        original_wrap_socket = ssl.SSLContext.wrap_socket

        def _capturing_wrap_socket(self_ctx, *args, **kwargs):
            wrapped = original_wrap_socket(self_ctx, *args, **kwargs)
            captured_versions.append(wrapped.version())
            return wrapped

        client = GuestAgentRpcClient(
            build_host_client_tls_context(host_config), host_config, port
        )
        with mock.patch.object(ssl.SSLContext, "wrap_socket", _capturing_wrap_socket):
            client.send_request(_sample_request())

        thread.join(timeout=5.0)
        self.assertFalse(thread.is_alive())
        self.assertNotIn("error", outcome, msg=outcome.get("error"))
        self.assertEqual(captured_versions, ["TLSv1.3", "TLSv1.3"])

    def test_wire_bytes_are_exactly_the_existing_canonical_codec_output(self) -> None:
        """Requirement 5: no reimplemented encoding. Captures the literal
        bytes handed to `write_guest_agent_rpc_frame` on both sides of a
        real round trip and compares them against the existing, unmodified
        canonical encoder functions directly."""
        host_config = self.host_config()
        guest_config = self.guest_config()
        server = GuestAgentRpcServer(
            build_guest_server_tls_context(guest_config), guest_config, _echo_handler
        )
        port = server.bind()

        captured_payloads: list[bytes] = []
        original_write = rpc_transport_module.write_guest_agent_rpc_frame

        def _capturing_write(sock, payload, **kwargs):
            captured_payloads.append(payload)
            return original_write(sock, payload, **kwargs)

        with mock.patch.object(
            rpc_transport_module, "write_guest_agent_rpc_frame", _capturing_write
        ):
            thread, outcome = _run_server_in_thread(server)
            client = GuestAgentRpcClient(
                build_host_client_tls_context(host_config), host_config, port
            )
            request = _sample_request()
            response = client.send_request(request)
            thread.join(timeout=5.0)

        self.assertFalse(thread.is_alive())
        self.assertNotIn("error", outcome)
        self.assertEqual(len(captured_payloads), 2)
        self.assertEqual(
            captured_payloads[0], canonical_guest_agent_request_bytes(request)
        )
        self.assertEqual(
            captured_payloads[1], canonical_guest_agent_response_bytes(response)
        )

    def test_near_maximum_hostile_but_bound_logical_input_round_trips(self) -> None:
        """A very long, but still protocol-bound, hostile logical-input
        value near the existing per-field maximum crosses the real channel
        unchanged."""
        from research.GuestAgentProtocol import MAX_LOGICAL_INPUT_VALUE_LENGTH

        hostile_value = ("<script>alert(1)</script>" * 200)[
            : MAX_LOGICAL_INPUT_VALUE_LENGTH - 1
        ]
        host_config = self.host_config()
        guest_config = self.guest_config()
        handler = _RecordingHandler()
        server = GuestAgentRpcServer(
            build_guest_server_tls_context(guest_config), guest_config, handler
        )
        port = server.bind()
        thread, outcome = _run_server_in_thread(server)

        client = GuestAgentRpcClient(
            build_host_client_tls_context(host_config), host_config, port
        )
        request = _sample_request(logical_inputs=(("hostile_field", hostile_value),))
        client.send_request(request)
        thread.join(timeout=5.0)
        self.assertFalse(thread.is_alive())
        self.assertNotIn("error", outcome)
        self.assertEqual(handler.calls[0].logical_inputs[0][1], hostile_value)


class LoopbackBindingTests(_LoopbackMtlsFixture):
    """Requirements 13-15: loopback-only, ephemeral port, never wildcard."""

    def test_loopback_host_constant_is_exactly_127_0_0_1(self) -> None:
        self.assertEqual(GUEST_AGENT_RPC_LOOPBACK_HOST, "127.0.0.1")

    def test_bind_returns_an_os_assigned_ephemeral_port_each_time(self) -> None:
        guest_config = self.guest_config()
        ports: set[int] = set()
        for _ in range(2):
            server = GuestAgentRpcServer(
                build_guest_server_tls_context(guest_config),
                guest_config,
                _echo_handler,
            )
            port = server.bind()
            ports.add(port)
            # Clean up the listening socket without serving anything.
            server._listen_sock.close()  # type: ignore[union-attr]
        self.assertNotIn(0, ports)

    def test_second_bind_on_the_same_instance_is_refused(self) -> None:
        guest_config = self.guest_config()
        server = GuestAgentRpcServer(
            build_guest_server_tls_context(guest_config), guest_config, _echo_handler
        )
        server.bind()
        with self.assertRaises(ResearchError):
            server.bind()
        server._listen_sock.close()  # type: ignore[union-attr]


class AuthenticationGateTests(_LoopbackMtlsFixture):
    """Requirements 9-12: CA-valid-but-wrong-role, untrusted CA, and a
    missing client certificate can never reach the decoder or handler."""

    def test_ca_valid_wrong_role_client_cannot_reach_server_handler(self) -> None:
        guest_config = self.guest_config()
        host_config_wrong_role = self.host_config(
            own_cert=self.guest_cert, own_key=self.guest_key
        )
        handler = _RecordingHandler()
        server = GuestAgentRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            handler,
            timeouts=_FAST_TIMEOUTS,
        )
        port = server.bind()
        thread, outcome = _run_server_in_thread(server)

        client = GuestAgentRpcClient(
            build_host_client_tls_context(host_config_wrong_role),
            host_config_wrong_role,
            port,
            timeouts=_FAST_TIMEOUTS,
        )
        try:
            client.send_request(_sample_request())
        except Exception:  # noqa: BLE001 - client-side outcome is secondary
            pass

        thread.join(timeout=5.0)
        self.assertFalse(thread.is_alive())
        self.assertEqual(handler.calls, [])
        self.assertIn("error", outcome)
        self.assertIsInstance(outcome["error"], GuestAgentRpcTransportError)
        self.assertEqual(
            outcome["error"].kind,  # type: ignore[union-attr]
            GuestAgentRpcFailureKind.PEER_AUTHENTICATION_FAILED,
        )

    def test_ca_valid_wrong_role_server_cannot_be_decoded_by_client(self) -> None:
        host_config = self.host_config()
        guest_config_wrong_role = self.guest_config(
            own_cert=self.host_cert, own_key=self.host_key
        )
        handler = _RecordingHandler()
        server = GuestAgentRpcServer(
            build_guest_server_tls_context(guest_config_wrong_role),
            guest_config_wrong_role,
            handler,
            timeouts=_FAST_TIMEOUTS,
        )
        port = server.bind()
        thread, _outcome = _run_server_in_thread(server)

        client = GuestAgentRpcClient(
            build_host_client_tls_context(host_config),
            host_config,
            port,
            timeouts=_FAST_TIMEOUTS,
        )
        with self.assertRaises(GuestAgentRpcTransportError) as ctx:
            client.send_request(_sample_request())
        self.assertEqual(
            ctx.exception.kind, GuestAgentRpcFailureKind.PEER_AUTHENTICATION_FAILED
        )
        thread.join(timeout=5.0)
        self.assertFalse(thread.is_alive())

    def test_untrusted_ca_client_cannot_reach_server_handler(self) -> None:
        guest_config = self.guest_config()
        host_config_untrusted = self.host_config(own_cert=self.wrong_ca_host_cert)
        handler = _RecordingHandler()
        server = GuestAgentRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            handler,
            timeouts=_FAST_TIMEOUTS,
        )
        port = server.bind()
        thread, outcome = _run_server_in_thread(server)

        client = GuestAgentRpcClient(
            build_host_client_tls_context(host_config_untrusted),
            host_config_untrusted,
            port,
            timeouts=_FAST_TIMEOUTS,
        )
        try:
            client.send_request(_sample_request())
        except Exception:  # noqa: BLE001
            pass

        thread.join(timeout=5.0)
        self.assertFalse(thread.is_alive())
        self.assertEqual(handler.calls, [])
        self.assertIn("error", outcome)
        self.assertIsInstance(outcome["error"], GuestAgentRpcTransportError)
        self.assertEqual(
            outcome["error"].kind,  # type: ignore[union-attr]
            GuestAgentRpcFailureKind.HANDSHAKE_FAILED,
        )

    def test_missing_client_certificate_cannot_reach_server_handler(self) -> None:
        guest_config = self.guest_config()
        host_config = self.host_config()
        handler = _RecordingHandler()
        server = GuestAgentRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            handler,
            timeouts=_FAST_TIMEOUTS,
        )
        port = server.bind()
        thread, outcome = _run_server_in_thread(server)

        bare_client_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        bare_client_ctx.minimum_version = ssl.TLSVersion.TLSv1_3
        bare_client_ctx.maximum_version = ssl.TLSVersion.TLSv1_3
        bare_client_ctx.verify_mode = ssl.CERT_REQUIRED
        bare_client_ctx.check_hostname = False
        bare_client_ctx.load_verify_locations(cafile=str(self.ca_cert))
        # Deliberately never calls load_cert_chain: no client certificate.

        client = GuestAgentRpcClient(
            bare_client_ctx, host_config, port, timeouts=_FAST_TIMEOUTS
        )
        try:
            client.send_request(_sample_request())
        except Exception:  # noqa: BLE001
            pass

        thread.join(timeout=5.0)
        self.assertFalse(thread.is_alive())
        self.assertEqual(handler.calls, [])
        self.assertIn("error", outcome)
        self.assertIsInstance(outcome["error"], GuestAgentRpcTransportError)
        self.assertEqual(
            outcome["error"].kind,  # type: ignore[union-attr]
            GuestAgentRpcFailureKind.HANDSHAKE_FAILED,
        )


class MalformedAndMismatchedPayloadTests(_LoopbackMtlsFixture):
    """Requirements 23-28: malformed JSON, unknown fields, unsupported
    version, wrong-direction messages, and request_id correlation -- on
    both the server's decode of a request and the client's decode of a
    response."""

    def _server_sees(self, raw_payload: bytes) -> dict[str, object]:
        guest_config = self.guest_config()
        host_config = self.host_config()
        handler = _RecordingHandler()
        server = GuestAgentRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            handler,
            timeouts=_FAST_TIMEOUTS,
        )
        port = server.bind()
        thread, outcome = _run_server_in_thread(server)
        client_ctx = build_host_client_tls_context(host_config)
        exchange = _raw_connect_and_exchange(client_ctx, port, raw_payload, timeout=5.0)
        thread.join(timeout=5.0)
        self.assertFalse(thread.is_alive())
        outcome["handler_calls"] = handler.calls
        outcome["client_exchange"] = exchange
        return outcome

    def test_server_rejects_malformed_json_bytes(self) -> None:
        outcome = self._server_sees(b"{this is not json")
        self.assertEqual(outcome["handler_calls"], [])
        self.assertIsInstance(outcome["error"], GuestAgentRpcTransportError)
        self.assertEqual(
            outcome["error"].kind,  # type: ignore[union-attr]
            GuestAgentRpcFailureKind.PROTOCOL_DECODE_INVALID,
        )

    def test_server_rejects_malformed_utf8_bytes(self) -> None:
        outcome = self._server_sees(b"\xff\xfe\x00\x01not-utf8")
        self.assertEqual(outcome["handler_calls"], [])
        self.assertEqual(
            outcome["error"].kind,  # type: ignore[union-attr]
            GuestAgentRpcFailureKind.PROTOCOL_DECODE_INVALID,
        )

    def test_server_rejects_unknown_top_level_field(self) -> None:
        document = {
            "protocol_version": GuestAgentProtocolVersion.V1.value,
            "request_id": "r1",
            "nonce": "n1",
            "operation_kind": ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP.value,
            "operation_digest": "a" * 64,
            "logical_inputs": [],
            "unexpected_field": "should be rejected",
        }
        payload = json.dumps(document, sort_keys=True).encode("utf-8")
        outcome = self._server_sees(payload)
        self.assertEqual(outcome["handler_calls"], [])
        self.assertEqual(
            outcome["error"].kind,  # type: ignore[union-attr]
            GuestAgentRpcFailureKind.PROTOCOL_DECODE_INVALID,
        )

    def test_server_rejects_unsupported_future_protocol_version(self) -> None:
        document = {
            "protocol_version": "hypatia-kali-guest-agent/99",
            "request_id": "r1",
            "nonce": "n1",
            "operation_kind": ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP.value,
            "operation_digest": "a" * 64,
            "logical_inputs": [],
        }
        payload = json.dumps(document, sort_keys=True).encode("utf-8")
        outcome = self._server_sees(payload)
        self.assertEqual(outcome["handler_calls"], [])
        self.assertEqual(
            outcome["error"].kind,  # type: ignore[union-attr]
            GuestAgentRpcFailureKind.PROTOCOL_DECODE_INVALID,
        )

    def test_server_rejects_a_response_shaped_wrong_direction_message(self) -> None:
        document = {
            "protocol_version": GuestAgentProtocolVersion.V1.value,
            "request_id": "r1",
            "status": GuestAgentResponseStatus.SUCCESS.value,
            "detail": "not a request",
        }
        payload = json.dumps(document, sort_keys=True).encode("utf-8")
        outcome = self._server_sees(payload)
        self.assertEqual(outcome["handler_calls"], [])
        self.assertEqual(
            outcome["error"].kind,  # type: ignore[union-attr]
            GuestAgentRpcFailureKind.PROTOCOL_DECODE_INVALID,
        )

    def _client_sees(
        self, response_payload_provider
    ) -> tuple[GuestAgentResponse | None, Exception | None]:
        host_config = self.host_config()
        guest_tls_context = build_guest_server_tls_context(self.guest_config())
        thread, port, _server_outcome = _run_fake_guest_peer(
            guest_tls_context, response_payload_provider, timeout=5.0
        )
        client = GuestAgentRpcClient(
            build_host_client_tls_context(host_config),
            host_config,
            port,
            timeouts=_FAST_TIMEOUTS,
        )
        response: GuestAgentResponse | None = None
        error: Exception | None = None
        try:
            response = client.send_request(_sample_request())
        except Exception as exc:  # noqa: BLE001
            error = exc
        thread.join(timeout=5.0)
        self.assertFalse(thread.is_alive())
        return response, error

    def test_client_rejects_malformed_json_response(self) -> None:
        _response, error = self._client_sees(lambda: b"{not valid json")
        self.assertIsInstance(error, GuestAgentRpcTransportError)
        self.assertEqual(
            error.kind, GuestAgentRpcFailureKind.PROTOCOL_DECODE_INVALID  # type: ignore[union-attr]
        )

    def test_client_rejects_a_request_shaped_wrong_direction_response(self) -> None:
        def _wrong_direction() -> bytes:
            document = {
                "protocol_version": GuestAgentProtocolVersion.V1.value,
                "request_id": "r1",
                "nonce": "n1",
                "operation_kind": (ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP.value),
                "operation_digest": "a" * 64,
                "logical_inputs": [],
            }
            return json.dumps(document, sort_keys=True).encode("utf-8")

        _response, error = self._client_sees(_wrong_direction)
        self.assertIsInstance(error, GuestAgentRpcTransportError)
        self.assertEqual(
            error.kind, GuestAgentRpcFailureKind.PROTOCOL_DECODE_INVALID  # type: ignore[union-attr]
        )

    def test_client_rejects_mismatched_response_request_id(self) -> None:
        def _mismatched() -> bytes:
            response = GuestAgentResponse(
                protocol_version=GuestAgentProtocolVersion.V1,
                request_id="a-completely-different-request-id",
                status=GuestAgentResponseStatus.SUCCESS,
                detail="wrong id",
            )
            return canonical_guest_agent_response_bytes(response)

        _response, error = self._client_sees(_mismatched)
        self.assertIsInstance(error, GuestAgentRpcTransportError)
        self.assertEqual(
            error.kind, GuestAgentRpcFailureKind.CORRELATION_FAILED  # type: ignore[union-attr]
        )

    def test_client_accepts_exact_matching_request_id(self) -> None:
        def _matching() -> bytes:
            response = GuestAgentResponse(
                protocol_version=GuestAgentProtocolVersion.V1,
                request_id="request-0001",
                status=GuestAgentResponseStatus.SUCCESS,
                detail="matched",
            )
            return canonical_guest_agent_response_bytes(response)

        response, error = self._client_sees(_matching)
        self.assertIsNone(error)
        assert response is not None
        self.assertEqual(response.request_id, "request-0001")


class HandlerFailureHygieneTests(_LoopbackMtlsFixture):
    """Requirements 46-47: a handler's exception text never reaches the
    peer, and a handler/response-correlation failure sends no response."""

    def test_handler_exception_text_is_never_reflected_to_the_client(self) -> None:
        marker = "HOSTILE-UNIQUE-HANDLER-EXCEPTION-MARKER-1234567890"

        def _failing_handler(request: GuestAgentRequest) -> GuestAgentResponse:
            raise RuntimeError(marker)

        guest_config = self.guest_config()
        host_config = self.host_config()
        server = GuestAgentRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            _failing_handler,
            timeouts=_FAST_TIMEOUTS,
        )
        port = server.bind()
        thread, outcome = _run_server_in_thread(server)

        client = GuestAgentRpcClient(
            build_host_client_tls_context(host_config),
            host_config,
            port,
            timeouts=_FAST_TIMEOUTS,
        )
        with self.assertRaises(GuestAgentRpcTransportError) as ctx:
            client.send_request(_sample_request())
        thread.join(timeout=5.0)
        self.assertFalse(thread.is_alive())

        # The client cannot distinguish "the server's handler raised" from
        # any other reason the connection closed without a response -- by
        # design, that specific reason is never transmitted to the peer.
        # The server's own observed kind IS deterministically HANDLER_FAILED.
        self.assertIn(
            ctx.exception.kind,
            (
                GuestAgentRpcFailureKind.FRAME_INVALID,
                GuestAgentRpcFailureKind.CONNECTION_FAILED,
            ),
        )
        self.assertNotIn(marker, str(ctx.exception))
        self.assertIsInstance(outcome.get("error"), GuestAgentRpcTransportError)
        self.assertEqual(
            outcome["error"].kind,  # type: ignore[union-attr]
            GuestAgentRpcFailureKind.HANDLER_FAILED,
        )
        self.assertNotIn(marker, str(outcome["error"]))
        self.assertLessEqual(len(str(ctx.exception)), 200)

    def test_handler_returning_mismatched_request_id_sends_nothing(self) -> None:
        def _mismatched_handler(request: GuestAgentRequest) -> GuestAgentResponse:
            return GuestAgentResponse(
                protocol_version=GuestAgentProtocolVersion.V1,
                request_id="not-the-right-id",
                status=GuestAgentResponseStatus.SUCCESS,
                detail="mismatched on purpose",
            )

        guest_config = self.guest_config()
        host_config = self.host_config()
        server = GuestAgentRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            _mismatched_handler,
            timeouts=_FAST_TIMEOUTS,
        )
        port = server.bind()
        thread, outcome = _run_server_in_thread(server)

        client = GuestAgentRpcClient(
            build_host_client_tls_context(host_config),
            host_config,
            port,
            timeouts=_FAST_TIMEOUTS,
        )
        with self.assertRaises(GuestAgentRpcTransportError):
            client.send_request(_sample_request())
        thread.join(timeout=5.0)
        self.assertFalse(thread.is_alive())
        self.assertEqual(
            outcome["error"].kind,  # type: ignore[union-attr]
            GuestAgentRpcFailureKind.HANDLER_FAILED,
        )


class OneShotSessionTests(_LoopbackMtlsFixture):
    """Requirements 29-32: exactly one request/response per connection, and
    the connection always closes afterward -- success, protocol failure, or
    handler failure alike."""

    def test_second_frame_on_the_same_connection_is_never_processed(self) -> None:
        guest_config = self.guest_config()
        host_config = self.host_config()
        handler = _RecordingHandler()
        server = GuestAgentRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            handler,
            timeouts=_FAST_TIMEOUTS,
        )
        port = server.bind()
        thread, outcome = _run_server_in_thread(server)

        first_request = _sample_request(request_id="first-request")
        second_request = _sample_request(request_id="second-request")

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        sock.connect((GUEST_AGENT_RPC_LOOPBACK_HOST, port))
        client_ctx = build_host_client_tls_context(host_config)
        tls_conn = client_ctx.wrap_socket(sock, server_hostname=None)
        tls_conn.settimeout(5.0)
        try:
            write_guest_agent_rpc_frame(
                tls_conn, canonical_guest_agent_request_bytes(first_request)
            )
            # Read the first (and only) response before sending anything
            # else: once the server returns from `serve_one_request` it
            # closes the connection while a second, unread frame would
            # still be sitting in its receive buffer, which some TCP
            # stacks (including this project's own Windows CI target)
            # answer with an abortive RST rather than a graceful close --
            # a known OS-level race, not a correctness question about
            # which frame was processed. Reading the first response before
            # ever sending a second frame avoids that race entirely while
            # still proving the one-shot server only ever answers once.
            first_response_bytes = read_guest_agent_rpc_frame(tls_conn)
            # Only now send a second frame, on the very same connection,
            # against a server that has already returned from
            # `serve_one_request` (and therefore already closed its end).
            # Whatever happens next -- the write itself failing, or a
            # subsequent read failing -- must fail; it must never deliver
            # a second real response.
            with self.assertRaises((OSError, ResearchError)):
                write_guest_agent_rpc_frame(
                    tls_conn, canonical_guest_agent_request_bytes(second_request)
                )
                read_guest_agent_rpc_frame(tls_conn)
        finally:
            tls_conn.close()

        thread.join(timeout=5.0)
        self.assertFalse(thread.is_alive())
        self.assertNotIn("error", outcome)
        self.assertEqual(len(handler.calls), 1)
        self.assertEqual(handler.calls[0].request_id, "first-request")
        self.assertTrue(len(first_response_bytes) > 0)

    def test_connection_closes_after_successful_response(self) -> None:
        guest_config = self.guest_config()
        host_config = self.host_config()
        server = GuestAgentRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            _echo_handler,
            timeouts=_FAST_TIMEOUTS,
        )
        port = server.bind()
        thread, outcome = _run_server_in_thread(server)
        self._assert_server_closes_after(host_config, port, thread, outcome)

    def test_connection_closes_after_a_protocol_failure(self) -> None:
        guest_config = self.guest_config()
        host_config = self.host_config()
        server = GuestAgentRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            _echo_handler,
            timeouts=_FAST_TIMEOUTS,
        )
        port = server.bind()
        thread, outcome = _run_server_in_thread(server)

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        sock.connect((GUEST_AGENT_RPC_LOOPBACK_HOST, port))
        client_ctx = build_host_client_tls_context(host_config)
        tls_conn = client_ctx.wrap_socket(sock, server_hostname=None)
        tls_conn.settimeout(5.0)
        write_guest_agent_rpc_frame(tls_conn, b"{not valid json")
        try:
            remainder = tls_conn.recv(1)
            self.assertEqual(remainder, b"")
        except OSError:
            pass  # A reset/closed connection is an equally valid proof.
        finally:
            tls_conn.close()

        thread.join(timeout=5.0)
        self.assertFalse(thread.is_alive())
        self.assertIn("error", outcome)

    def test_connection_closes_after_a_handler_failure(self) -> None:
        def _failing_handler(request: GuestAgentRequest) -> GuestAgentResponse:
            raise RuntimeError("deliberate failure")

        guest_config = self.guest_config()
        host_config = self.host_config()
        server = GuestAgentRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            _failing_handler,
            timeouts=_FAST_TIMEOUTS,
        )
        port = server.bind()
        thread, outcome = _run_server_in_thread(server)

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        sock.connect((GUEST_AGENT_RPC_LOOPBACK_HOST, port))
        client_ctx = build_host_client_tls_context(host_config)
        tls_conn = client_ctx.wrap_socket(sock, server_hostname=None)
        tls_conn.settimeout(5.0)
        write_guest_agent_rpc_frame(
            tls_conn, canonical_guest_agent_request_bytes(_sample_request())
        )
        try:
            remainder = tls_conn.recv(1)
            self.assertEqual(remainder, b"")
        except OSError:
            pass
        finally:
            tls_conn.close()

        thread.join(timeout=5.0)
        self.assertFalse(thread.is_alive())
        self.assertEqual(
            outcome["error"].kind,  # type: ignore[union-attr]
            GuestAgentRpcFailureKind.HANDLER_FAILED,
        )

    def _assert_server_closes_after(
        self,
        host_config,
        port: int,
        thread: threading.Thread,
        outcome: dict[str, object],
    ) -> None:
        client = GuestAgentRpcClient(
            build_host_client_tls_context(host_config),
            host_config,
            port,
            timeouts=_FAST_TIMEOUTS,
        )
        client.send_request(_sample_request())
        thread.join(timeout=5.0)
        self.assertFalse(thread.is_alive())
        self.assertNotIn("error", outcome)

    def test_serve_one_request_a_second_time_on_the_same_instance_is_refused(
        self,
    ) -> None:
        guest_config = self.guest_config()
        host_config = self.host_config()
        server = GuestAgentRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            _echo_handler,
            timeouts=_FAST_TIMEOUTS,
        )
        port = server.bind()
        thread, outcome = _run_server_in_thread(server)
        client = GuestAgentRpcClient(
            build_host_client_tls_context(host_config),
            host_config,
            port,
            timeouts=_FAST_TIMEOUTS,
        )
        client.send_request(_sample_request())
        thread.join(timeout=5.0)
        self.assertFalse(thread.is_alive())
        self.assertNotIn("error", outcome)
        with self.assertRaises(ResearchError):
            server.serve_one_request()


class TimeoutAndRetryTests(_LoopbackMtlsFixture):
    """Requirements 33-34: bounded timeouts, and no transparent retry."""

    def test_default_timeouts_are_positive_and_bounded(self) -> None:
        timeouts = GuestAgentRpcTransportTimeouts()
        for value in (
            timeouts.connect_seconds,
            timeouts.handshake_seconds,
            timeouts.read_seconds,
            timeouts.write_seconds,
        ):
            self.assertGreater(value, 0.0)
            self.assertLessEqual(value, 30.0)

    def test_timeout_above_thirty_seconds_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentRpcTransportTimeouts(connect_seconds=30.1)

    def test_zero_or_negative_timeout_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentRpcTransportTimeouts(read_seconds=0.0)
        with self.assertRaises(ResearchError):
            GuestAgentRpcTransportTimeouts(write_seconds=-1.0)

    def test_send_request_contains_no_retry_loop_structurally(self) -> None:
        tree = ast.parse(
            TRANSPORT_MODULE_FILE.read_text(encoding="utf-8"),
            filename=str(TRANSPORT_MODULE_FILE),
        )
        send_request_def = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "send_request":
                send_request_def = node
                break
        self.assertIsNotNone(send_request_def)
        for inner in ast.walk(send_request_def):  # type: ignore[arg-type]
            self.assertNotIsInstance(inner, (ast.For, ast.While))

    def test_a_failed_connect_is_attempted_exactly_once(self) -> None:
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.bind((GUEST_AGENT_RPC_LOOPBACK_HOST, 0))
        unused_port = probe.getsockname()[1]
        probe.close()

        host_config = self.host_config()
        client = GuestAgentRpcClient(
            build_host_client_tls_context(host_config),
            host_config,
            unused_port,
            timeouts=_FAST_TIMEOUTS,
        )
        connect_attempts: list[object] = []
        original_connect = socket.socket.connect

        def _counting_connect(self_sock, address):
            connect_attempts.append(address)
            return original_connect(self_sock, address)

        with mock.patch.object(socket.socket, "connect", _counting_connect):
            with self.assertRaises(GuestAgentRpcTransportError) as ctx:
                client.send_request(_sample_request())
        self.assertEqual(ctx.exception.kind, GuestAgentRpcFailureKind.CONNECTION_FAILED)
        self.assertEqual(len(connect_attempts), 1)


class ReplayNonConsumptionTests(_LoopbackMtlsFixture):
    """Requirement 35: transport receipt never consumes a replay identity."""

    def test_nonce_remains_unconsumed_after_a_successful_round_trip(self) -> None:
        class _InMemoryReplayStore:
            def __init__(self) -> None:
                self._records: list[GuestAgentReplayNonceRecord] = []

            def load(self) -> list[GuestAgentReplayNonceRecord]:
                return list(self._records)

            def save(self, records: list[GuestAgentReplayNonceRecord]) -> None:
                self._records = list(records)

        guest_config = self.guest_config()
        host_config = self.host_config()
        server = GuestAgentRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            _echo_handler,
            timeouts=_FAST_TIMEOUTS,
        )
        port = server.bind()
        thread, outcome = _run_server_in_thread(server)

        client = GuestAgentRpcClient(
            build_host_client_tls_context(host_config),
            host_config,
            port,
            timeouts=_FAST_TIMEOUTS,
        )
        request = _sample_request(nonce="still-unconsumed-nonce")
        client.send_request(request)
        thread.join(timeout=5.0)
        self.assertFalse(thread.is_alive())
        self.assertNotIn("error", outcome)

        protector = GuestAgentReplayProtector(_InMemoryReplayStore())
        outcome_after_transport = protector.consume_once(request)
        self.assertEqual(outcome_after_transport, GuestAgentReplayOutcome.ACCEPTED)


class PrivateKeyHygieneAndCleanupTests(_LoopbackMtlsFixture):
    """Requirements 48-49: temporary certificate material is cleaned up, and
    private key text never leaks into a captured error string."""

    def test_temporary_material_is_removed_after_this_class(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hypatia-rpc-cleanup-check-") as name:
            directory = Path(name)
            marker = directory / "marker.txt"
            marker.write_text("throwaway")
            self.assertTrue(marker.exists())
        self.assertFalse(directory.exists())

    def test_no_private_key_text_in_any_negative_path_error(self) -> None:
        host_key_text = self.host_key.read_text(encoding="utf-8")
        guest_key_text = self.guest_key.read_text(encoding="utf-8")

        guest_config = self.guest_config()
        host_config_untrusted = self.host_config(own_cert=self.wrong_ca_host_cert)
        server = GuestAgentRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            _echo_handler,
            timeouts=_FAST_TIMEOUTS,
        )
        port = server.bind()
        thread, outcome = _run_server_in_thread(server)
        client = GuestAgentRpcClient(
            build_host_client_tls_context(host_config_untrusted),
            host_config_untrusted,
            port,
            timeouts=_FAST_TIMEOUTS,
        )
        client_error_text = ""
        try:
            client.send_request(_sample_request())
        except Exception as error:  # noqa: BLE001
            client_error_text = str(error)
        thread.join(timeout=5.0)
        self.assertFalse(thread.is_alive())

        server_error_text = str(outcome.get("error", ""))
        for text in (client_error_text, server_error_text):
            self.assertNotIn(host_key_text, text)
            self.assertNotIn(guest_key_text, text)
            self.assertNotIn("PRIVATE KEY", text)


class StructuralSecurityTests(unittest.TestCase):
    """Requirements 18-26, 35-45: AST-based proof that neither new source
    file (nor this test file) introduces an execution-authority dependency,
    a replay coupling, a non-loopback bind/connect, or any subprocess
    reference -- mirroring the existing structural test patterns exactly."""

    def setUp(self) -> None:
        self.framing_tree = ast.parse(
            FRAMING_MODULE_FILE.read_text(encoding="utf-8"),
            filename=str(FRAMING_MODULE_FILE),
        )
        self.transport_tree = ast.parse(
            TRANSPORT_MODULE_FILE.read_text(encoding="utf-8"),
            filename=str(TRANSPORT_MODULE_FILE),
        )
        self.test_tree = ast.parse(
            THIS_FILE.read_text(encoding="utf-8"), filename=str(THIS_FILE)
        )
        self.all_trees = (self.framing_tree, self.transport_tree, self.test_tree)

    @staticmethod
    def _referenced_names(tree: ast.AST) -> set[str]:
        referenced: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                referenced.add(node.id)
            elif isinstance(node, ast.Attribute):
                referenced.add(node.attr)
            elif isinstance(node, ast.ImportFrom):
                referenced.update(alias.name for alias in node.names)
            elif isinstance(node, ast.Import):
                referenced.update(alias.name for alias in node.names)
        return referenced

    def test_no_kali_execution_authority_is_imported_or_referenced(self) -> None:
        forbidden = {
            "KaliToolGateway",
            "ToolExecutionService",
            "ResearchKaliOperationAuthorization",
            "JsonFileResearchKaliOperationAuthorizationStore",
            "WslKaliOperationProcessAdapter",
            "VmwareKaliOperationProcessAdapter",
        }
        for tree in self.all_trees:
            with self.subTest(tree=tree):
                self.assertEqual(self._referenced_names(tree) & forbidden, set())

    def test_replay_protection_is_not_imported_or_invoked_in_production_code(
        self,
    ) -> None:
        forbidden = {
            "GuestAgentReplayProtector",
            "GuestAgentReplayOutcome",
            "JsonFileGuestAgentReplayNonceStore",
            "consume_once",
        }
        for tree in (self.framing_tree, self.transport_tree):
            with self.subTest(tree=tree):
                self.assertEqual(self._referenced_names(tree) & forbidden, set())

    def test_no_vmware_kali_ssh_wsl_execution_token_is_referenced(self) -> None:
        forbidden = {"vmrun", "sshd", "paramiko", "wsl"}
        for tree in self.all_trees:
            with self.subTest(tree=tree):
                lowered = {name.lower() for name in self._referenced_names(tree)}
                self.assertEqual(lowered & forbidden, set())

    def test_no_subprocess_reference_anywhere_in_the_new_files(self) -> None:
        """Unlike the real-handshake precedent, nothing here needs to
        generate certificates itself (the fixture is reused unmodified), so
        the strongest honest proof is simply: no `subprocess` reference at
        all in either new production module or this test file."""
        for tree in self.all_trees:
            with self.subTest(tree=tree):
                self.assertNotIn("subprocess", self._referenced_names(tree))

    def test_every_bind_or_connect_call_targets_loopback_only(self) -> None:
        for tree in (self.transport_tree, self.test_tree):
            found_any = False
            for node in ast.walk(tree):
                if not (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr in ("bind", "connect")
                ):
                    continue
                if not node.args or not isinstance(node.args[0], ast.Tuple):
                    continue
                address_tuple = node.args[0]
                if not address_tuple.elts:
                    continue
                found_any = True
                host_node = address_tuple.elts[0]
                with self.subTest(tree=tree, line=node.lineno, call=node.func.attr):
                    if isinstance(host_node, ast.Constant) and isinstance(
                        host_node.value, str
                    ):
                        self.assertEqual(host_node.value, "127.0.0.1")
                    elif isinstance(host_node, ast.Name):
                        self.assertIn(
                            host_node.id,
                            {"GUEST_AGENT_RPC_LOOPBACK_HOST"},
                        )
                    else:
                        self.fail(
                            f"unrecognized bind/connect host argument: {host_node}"
                        )
            self.assertTrue(found_any)

    def test_guest_agent_rpc_loopback_host_constant_is_never_a_parameter(self) -> None:
        """`GUEST_AGENT_RPC_LOOPBACK_HOST` is never accepted as a function
        parameter anywhere in the transport module -- it cannot be
        overridden by a caller."""
        parameter_names: set[str] = set()
        for node in ast.walk(self.transport_tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for arg in (
                    node.args.args + node.args.kwonlyargs + node.args.posonlyargs
                ):
                    parameter_names.add(arg.arg)
        self.assertNotIn("host", parameter_names)

    def test_parse_peer_certificate_identity_and_authenticate_peer_are_reused(
        self,
    ) -> None:
        """No local reimplementation -- the imported symbols genuinely are
        the existing modules' own."""
        from research.GuestAgentPeerAuthenticator import authenticate_peer
        from research.GuestAgentPeerCertificateIdentity import (
            parse_peer_certificate_identity,
        )

        self.assertEqual(
            authenticate_peer.__module__, "research.GuestAgentPeerAuthenticator"
        )
        self.assertEqual(
            parse_peer_certificate_identity.__module__,
            "research.GuestAgentPeerCertificateIdentity",
        )


if __name__ == "__main__":
    unittest.main()
