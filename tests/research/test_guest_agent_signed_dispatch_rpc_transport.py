"""The real verify -> admit -> replay-consume composition over a real RPC socket.

Every positive test here proves a real, authenticated TLS 1.3 loopback
round trip carrying a real, cryptographically signed
`GuestAgentSignedDispatchEnvelope` -- never that any operation may
execute. Every negative/adversarial test proves either fail-closed
construction, or that the connection aborts with ZERO wire response
whenever any stage before replay consumption fails -- and, above all,
that replay consumption is structurally reached only after verification
has already succeeded, and admission before that.

Ephemeral test-only certificate material and the fixture class/trust
configuration helpers are reused unmodified from
`tests.research.test_guest_agent_loopback_mtls_handshake._LoopbackMtlsFixture`.
A real one-shot `GuestAgentHostDispatchGrant` and a real Ed25519-signed
envelope are built the same way
`tests.research.test_guest_agent_dispatch_signing` already does, reusing
its own fixture helpers (`FakeAuthorizationStore`, `_authorize`,
`_preview`, `_https_preview`) directly.
"""

from __future__ import annotations

import ast
import inspect
import socket
import ssl
import sys
import threading
import unittest
from datetime import datetime, timedelta
from itertools import count
from pathlib import Path
from unittest import mock

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # noqa: E402
    Ed25519PrivateKey,
)

import research.GuestAgentSignedDispatchRpcTransport as transport_module  # noqa: E402
from core.Exceptions import ResearchError  # noqa: E402
from research.GuestAgentDispatchProof import (  # noqa: E402
    GuestAgentSignedDispatchEnvelope,
)
from research.GuestAgentDispatchSigning import (
    create_signed_dispatch_envelope,
)  # noqa: E402
from research.GuestAgentDispatchVerification import (  # noqa: E402
    GuestAgentDispatchVerificationError,
    GuestAgentDispatchVerificationFailure,
    GuestAgentDispatchVerificationStage,
)
from research.GuestAgentHostAuthorizationHandoff import (  # noqa: E402
    consume_authorization_for_guest_agent_dispatch,
)
from research.GuestAgentMtlsContext import (  # noqa: E402
    build_guest_server_tls_context,
    build_host_client_tls_context,
)
from research.GuestAgentProtocol import (
    GuestAgentResponse,
    GuestAgentResponseStatus,
)  # noqa: E402
from research.GuestAgentReplayProtector import (  # noqa: E402
    GuestAgentReplayProtector,
)
from research.GuestAgentRpcFraming import MAX_GUEST_AGENT_RPC_FRAME_SIZE  # noqa: E402
from research.GuestAgentSignedDispatchRpcTransport import (  # noqa: E402
    GuestAgentSignedDispatchRpcClient,
    GuestAgentSignedDispatchRpcFailureKind,
    GuestAgentSignedDispatchRpcServer,
    GuestAgentSignedDispatchRpcTransportError,
)
from research.GuestAgentSignedDispatchSerialization import (  # noqa: E402
    canonical_guest_agent_signed_dispatch_envelope_bytes,
)
from tests.research.test_guest_agent_host_authorization_handoff import (  # noqa: E402
    NOW,
    FakeAuthorizationStore,
    _authorize,
    _https_preview,
    _preview,
)
from tests.research.test_guest_agent_loopback_mtls_handshake import (  # noqa: E402
    _LoopbackMtlsFixture,
)

THIS_FILE = Path(__file__).resolve()
TRANSPORT_MODULE_FILE = SRC_DIR / "research" / "GuestAgentSignedDispatchRpcTransport.py"

_authorization_ids = count(1)


def _real_envelope(
    signing_key: Ed25519PrivateKey,
    *,
    preview=None,
    request_id: str = "r1",
    nonce: str = "n1",
    now: datetime = NOW,
) -> GuestAgentSignedDispatchEnvelope:
    preview = preview or _preview()
    authorization_id = f"auth-{next(_authorization_ids)}"
    authorization = _authorize(preview, authorization_id=authorization_id)
    store = FakeAuthorizationStore([authorization])
    grant = consume_authorization_for_guest_agent_dispatch(
        store, authorization_id, preview, now=now
    )
    return create_signed_dispatch_envelope(
        grant, request_id=request_id, nonce=nonce, signing_key=signing_key, now=now
    )


class _FakeReplayStore:
    """A minimal in-memory `GuestAgentReplayNonceStore` with error injection."""

    def __init__(self, *, save_error: Exception | None = None) -> None:
        self._records: list = []
        self._save_error = save_error
        self.save_calls = 0

    def load(self) -> list:
        return list(self._records)

    def save(self, records: list) -> None:
        self.save_calls += 1
        if self._save_error is not None:
            raise self._save_error
        self._records = list(records)


def _run_server(server: GuestAgentSignedDispatchRpcServer):
    outcome: dict[str, object] = {}

    def _run() -> None:
        try:
            outcome["response"] = server.serve_one_signed_dispatch()
        except Exception as error:  # noqa: BLE001 - must observe any failure
            outcome["error"] = error

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread, outcome


class RealRoundTripTests(_LoopbackMtlsFixture):
    """A first-seen, valid, admitted signed dispatch is DECLINED on the
    wire; the identical dispatch replayed later is REPLAY_REJECTED."""

    def test_first_seen_valid_dispatch_is_declined(self) -> None:
        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        replay_protector = GuestAgentReplayProtector(_FakeReplayStore())
        envelope = _real_envelope(signing_key)

        server = GuestAgentSignedDispatchRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            verification_key=signing_key.public_key(),
            replay_protector=replay_protector,
            clock=lambda: NOW,
        )
        port = server.bind()
        thread, outcome = _run_server(server)

        client = GuestAgentSignedDispatchRpcClient(
            build_host_client_tls_context(host_config), host_config, port
        )
        response = client.send_signed_dispatch(envelope)
        thread.join(timeout=5.0)

        self.assertNotIn("error", outcome, msg=outcome.get("error"))
        self.assertEqual(response.status, GuestAgentResponseStatus.DECLINED)
        self.assertEqual(response.request_id, envelope.request.request_id)
        self.assertEqual(response.output_lines, ())
        self.assertEqual(response, outcome["response"])

    def test_replayed_identical_dispatch_is_replay_rejected(self) -> None:
        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        store = _FakeReplayStore()
        envelope = _real_envelope(signing_key)

        def _make_server() -> GuestAgentSignedDispatchRpcServer:
            server = GuestAgentSignedDispatchRpcServer(
                build_guest_server_tls_context(guest_config),
                guest_config,
                verification_key=signing_key.public_key(),
                replay_protector=GuestAgentReplayProtector(store),
                clock=lambda: NOW,
            )
            return server

        first_server = _make_server()
        port = first_server.bind()
        thread, outcome = _run_server(first_server)
        client_for_port = GuestAgentSignedDispatchRpcClient(
            build_host_client_tls_context(host_config), host_config, port
        )
        first_response = client_for_port.send_signed_dispatch(envelope)
        thread.join(timeout=5.0)
        self.assertEqual(first_response.status, GuestAgentResponseStatus.DECLINED)

        second_server = _make_server()
        second_port = second_server.bind()
        thread2, outcome2 = _run_server(second_server)
        client_for_second_port = GuestAgentSignedDispatchRpcClient(
            build_host_client_tls_context(host_config), host_config, second_port
        )
        second_response = client_for_second_port.send_signed_dispatch(envelope)
        thread2.join(timeout=5.0)

        self.assertNotIn("error", outcome2, msg=outcome2.get("error"))
        self.assertEqual(
            second_response.status, GuestAgentResponseStatus.REPLAY_REJECTED
        )
        self.assertEqual(second_response.request_id, first_response.request_id)
        self.assertEqual(second_response.output_lines, ())

    def test_https_header_lookup_operation_also_declines(self) -> None:
        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        envelope = _real_envelope(signing_key, preview=_https_preview())

        server = GuestAgentSignedDispatchRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            verification_key=signing_key.public_key(),
            replay_protector=GuestAgentReplayProtector(_FakeReplayStore()),
            clock=lambda: NOW,
        )
        port = server.bind()
        thread, outcome = _run_server(server)
        client = GuestAgentSignedDispatchRpcClient(
            build_host_client_tls_context(host_config), host_config, port
        )
        response = client.send_signed_dispatch(envelope)
        thread.join(timeout=5.0)
        self.assertNotIn("error", outcome, msg=outcome.get("error"))
        self.assertEqual(response.status, GuestAgentResponseStatus.DECLINED)

    def test_tls13_is_negotiated_on_both_sides(self) -> None:
        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        envelope = _real_envelope(signing_key)

        server = GuestAgentSignedDispatchRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            verification_key=signing_key.public_key(),
            replay_protector=GuestAgentReplayProtector(_FakeReplayStore()),
            clock=lambda: NOW,
        )
        port = server.bind()
        thread, outcome = _run_server(server)

        captured: list[object] = []
        original_wrap_socket = ssl.SSLContext.wrap_socket

        def _capturing(self_ctx, *args, **kwargs):
            wrapped = original_wrap_socket(self_ctx, *args, **kwargs)
            captured.append(wrapped.version())
            return wrapped

        client = GuestAgentSignedDispatchRpcClient(
            build_host_client_tls_context(host_config), host_config, port
        )
        with mock.patch.object(ssl.SSLContext, "wrap_socket", _capturing):
            client.send_signed_dispatch(envelope)
        thread.join(timeout=5.0)
        self.assertNotIn("error", outcome, msg=outcome.get("error"))
        self.assertTrue(captured)
        for version in captured:
            self.assertEqual(version, "TLSv1.3")


class OrderingTests(_LoopbackMtlsFixture):
    """Replay consumption must never occur before signature verification;
    admission must never be skipped by going straight to replay."""

    def test_verification_failure_prevents_admission_and_replay(self) -> None:
        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        envelope = _real_envelope(signing_key)
        store = _FakeReplayStore()
        replay_protector = GuestAgentReplayProtector(store)

        failure = GuestAgentDispatchVerificationFailure(
            stage=GuestAgentDispatchVerificationStage.SIGNATURE,
            reason="forced failure for ordering test",
        )

        server = GuestAgentSignedDispatchRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            verification_key=signing_key.public_key(),
            replay_protector=replay_protector,
            clock=lambda: NOW,
        )
        port = server.bind()

        with (
            mock.patch.object(
                transport_module,
                "verify_signed_dispatch_envelope",
                side_effect=GuestAgentDispatchVerificationError(failure),
            ) as mock_verify,
            mock.patch.object(
                transport_module, "admit_guest_agent_request"
            ) as mock_admit,
        ):
            thread, outcome = _run_server(server)
            client = GuestAgentSignedDispatchRpcClient(
                build_host_client_tls_context(host_config), host_config, port
            )
            with self.assertRaises(GuestAgentSignedDispatchRpcTransportError):
                client.send_signed_dispatch(envelope)
            thread.join(timeout=5.0)

        mock_verify.assert_called_once()
        mock_admit.assert_not_called()
        self.assertEqual(store.save_calls, 0)
        self.assertIn("error", outcome)
        self.assertEqual(
            outcome["error"].kind,  # type: ignore[union-attr]
            GuestAgentSignedDispatchRpcFailureKind.DISPATCH_VERIFICATION_FAILED,
        )

    def test_unsupported_capability_admission_skips_replay(self) -> None:
        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        envelope = _real_envelope(signing_key)
        store = _FakeReplayStore()
        replay_protector = GuestAgentReplayProtector(store)

        fake_response = GuestAgentResponse(
            protocol_version=envelope.request.protocol_version,
            request_id=envelope.request.request_id,
            status=GuestAgentResponseStatus.UNSUPPORTED_CAPABILITY,
            detail="Forced for ordering test.",
            output_lines=(),
        )

        server = GuestAgentSignedDispatchRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            verification_key=signing_key.public_key(),
            replay_protector=replay_protector,
            clock=lambda: NOW,
        )
        port = server.bind()

        with mock.patch.object(
            transport_module, "admit_guest_agent_request", return_value=fake_response
        ) as mock_admit:
            thread, outcome = _run_server(server)
            client = GuestAgentSignedDispatchRpcClient(
                build_host_client_tls_context(host_config), host_config, port
            )
            response = client.send_signed_dispatch(envelope)
            thread.join(timeout=5.0)

        mock_admit.assert_called_once()
        self.assertEqual(store.save_calls, 0)
        self.assertEqual(response, fake_response)
        self.assertNotIn("error", outcome, msg=outcome.get("error"))

    def test_invalid_request_admission_skips_replay(self) -> None:
        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        envelope = _real_envelope(signing_key)
        store = _FakeReplayStore()
        replay_protector = GuestAgentReplayProtector(store)

        fake_response = GuestAgentResponse(
            protocol_version=envelope.request.protocol_version,
            request_id=envelope.request.request_id,
            status=GuestAgentResponseStatus.INVALID_REQUEST,
            detail="Forced for ordering test.",
            output_lines=(),
        )

        server = GuestAgentSignedDispatchRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            verification_key=signing_key.public_key(),
            replay_protector=replay_protector,
            clock=lambda: NOW,
        )
        port = server.bind()

        with mock.patch.object(
            transport_module, "admit_guest_agent_request", return_value=fake_response
        ):
            thread, outcome = _run_server(server)
            client = GuestAgentSignedDispatchRpcClient(
                build_host_client_tls_context(host_config), host_config, port
            )
            response = client.send_signed_dispatch(envelope)
            thread.join(timeout=5.0)

        self.assertEqual(store.save_calls, 0)
        self.assertEqual(response, fake_response)
        self.assertNotIn("error", outcome, msg=outcome.get("error"))

    def test_declined_admission_consumes_replay_exactly_once(self) -> None:
        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        envelope = _real_envelope(signing_key)
        store = _FakeReplayStore()
        replay_protector = GuestAgentReplayProtector(store)

        server = GuestAgentSignedDispatchRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            verification_key=signing_key.public_key(),
            replay_protector=replay_protector,
            clock=lambda: NOW,
        )
        port = server.bind()
        thread, outcome = _run_server(server)
        client = GuestAgentSignedDispatchRpcClient(
            build_host_client_tls_context(host_config), host_config, port
        )
        response = client.send_signed_dispatch(envelope)
        thread.join(timeout=5.0)

        self.assertNotIn("error", outcome, msg=outcome.get("error"))
        self.assertEqual(response.status, GuestAgentResponseStatus.DECLINED)
        self.assertEqual(store.save_calls, 1)


class AdversarialVerificationTests(_LoopbackMtlsFixture):
    """Every verification failure aborts the connection with ZERO wire
    response, and replay is never consumed."""

    def _assert_aborted_without_replay(
        self, *, envelope, verification_key, store, clock, host_config, guest_config
    ) -> None:
        server = GuestAgentSignedDispatchRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            verification_key=verification_key,
            replay_protector=GuestAgentReplayProtector(store),
            clock=clock,
        )
        port = server.bind()
        thread, outcome = _run_server(server)
        client = GuestAgentSignedDispatchRpcClient(
            build_host_client_tls_context(host_config), host_config, port
        )
        with self.assertRaises(GuestAgentSignedDispatchRpcTransportError):
            client.send_signed_dispatch(envelope)
        thread.join(timeout=5.0)
        self.assertIn("error", outcome)
        self.assertIsInstance(
            outcome["error"], GuestAgentSignedDispatchRpcTransportError
        )
        self.assertEqual(
            outcome["error"].kind,  # type: ignore[union-attr]
            GuestAgentSignedDispatchRpcFailureKind.DISPATCH_VERIFICATION_FAILED,
        )
        self.assertEqual(store.save_calls, 0)

    def test_tampered_signature_aborts(self) -> None:
        import dataclasses

        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        envelope = _real_envelope(signing_key)
        tampered_proof = dataclasses.replace(
            envelope.proof,
            signature_hex=("0" if envelope.proof.signature_hex[0] != "0" else "1")
            + envelope.proof.signature_hex[1:],
        )
        tampered_envelope = dataclasses.replace(envelope, proof=tampered_proof)
        self._assert_aborted_without_replay(
            envelope=tampered_envelope,
            verification_key=signing_key.public_key(),
            store=_FakeReplayStore(),
            clock=lambda: NOW,
            host_config=host_config,
            guest_config=guest_config,
        )

    def test_tampered_request_field_aborts(self) -> None:
        import dataclasses

        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        envelope = _real_envelope(signing_key)
        tampered_request = dataclasses.replace(envelope.request, nonce="tampered-nonce")
        tampered_envelope = dataclasses.replace(envelope, request=tampered_request)
        self._assert_aborted_without_replay(
            envelope=tampered_envelope,
            verification_key=signing_key.public_key(),
            store=_FakeReplayStore(),
            clock=lambda: NOW,
            host_config=host_config,
            guest_config=guest_config,
        )

    def test_wrong_verification_key_aborts(self) -> None:
        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        wrong_key = Ed25519PrivateKey.generate().public_key()
        envelope = _real_envelope(signing_key)
        self._assert_aborted_without_replay(
            envelope=envelope,
            verification_key=wrong_key,
            store=_FakeReplayStore(),
            clock=lambda: NOW,
            host_config=host_config,
            guest_config=guest_config,
        )

    def test_expired_proof_aborts(self) -> None:
        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        envelope = _real_envelope(signing_key)
        self._assert_aborted_without_replay(
            envelope=envelope,
            verification_key=signing_key.public_key(),
            store=_FakeReplayStore(),
            clock=lambda: NOW + timedelta(seconds=61),
            host_config=host_config,
            guest_config=guest_config,
        )

    def test_not_yet_valid_proof_aborts(self) -> None:
        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        envelope = _real_envelope(signing_key)
        self._assert_aborted_without_replay(
            envelope=envelope,
            verification_key=signing_key.public_key(),
            store=_FakeReplayStore(),
            clock=lambda: NOW - timedelta(seconds=1),
            host_config=host_config,
            guest_config=guest_config,
        )


class EnvelopeDecodeFailureTests(_LoopbackMtlsFixture):
    """A malformed application frame aborts before verify/admit/replay."""

    def test_malformed_envelope_bytes_abort_before_verification(self) -> None:
        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        store = _FakeReplayStore()

        server = GuestAgentSignedDispatchRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            verification_key=signing_key.public_key(),
            replay_protector=GuestAgentReplayProtector(store),
            clock=lambda: NOW,
        )
        port = server.bind()

        with mock.patch.object(
            transport_module, "verify_signed_dispatch_envelope"
        ) as mock_verify:
            thread, outcome = _run_server(server)
            raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            raw_sock.settimeout(5.0)
            raw_sock.connect((transport_module.GUEST_AGENT_RPC_LOOPBACK_HOST, port))
            tls_context = build_host_client_tls_context(host_config)
            tls_conn = tls_context.wrap_socket(raw_sock, server_hostname=None)
            from research.GuestAgentRpcFraming import write_guest_agent_rpc_frame

            write_guest_agent_rpc_frame(tls_conn, b"not a valid envelope")
            try:
                received = tls_conn.recv(4)
            except OSError:
                received = b""
            tls_conn.close()
            thread.join(timeout=5.0)

        # Zero wire response bytes on this failure path: either the
        # connection is already closed (recv raises) or recv returns an
        # empty read -- never actual response bytes.
        self.assertEqual(received, b"")

        mock_verify.assert_not_called()
        self.assertEqual(store.save_calls, 0)
        self.assertIn("error", outcome)
        self.assertEqual(
            outcome["error"].kind,  # type: ignore[union-attr]
            GuestAgentSignedDispatchRpcFailureKind.ENVELOPE_DECODE_INVALID,
        )


class ReplayStoreFailureTests(_LoopbackMtlsFixture):
    def test_replay_store_save_failure_aborts_without_response(self) -> None:
        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        envelope = _real_envelope(signing_key)
        store = _FakeReplayStore(save_error=ResearchError("forced store failure"))

        server = GuestAgentSignedDispatchRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            verification_key=signing_key.public_key(),
            replay_protector=GuestAgentReplayProtector(store),
            clock=lambda: NOW,
        )
        port = server.bind()
        thread, outcome = _run_server(server)
        client = GuestAgentSignedDispatchRpcClient(
            build_host_client_tls_context(host_config), host_config, port
        )
        with self.assertRaises(GuestAgentSignedDispatchRpcTransportError):
            client.send_signed_dispatch(envelope)
        thread.join(timeout=5.0)

        self.assertIn("error", outcome)
        self.assertEqual(
            outcome["error"].kind,  # type: ignore[union-attr]
            GuestAgentSignedDispatchRpcFailureKind.REPLAY_CONSUMPTION_FAILED,
        )


class ConstructionValidationTests(_LoopbackMtlsFixture):
    def test_client_rejects_non_tls_context(self) -> None:
        host_config = self.host_config()
        for bad in (None, "not a context", object(), 123):
            with self.subTest(value=bad):
                with self.assertRaises(ResearchError):
                    GuestAgentSignedDispatchRpcClient(bad, host_config, 12345)  # type: ignore[arg-type]

    def test_client_rejects_invalid_port(self) -> None:
        host_config = self.host_config()
        tls_context = build_host_client_tls_context(host_config)
        for bad in (0, -1, 65536, "12345", 1.5, True, None):
            with self.subTest(value=bad):
                with self.assertRaises(ResearchError):
                    GuestAgentSignedDispatchRpcClient(
                        tls_context, host_config, bad  # type: ignore[arg-type]
                    )

    def test_client_rejects_invalid_timeouts(self) -> None:
        host_config = self.host_config()
        tls_context = build_host_client_tls_context(host_config)
        for bad in (None, "not timeouts", object(), 5.0):
            with self.subTest(value=bad):
                with self.assertRaises(ResearchError):
                    GuestAgentSignedDispatchRpcClient(
                        tls_context, host_config, 12345, timeouts=bad  # type: ignore[arg-type]
                    )

    def test_server_rejects_non_tls_context(self) -> None:
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        for bad in (None, "not a context", object(), 123):
            with self.subTest(value=bad):
                with self.assertRaises(ResearchError):
                    GuestAgentSignedDispatchRpcServer(
                        bad,  # type: ignore[arg-type]
                        guest_config,
                        verification_key=signing_key.public_key(),
                        replay_protector=GuestAgentReplayProtector(_FakeReplayStore()),
                    )

    def test_server_rejects_invalid_timeouts(self) -> None:
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        tls_context = build_guest_server_tls_context(guest_config)
        for bad in (None, "not timeouts", object(), 5.0):
            with self.subTest(value=bad):
                with self.assertRaises(ResearchError):
                    GuestAgentSignedDispatchRpcServer(
                        tls_context,
                        guest_config,
                        verification_key=signing_key.public_key(),
                        replay_protector=GuestAgentReplayProtector(_FakeReplayStore()),
                        timeouts=bad,  # type: ignore[arg-type]
                    )

    def test_client_rejects_guest_role_trust_configuration(self) -> None:
        guest_config = self.guest_config()
        with self.assertRaises(ResearchError):
            GuestAgentSignedDispatchRpcClient(
                build_guest_server_tls_context(guest_config), guest_config, 12345
            )

    def test_server_rejects_host_role_trust_configuration(self) -> None:
        host_config = self.host_config()
        signing_key = Ed25519PrivateKey.generate()
        with self.assertRaises(ResearchError):
            GuestAgentSignedDispatchRpcServer(
                build_host_client_tls_context(host_config),
                host_config,
                verification_key=signing_key.public_key(),
                replay_protector=GuestAgentReplayProtector(_FakeReplayStore()),
            )

    def test_server_rejects_non_ed25519_public_key(self) -> None:
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        for bad in (signing_key, "not a key", None, object()):
            with self.subTest(value=bad):
                with self.assertRaises(ResearchError):
                    GuestAgentSignedDispatchRpcServer(
                        build_guest_server_tls_context(guest_config),
                        guest_config,
                        verification_key=bad,  # type: ignore[arg-type]
                        replay_protector=GuestAgentReplayProtector(_FakeReplayStore()),
                    )

    def test_server_rejects_non_replay_protector(self) -> None:
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        for bad in ("not a protector", None, object()):
            with self.subTest(value=bad):
                with self.assertRaises(ResearchError):
                    GuestAgentSignedDispatchRpcServer(
                        build_guest_server_tls_context(guest_config),
                        guest_config,
                        verification_key=signing_key.public_key(),
                        replay_protector=bad,  # type: ignore[arg-type]
                    )

    def test_client_rejects_non_envelope_value(self) -> None:
        host_config = self.host_config()
        client = GuestAgentSignedDispatchRpcClient(
            build_host_client_tls_context(host_config), host_config, 12345
        )
        for bad in (None, "not an envelope", object(), 123):
            with self.subTest(value=bad):
                with self.assertRaises(ResearchError):
                    client.send_signed_dispatch(bad)  # type: ignore[arg-type]


class OneShotTests(_LoopbackMtlsFixture):
    def test_bind_twice_raises(self) -> None:
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        server = GuestAgentSignedDispatchRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            verification_key=signing_key.public_key(),
            replay_protector=GuestAgentReplayProtector(_FakeReplayStore()),
        )
        server.bind()
        with self.assertRaises(ResearchError):
            server.bind()
        server._listen_sock.close()  # type: ignore[union-attr]

    def test_serve_before_bind_raises(self) -> None:
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        server = GuestAgentSignedDispatchRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            verification_key=signing_key.public_key(),
            replay_protector=GuestAgentReplayProtector(_FakeReplayStore()),
        )
        with self.assertRaises(ResearchError):
            server.serve_one_signed_dispatch()

    def test_serve_twice_raises_on_second_call(self) -> None:
        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        envelope = _real_envelope(signing_key)
        server = GuestAgentSignedDispatchRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            verification_key=signing_key.public_key(),
            replay_protector=GuestAgentReplayProtector(_FakeReplayStore()),
            clock=lambda: NOW,
        )
        port = server.bind()
        thread, outcome = _run_server(server)
        client = GuestAgentSignedDispatchRpcClient(
            build_host_client_tls_context(host_config), host_config, port
        )
        client.send_signed_dispatch(envelope)
        thread.join(timeout=5.0)
        self.assertNotIn("error", outcome, msg=outcome.get("error"))
        with self.assertRaises(ResearchError):
            server.serve_one_signed_dispatch()


class FrameSizeTests(unittest.TestCase):
    def test_worst_case_envelope_fits_under_the_existing_frame_bound(self) -> None:
        from datetime import UTC as _UTC

        from research.GuestAgentDispatchProof import (
            DISPATCH_PROOF_GUEST_AUDIENCE_IDENTITY,
            DISPATCH_PROOF_HOST_ISSUER_IDENTITY,
            MAX_DISPATCH_PROOF_VALIDITY_SECONDS,
            GuestAgentDispatchAuthorizationProof,
            GuestAgentDispatchProofMetadata,
            GuestAgentDispatchProofVersion,
        )
        from research.GuestAgentProtocol import (
            MAX_LOGICAL_INPUT_FIELD_NAME_LENGTH,
            MAX_LOGICAL_INPUT_FIELDS,
            MAX_LOGICAL_INPUT_VALUE_LENGTH,
            MAX_NONCE_LENGTH,
            MAX_REQUEST_ID_LENGTH,
            GuestAgentProtocolVersion,
            GuestAgentRequest,
        )
        from research.ResearchKaliOperationPreview import ResearchKaliOperationKind

        astral = chr(0x1F600)
        request_id = (astral * (MAX_REQUEST_ID_LENGTH // 2 + 1))[:MAX_REQUEST_ID_LENGTH]
        nonce = (astral * (MAX_NONCE_LENGTH // 2 + 1))[:MAX_NONCE_LENGTH]
        logical_inputs = tuple(
            (
                ("x" * (MAX_LOGICAL_INPUT_FIELD_NAME_LENGTH - 2)) + str(i % 10) + "y",
                astral * (MAX_LOGICAL_INPUT_VALUE_LENGTH // 2),
            )
            for i in range(MAX_LOGICAL_INPUT_FIELDS)
        )
        request = GuestAgentRequest(
            protocol_version=GuestAgentProtocolVersion.V1,
            request_id=request_id,
            nonce=nonce,
            operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
            operation_digest="a" * 64,
            logical_inputs=logical_inputs,
        )
        now = datetime.now(_UTC)
        metadata = GuestAgentDispatchProofMetadata(
            proof_version=GuestAgentDispatchProofVersion.V1,
            request_sha256="b" * 64,
            issuer_identity=DISPATCH_PROOF_HOST_ISSUER_IDENTITY,
            audience_identity=DISPATCH_PROOF_GUEST_AUDIENCE_IDENTITY,
            issued_at=now,
            expires_at=now + timedelta(seconds=MAX_DISPATCH_PROOF_VALIDITY_SECONDS),
        )
        proof = GuestAgentDispatchAuthorizationProof(
            metadata=metadata, signature_hex="c" * 128
        )
        envelope = GuestAgentSignedDispatchEnvelope(request=request, proof=proof)
        data = canonical_guest_agent_signed_dispatch_envelope_bytes(envelope)
        self.assertLess(len(data), MAX_GUEST_AGENT_RPC_FRAME_SIZE)
        # Comfortable headroom, not a coincidental near-miss.
        self.assertLess(len(data), MAX_GUEST_AGENT_RPC_FRAME_SIZE - 100_000)


class StructuralSecurityTests(unittest.TestCase):
    """AST-based proof of ordering, non-genericization, and no capability
    executor -- mirroring the existing structural test patterns exactly."""

    def setUp(self) -> None:
        self.tree = ast.parse(
            TRANSPORT_MODULE_FILE.read_text(encoding="utf-8"),
            filename=str(TRANSPORT_MODULE_FILE),
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

    def test_no_capability_executor_or_process_adapter_reference(self) -> None:
        forbidden = {
            "GuestAgentCapabilityExecutor",
            "GuestAgentDnsExecutor",
            "GuestAgentHttpsExecutor",
            "ResearchKaliOperationProcessAdapter",
            "KaliToolGateway",
            "ToolExecutionService",
            "subprocess",
            "dig",
            "curl",
            "nmap",
        }
        self.assertEqual(self._referenced_names(self.tree) & forbidden, set())

    def test_no_generic_byte_transport_method_names(self) -> None:
        forbidden = {
            "send_bytes",
            "send_payload",
            "serve_bytes",
            "dispatch_raw",
            "handle_blob",
        }
        function_names = {
            node.name
            for node in ast.walk(self.tree)
            if isinstance(node, ast.FunctionDef)
        }
        self.assertEqual(function_names & forbidden, set())

    def test_server_constructor_has_no_injectable_handler_parameter(self) -> None:
        parameters = set(
            inspect.signature(GuestAgentSignedDispatchRpcServer.__init__).parameters
        )
        self.assertNotIn("handler", parameters)

    def test_send_signed_dispatch_contains_no_retry_loop(self) -> None:
        send_def = None
        for node in ast.walk(self.tree):
            if (
                isinstance(node, ast.FunctionDef)
                and node.name == "send_signed_dispatch"
            ):
                send_def = node
                break
        self.assertIsNotNone(send_def)
        for inner in ast.walk(send_def):  # type: ignore[arg-type]
            self.assertNotIsInstance(inner, (ast.For, ast.While))

    def test_serve_one_signed_dispatch_contains_no_loop(self) -> None:
        serve_def = None
        for node in ast.walk(self.tree):
            if (
                isinstance(node, ast.FunctionDef)
                and node.name == "serve_one_signed_dispatch"
            ):
                serve_def = node
                break
        self.assertIsNotNone(serve_def)
        for inner in ast.walk(serve_def):  # type: ignore[arg-type]
            self.assertNotIsInstance(inner, (ast.For, ast.While))

    def test_verify_then_admit_then_replay_consume_in_source_order(self) -> None:
        def _first_call_lineno(name_fragment: str) -> int:
            matches = []
            for node in ast.walk(self.tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if isinstance(func, ast.Name) and func.id == name_fragment:
                    matches.append(node.lineno)
                elif isinstance(func, ast.Attribute) and func.attr == name_fragment:
                    matches.append(node.lineno)
            self.assertTrue(matches, f"no call to {name_fragment!r} found")
            return min(matches)

        verify_line = _first_call_lineno("verify_signed_dispatch_envelope")
        admit_line = _first_call_lineno("admit_guest_agent_request")
        consume_line = _first_call_lineno("consume_once")
        self.assertLess(verify_line, admit_line)
        self.assertLess(admit_line, consume_line)

    def test_exactly_one_consume_once_call_site(self) -> None:
        calls = [
            node
            for node in ast.walk(self.tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "consume_once"
        ]
        self.assertEqual(len(calls), 1)

    def test_separate_failure_kind_enum_from_plain_transport(self) -> None:
        from research.GuestAgentRpcTransport import GuestAgentRpcFailureKind

        self.assertIsNot(
            GuestAgentSignedDispatchRpcFailureKind, GuestAgentRpcFailureKind
        )

    def test_authenticate_tls_peer_is_reused_not_reimplemented(self) -> None:
        import research.GuestAgentRpcTransport as plain_transport_module

        self.assertIs(
            transport_module._authenticate_tls_peer,
            plain_transport_module._authenticate_tls_peer,
        )

    def test_every_bind_or_connect_call_targets_loopback_only(self) -> None:
        found_any = False
        for node in ast.walk(self.tree):
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
            if isinstance(host_node, ast.Constant) and isinstance(host_node.value, str):
                self.assertEqual(host_node.value, "127.0.0.1")
            elif isinstance(host_node, ast.Name):
                self.assertEqual(host_node.id, "GUEST_AGENT_RPC_LOOPBACK_HOST")
            else:
                self.fail(f"unrecognized bind/connect host argument: {host_node}")
        self.assertTrue(found_any)


if __name__ == "__main__":
    unittest.main()
