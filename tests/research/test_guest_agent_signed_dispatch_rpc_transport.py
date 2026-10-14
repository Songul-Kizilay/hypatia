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

import research.GuestAgentInvocationPreparation as preparation_module  # noqa: E402
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
from research.GuestAgentDnsExecutionAdapter import (  # noqa: E402
    execute_guest_agent_dns_record_lookup,
)
from research.GuestAgentExecutionAdmission import (  # noqa: E402
    GuestAgentExecutionBoundaryReceipt,
    admit_guest_agent_execution,
)
from research.GuestAgentHostAuthorizationHandoff import (  # noqa: E402
    consume_authorization_for_guest_agent_dispatch,
)
from research.GuestAgentLocalReadiness import (  # noqa: E402
    GuestAgentLocalReadinessProbe,
    GuestAgentLocalReadinessReceipt,
    GuestAgentLocalReadinessState,
)
from research.GuestAgentMtlsContext import (  # noqa: E402
    build_guest_server_tls_context,
    build_host_client_tls_context,
)
from research.GuestAgentProtocol import (
    MAX_RESPONSE_DETAIL_LENGTH,
    GuestAgentProtocolVersion,
    GuestAgentResponse,
    GuestAgentResponseStatus,
)  # noqa: E402
from research.GuestAgentProtocolSerialization import (  # noqa: E402
    canonical_guest_agent_response_bytes,
)
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
from research.ResearchKaliOperationExecution import (  # noqa: E402
    KALI_OPERATION_OUTPUT_TRUST,
    MAX_KALI_OPERATION_OUTPUT_LINE_CHARACTERS,
    MAX_KALI_OPERATION_OUTPUT_LINES,
)
from research.ResearchKaliOperationPreview import (  # noqa: E402
    ResearchKaliCommandTransport,
    ResearchKaliOperationKind,
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
PREPARATION_MODULE_FILE = SRC_DIR / "research" / "GuestAgentInvocationPreparation.py"

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
    wire; the identical dispatch replayed later is REPLAY_REJECTED.

    v0.3.466 note: `_real_envelope` now always carries a V2
    (execution-bound) request -- `GuestAgentHostDispatchGrant
    .materialize_request` always produces V2 since this milestone (see
    its own docstring) -- so every test in this class already exercises
    the V2 path end-to-end, including silent prepared-invocation
    construction/discard, with no change to the wire-observable
    behavior v0.3.465 already established.
    """

    def test_first_seen_valid_dispatch_is_declined(self) -> None:
        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        replay_protector = GuestAgentReplayProtector(_FakeReplayStore())
        envelope = _real_envelope(signing_key)
        self.assertIs(envelope.request.protocol_version, GuestAgentProtocolVersion.V2)
        self.assertIsNotNone(envelope.request.execution_limits)

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


def _sign_arbitrary_request_for_test(
    request,
    *,
    signing_key: Ed25519PrivateKey,
    now: datetime,
) -> GuestAgentSignedDispatchEnvelope:
    """Test-only: sign ANY request, bypassing the one real production entry
    point (`create_signed_dispatch_envelope`, which accepts only an
    already-consumed `GuestAgentHostDispatchGrant` and therefore -- since
    v0.3.466 -- can only ever produce V2). `materialize_request` always
    produces V2 now, so this is the only way to exercise "V1 RPC BEHAVIOR"
    end-to-end over a real signed envelope; it performs the identical
    signing steps `create_signed_dispatch_envelope` performs internally,
    just without requiring a grant."""
    import hashlib
    from datetime import timedelta

    from research.GuestAgentDispatchProof import (
        DISPATCH_PROOF_GUEST_AUDIENCE_IDENTITY,
        DISPATCH_PROOF_HOST_ISSUER_IDENTITY,
        MAX_DISPATCH_PROOF_VALIDITY_SECONDS,
        GuestAgentDispatchAuthorizationProof,
        GuestAgentDispatchProofMetadata,
        GuestAgentDispatchProofVersion,
        canonical_guest_agent_dispatch_proof_metadata_bytes,
    )
    from research.GuestAgentProtocolSerialization import (
        canonical_guest_agent_request_bytes,
    )

    metadata = GuestAgentDispatchProofMetadata(
        proof_version=GuestAgentDispatchProofVersion.V1,
        request_sha256=hashlib.sha256(
            canonical_guest_agent_request_bytes(request)
        ).hexdigest(),
        issuer_identity=DISPATCH_PROOF_HOST_ISSUER_IDENTITY,
        audience_identity=DISPATCH_PROOF_GUEST_AUDIENCE_IDENTITY,
        issued_at=now,
        expires_at=now + timedelta(seconds=MAX_DISPATCH_PROOF_VALIDITY_SECONDS),
    )
    signature = signing_key.sign(
        canonical_guest_agent_dispatch_proof_metadata_bytes(metadata)
    )
    proof = GuestAgentDispatchAuthorizationProof(
        metadata=metadata, signature_hex=signature.hex()
    )
    return GuestAgentSignedDispatchEnvelope(request=request, proof=proof)


class V1OverRealWireTests(_LoopbackMtlsFixture):
    """V1 RPC BEHAVIOR: a manually-signed V1 request still verifies, is
    still admitted/DECLINED, and replay behavior remains compatible --
    but it never carries a prepared invocation (not observable on the
    wire; proven directly against `prepare_guest_agent_invocation` in
    tests.research.test_guest_agent_invocation_preparation)."""

    def _v1_request(self):
        from research.GuestAgentProtocol import (
            GuestAgentProtocolVersion,
            GuestAgentRequest,
        )
        from research.ResearchKaliOperationPreview import ResearchKaliOperationKind

        return GuestAgentRequest(
            protocol_version=GuestAgentProtocolVersion.V1,
            request_id="v1-r1",
            nonce="v1-n1",
            operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
            operation_digest="a" * 64,
            logical_inputs=(("hostname", "example.com"), ("dns_record_type", "A")),
        )

    def test_v1_first_seen_dispatch_is_declined(self) -> None:
        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        envelope = _sign_arbitrary_request_for_test(
            self._v1_request(), signing_key=signing_key, now=NOW
        )
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

    def test_v1_replayed_dispatch_is_replay_rejected(self) -> None:
        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        envelope = _sign_arbitrary_request_for_test(
            self._v1_request(), signing_key=signing_key, now=NOW
        )
        store = _FakeReplayStore()

        def _make_server() -> GuestAgentSignedDispatchRpcServer:
            return GuestAgentSignedDispatchRpcServer(
                build_guest_server_tls_context(guest_config),
                guest_config,
                verification_key=signing_key.public_key(),
                replay_protector=GuestAgentReplayProtector(store),
                clock=lambda: NOW,
            )

        first_server = _make_server()
        first_port = first_server.bind()
        thread1, outcome1 = _run_server(first_server)
        client1 = GuestAgentSignedDispatchRpcClient(
            build_host_client_tls_context(host_config), host_config, first_port
        )
        client1.send_signed_dispatch(envelope)
        thread1.join(timeout=5.0)
        self.assertNotIn("error", outcome1, msg=outcome1.get("error"))

        second_server = _make_server()
        second_port = second_server.bind()
        thread2, outcome2 = _run_server(second_server)
        client2 = GuestAgentSignedDispatchRpcClient(
            build_host_client_tls_context(host_config), host_config, second_port
        )
        response2 = client2.send_signed_dispatch(envelope)
        thread2.join(timeout=5.0)
        self.assertNotIn("error", outcome2, msg=outcome2.get("error"))
        self.assertEqual(response2.status, GuestAgentResponseStatus.REPLAY_REJECTED)


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
                preparation_module, "admit_guest_agent_request"
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
            preparation_module, "admit_guest_agent_request", return_value=fake_response
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
            preparation_module, "admit_guest_agent_request", return_value=fake_response
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

    def test_tampered_max_seconds_aborts(self) -> None:
        import dataclasses

        from research.GuestAgentProtocol import GuestAgentExecutionLimits

        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        envelope = _real_envelope(signing_key)
        self.assertIsNotNone(envelope.request.execution_limits)
        tampered_request = dataclasses.replace(
            envelope.request,
            execution_limits=GuestAgentExecutionLimits(
                max_seconds=envelope.request.execution_limits.max_seconds + 1.0
            ),
        )
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
            GuestAgentExecutionLimits,
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
        # V2 (execution-bound) is now the worst case: it carries every V1
        # field plus `execution_limits`.
        request = GuestAgentRequest(
            protocol_version=GuestAgentProtocolVersion.V2,
            request_id=request_id,
            nonce=nonce,
            operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
            operation_digest="a" * 64,
            logical_inputs=logical_inputs,
            execution_limits=GuestAgentExecutionLimits(max_seconds=30.0),
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
        self.preparation_tree = ast.parse(
            PREPARATION_MODULE_FILE.read_text(encoding="utf-8"),
            filename=str(PREPARATION_MODULE_FILE),
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

    @staticmethod
    def _first_call_lineno(tree: ast.AST, name_fragment: str) -> int:
        matches = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name) and func.id == name_fragment:
                matches.append(node.lineno)
            elif isinstance(func, ast.Attribute) and func.attr == name_fragment:
                matches.append(node.lineno)
        return min(matches) if matches else -1

    def test_verify_then_prepare_invocation_in_source_order(self) -> None:
        """`serve_one_signed_dispatch` calls `verify_signed_dispatch_envelope`
        before it calls `prepare_guest_agent_invocation` -- the shared
        function that itself composes admit -> replay-consume (proven
        separately below, within that function's own module)."""
        verify_line = self._first_call_lineno(
            self.tree, "verify_signed_dispatch_envelope"
        )
        prepare_line = self._first_call_lineno(
            self.tree, "prepare_guest_agent_invocation"
        )
        self.assertGreater(verify_line, 0, "no call to verify_signed_dispatch_envelope")
        self.assertGreater(prepare_line, 0, "no call to prepare_guest_agent_invocation")
        self.assertLess(verify_line, prepare_line)

    def test_prepare_then_readiness_in_source_order(self) -> None:
        """`serve_one_signed_dispatch` calls `prepare_guest_agent_invocation`
        before it ever calls `check_guest_agent_runtime_readiness` -- local
        readiness must never be checked before a prepared invocation exists
        (which itself requires fresh replay acceptance)."""
        prepare_line = self._first_call_lineno(
            self.tree, "prepare_guest_agent_invocation"
        )
        readiness_line = self._first_call_lineno(
            self.tree, "check_guest_agent_runtime_readiness"
        )
        self.assertGreater(prepare_line, 0, "no call to prepare_guest_agent_invocation")
        self.assertGreater(
            readiness_line, 0, "no call to check_guest_agent_runtime_readiness"
        )
        self.assertLess(prepare_line, readiness_line)

    def test_readiness_call_is_guarded_by_prepared_invocation_none_check(self) -> None:
        """The one `check_guest_agent_runtime_readiness` call site is
        structurally inside an `if _prepared_invocation is not None:` block
        -- never unconditional -- so V1 and replay-rejected paths (where
        `_prepared_invocation` is `None`) cannot reach it by construction."""
        serve_def = None
        for node in ast.walk(self.tree):
            if (
                isinstance(node, ast.FunctionDef)
                and node.name == "serve_one_signed_dispatch"
            ):
                serve_def = node
                break
        self.assertIsNotNone(serve_def)
        guarding_if = None
        for node in ast.walk(serve_def):  # type: ignore[arg-type]
            if isinstance(node, ast.If):
                readiness_calls = [
                    inner
                    for inner in ast.walk(node)
                    if isinstance(inner, ast.Call)
                    and isinstance(inner.func, ast.Name)
                    and inner.func.id == "check_guest_agent_runtime_readiness"
                ]
                if readiness_calls:
                    guarding_if = node
                    break
        self.assertIsNotNone(
            guarding_if, "check_guest_agent_runtime_readiness is not inside an if-block"
        )
        test_source = ast.unparse(guarding_if.test)  # type: ignore[union-attr]
        self.assertIn("_prepared_invocation", test_source)
        self.assertIn("is not None", test_source)

    def test_readiness_then_admission_in_source_order(self) -> None:
        """`serve_one_signed_dispatch` calls
        `check_guest_agent_runtime_readiness` before it ever calls
        `admit_guest_agent_execution` -- execution admission must never be
        attempted before readiness has run."""
        readiness_line = self._first_call_lineno(
            self.tree, "check_guest_agent_runtime_readiness"
        )
        admission_line = self._first_call_lineno(
            self.tree, "admit_guest_agent_execution"
        )
        self.assertGreater(
            readiness_line, 0, "no call to check_guest_agent_runtime_readiness"
        )
        self.assertGreater(admission_line, 0, "no call to admit_guest_agent_execution")
        self.assertLess(readiness_line, admission_line)

    def test_admission_call_is_guarded_by_ready_invocation_none_check(self) -> None:
        """The one `admit_guest_agent_execution` call site is structurally
        inside an `if _ready_invocation is not None:` block -- never
        unconditional -- so a V1 path, a replay-rejected path, and a
        readiness-`UNAVAILABLE` path (where `_ready_invocation` is `None`
        in every case) cannot reach it by construction."""
        serve_def = None
        for node in ast.walk(self.tree):
            if (
                isinstance(node, ast.FunctionDef)
                and node.name == "serve_one_signed_dispatch"
            ):
                serve_def = node
                break
        self.assertIsNotNone(serve_def)
        # There are two nested `if ... is not None:` guards here (the
        # outer `_prepared_invocation` readiness guard, the inner
        # `_ready_invocation` admission guard) -- find the INNERMOST one
        # that directly contains the admission call, not merely any
        # enclosing one.
        candidate_ifs = [
            node
            for node in ast.walk(serve_def)  # type: ignore[arg-type]
            if isinstance(node, ast.If)
            and any(
                isinstance(inner, ast.Call)
                and isinstance(inner.func, ast.Name)
                and inner.func.id == "admit_guest_agent_execution"
                for inner in ast.walk(node)
            )
        ]
        self.assertTrue(
            candidate_ifs, "admit_guest_agent_execution is not inside an if-block"
        )
        guarding_if = min(candidate_ifs, key=lambda node: len(list(ast.walk(node))))
        test_source = ast.unparse(guarding_if.test)
        self.assertIn("_ready_invocation", test_source)
        self.assertIn("is not None", test_source)

    def test_admit_then_replay_consume_in_source_order_within_preparation(
        self,
    ) -> None:
        """Within `research.GuestAgentInvocationPreparation` itself,
        `admit_guest_agent_request` precedes the sole `consume_once` call
        site -- the composition this milestone reuses rather than
        duplicating inline in the transport module."""
        admit_line = self._first_call_lineno(
            self.preparation_tree, "admit_guest_agent_request"
        )
        consume_line = self._first_call_lineno(self.preparation_tree, "consume_once")
        self.assertGreater(admit_line, 0, "no call to admit_guest_agent_request")
        self.assertGreater(consume_line, 0, "no call to consume_once")
        self.assertLess(admit_line, consume_line)

    def test_exactly_one_consume_once_call_site(self) -> None:
        calls = [
            node
            for node in ast.walk(self.preparation_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "consume_once"
        ]
        self.assertEqual(len(calls), 1)

    def test_exactly_one_prepare_guest_agent_invocation_call_site_in_transport(
        self,
    ) -> None:
        calls = [
            node
            for node in ast.walk(self.tree)
            if isinstance(node, ast.Call)
            and (
                (
                    isinstance(node.func, ast.Name)
                    and node.func.id == "prepare_guest_agent_invocation"
                )
                or (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "prepare_guest_agent_invocation"
                )
            )
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


class _RecordingLocalReadinessProbe(GuestAgentLocalReadinessProbe):
    """Test double: returns a canned receipt per call, records every
    prepared invocation it was handed, and never touches `subprocess`."""

    def __init__(self, receipt: GuestAgentLocalReadinessReceipt) -> None:
        self._receipt = receipt
        self.calls: list = []

    def check(self, prepared_invocation):  # type: ignore[no-untyped-def]
        self.calls.append(prepared_invocation)
        return self._receipt


def _ready_receipt_for(operation_kind) -> GuestAgentLocalReadinessReceipt:  # type: ignore[no-untyped-def]
    return GuestAgentLocalReadinessReceipt(
        operation_kind=operation_kind,
        state=GuestAgentLocalReadinessState.READY,
        reason="simulated ready for integration test",
        executable_path="/usr/bin/dig",
        observed_version="DiG 9.18.0",
        probe_process_started=True,
    )


def _unavailable_receipt_for(operation_kind) -> GuestAgentLocalReadinessReceipt:  # type: ignore[no-untyped-def]
    return GuestAgentLocalReadinessReceipt(
        operation_kind=operation_kind,
        state=GuestAgentLocalReadinessState.UNAVAILABLE,
        reason="simulated unavailable for integration test",
    )


class ReadinessIntegrationTests(_LoopbackMtlsFixture):
    """v0.3.467: local runtime readiness composed into the real RPC server.

    Readiness itself is observed only through the injected probe's own
    call count/arguments. Before v0.3.470, the wire response stayed
    `DECLINED` regardless of readiness outcome for every operation kind --
    that remains true for HTTPS and for `UNAVAILABLE` readiness today, but
    a READY DNS request now reaches real execution (see
    `DnsRpcExecutionTests` for the full SUCCESS/FAILED proof); every test
    below that exercises that exact scenario mocks `subprocess.run`
    deterministically, never performing a real DNS query."""

    def test_v1_request_never_reaches_readiness(self) -> None:
        from research.GuestAgentProtocol import GuestAgentRequest

        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        v1_request = GuestAgentRequest(
            protocol_version=GuestAgentProtocolVersion.V1,
            request_id="v1-readiness",
            nonce="v1-readiness-nonce",
            operation_kind=_preview().operation_kind,
            operation_digest="a" * 64,
            logical_inputs=(("hostname", "example.com"), ("dns_record_type", "A")),
        )
        envelope = _sign_arbitrary_request_for_test(
            v1_request, signing_key=signing_key, now=NOW
        )
        probe = _RecordingLocalReadinessProbe(
            _ready_receipt_for(v1_request.operation_kind)
        )
        server = GuestAgentSignedDispatchRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            verification_key=signing_key.public_key(),
            replay_protector=GuestAgentReplayProtector(_FakeReplayStore()),
            clock=lambda: NOW,
            local_runtime_probe=probe,
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
        self.assertEqual(probe.calls, [])

    def test_replayed_v2_request_never_reaches_readiness(self) -> None:
        """v0.3.470 note: the default preview is DNS, so once admitted and
        READY this dispatch now reaches real execution -- `subprocess.run`
        is mocked deterministically (never a real DNS query) so this test
        stays safe to run anywhere, including CI."""
        import subprocess as subprocess_module

        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        store = _FakeReplayStore()
        envelope = _real_envelope(signing_key)
        probe = _RecordingLocalReadinessProbe(
            _ready_receipt_for(envelope.request.operation_kind)
        )

        def _make_server() -> GuestAgentSignedDispatchRpcServer:
            return GuestAgentSignedDispatchRpcServer(
                build_guest_server_tls_context(guest_config),
                guest_config,
                verification_key=signing_key.public_key(),
                replay_protector=GuestAgentReplayProtector(store),
                clock=lambda: NOW,
                local_runtime_probe=probe,
            )

        with mock.patch.object(
            subprocess_module,
            "run",
            return_value=subprocess_module.CompletedProcess(
                args=(), returncode=0, stdout="1.2.3.4\n", stderr=""
            ),
        ) as run:
            first_server = _make_server()
            first_port = first_server.bind()
            thread1, outcome1 = _run_server(first_server)
            client1 = GuestAgentSignedDispatchRpcClient(
                build_host_client_tls_context(host_config), host_config, first_port
            )
            client1.send_signed_dispatch(envelope)
            thread1.join(timeout=5.0)
            self.assertNotIn("error", outcome1, msg=outcome1.get("error"))
            self.assertEqual(len(probe.calls), 1)  # the first-seen dispatch

            second_server = _make_server()
            second_port = second_server.bind()
            thread2, outcome2 = _run_server(second_server)
            client2 = GuestAgentSignedDispatchRpcClient(
                build_host_client_tls_context(host_config), host_config, second_port
            )
            response2 = client2.send_signed_dispatch(envelope)
            thread2.join(timeout=5.0)
            self.assertNotIn("error", outcome2, msg=outcome2.get("error"))
            self.assertEqual(response2.status, GuestAgentResponseStatus.REPLAY_REJECTED)
            # The replay never added a second call: readiness ran exactly
            # once, for the first-seen dispatch only, and the DNS executor
            # itself ran at most once overall -- never retried for the
            # replay.
            self.assertEqual(len(probe.calls), 1)
            run.assert_called_once()

    def test_ready_first_seen_dns_v2_request_reaches_readiness_once(self) -> None:
        """v0.3.470 note: readiness `READY` for a DNS request no longer
        implies the wire stays `DECLINED` -- once v0.3.470 wired a real
        executor in, this exact scenario (readiness `READY`, admission
        succeeds) now reaches real execution. That full SUCCESS/FAILED
        proof lives in `DnsRpcExecutionTests` below; this test keeps its
        original, narrower scope: readiness itself is still reached
        exactly once for the first-seen dispatch. `subprocess.run` is
        mocked deterministically -- never a real DNS query."""
        import subprocess as subprocess_module

        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        envelope = _real_envelope(signing_key, preview=_preview())
        probe = _RecordingLocalReadinessProbe(
            _ready_receipt_for(envelope.request.operation_kind)
        )
        server = GuestAgentSignedDispatchRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            verification_key=signing_key.public_key(),
            replay_protector=GuestAgentReplayProtector(_FakeReplayStore()),
            clock=lambda: NOW,
            local_runtime_probe=probe,
        )
        port = server.bind()
        with mock.patch.object(
            subprocess_module,
            "run",
            return_value=subprocess_module.CompletedProcess(
                args=(), returncode=0, stdout="1.2.3.4\n", stderr=""
            ),
        ):
            thread, outcome = _run_server(server)
            client = GuestAgentSignedDispatchRpcClient(
                build_host_client_tls_context(host_config), host_config, port
            )
            response = client.send_signed_dispatch(envelope)
            thread.join(timeout=5.0)
        self.assertNotIn("error", outcome, msg=outcome.get("error"))
        self.assertEqual(response.status, GuestAgentResponseStatus.SUCCESS)
        self.assertEqual(len(probe.calls), 1)
        prepared = probe.calls[0]
        self.assertEqual(
            prepared.operation_kind, ResearchKaliOperationKind.DNS_RECORD_LOOKUP
        )
        self.assertIs(
            prepared.command_plan.transport, ResearchKaliCommandTransport.GUEST_AGENT
        )

    def test_ready_first_seen_https_v2_request_still_declined_on_wire(self) -> None:
        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        envelope = _real_envelope(signing_key, preview=_https_preview())
        probe = _RecordingLocalReadinessProbe(
            _ready_receipt_for(envelope.request.operation_kind)
        )
        server = GuestAgentSignedDispatchRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            verification_key=signing_key.public_key(),
            replay_protector=GuestAgentReplayProtector(_FakeReplayStore()),
            clock=lambda: NOW,
            local_runtime_probe=probe,
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
        self.assertEqual(len(probe.calls), 1)
        self.assertEqual(
            probe.calls[0].operation_kind,
            ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP,
        )

    def test_unavailable_readiness_still_declined_never_success(self) -> None:
        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        envelope = _real_envelope(signing_key)
        probe = _RecordingLocalReadinessProbe(
            _unavailable_receipt_for(envelope.request.operation_kind)
        )
        server = GuestAgentSignedDispatchRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            verification_key=signing_key.public_key(),
            replay_protector=GuestAgentReplayProtector(_FakeReplayStore()),
            clock=lambda: NOW,
            local_runtime_probe=probe,
        )
        port = server.bind()
        thread, outcome = _run_server(server)
        client = GuestAgentSignedDispatchRpcClient(
            build_host_client_tls_context(host_config), host_config, port
        )
        response = client.send_signed_dispatch(envelope)
        thread.join(timeout=5.0)
        self.assertNotIn("error", outcome, msg=outcome.get("error"))
        self.assertNotEqual(response.status, GuestAgentResponseStatus.SUCCESS)
        self.assertEqual(response.status, GuestAgentResponseStatus.DECLINED)
        self.assertEqual(len(probe.calls), 1)

    def test_default_server_uses_unavailable_probe_with_zero_subprocess(self) -> None:
        """A server constructed without `local_runtime_probe` (every
        existing v0.3.465/v0.3.466 test in this file does this) must still
        start zero subprocesses -- the default probe fails closed."""
        import subprocess as subprocess_module

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
        with mock.patch.object(subprocess_module, "run") as run:
            thread, outcome = _run_server(server)
            client = GuestAgentSignedDispatchRpcClient(
                build_host_client_tls_context(host_config), host_config, port
            )
            response = client.send_signed_dispatch(envelope)
            thread.join(timeout=5.0)
        self.assertNotIn("error", outcome, msg=outcome.get("error"))
        self.assertEqual(response.status, GuestAgentResponseStatus.DECLINED)
        run.assert_not_called()


class ExecutionAdmissionIntegrationTests(_LoopbackMtlsFixture):
    """v0.3.468: exact-request execution admission composed into the real
    RPC server, strictly after readiness `READY`.

    Admission is observed only through a spy on `admit_guest_agent_execution`
    itself (`mock.patch.object(..., wraps=...)`, preserving real behavior).
    Before v0.3.470, admission succeeding never changed the wire response
    for any operation kind -- that remains true for HTTPS today, but a
    successful DNS admission now reaches real execution (see
    `DnsRpcExecutionTests` for the full SUCCESS/FAILED proof); every test
    below that exercises that exact scenario mocks `subprocess.run`
    deterministically, never performing a real DNS query."""

    def test_v1_request_never_reaches_execution_admission(self) -> None:
        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        from research.GuestAgentProtocol import GuestAgentRequest

        v1_request = GuestAgentRequest(
            protocol_version=GuestAgentProtocolVersion.V1,
            request_id="v1-admission",
            nonce="v1-admission-nonce",
            operation_kind=_preview().operation_kind,
            operation_digest="a" * 64,
            logical_inputs=(("hostname", "example.com"), ("dns_record_type", "A")),
        )
        envelope = _sign_arbitrary_request_for_test(
            v1_request, signing_key=signing_key, now=NOW
        )
        probe = _RecordingLocalReadinessProbe(
            _ready_receipt_for(v1_request.operation_kind)
        )
        server = GuestAgentSignedDispatchRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            verification_key=signing_key.public_key(),
            replay_protector=GuestAgentReplayProtector(_FakeReplayStore()),
            clock=lambda: NOW,
            local_runtime_probe=probe,
        )
        port = server.bind()
        with mock.patch.object(
            transport_module,
            "admit_guest_agent_execution",
            wraps=admit_guest_agent_execution,
        ) as admission_spy:
            thread, outcome = _run_server(server)
            client = GuestAgentSignedDispatchRpcClient(
                build_host_client_tls_context(host_config), host_config, port
            )
            response = client.send_signed_dispatch(envelope)
            thread.join(timeout=5.0)
        self.assertNotIn("error", outcome, msg=outcome.get("error"))
        self.assertEqual(response.status, GuestAgentResponseStatus.DECLINED)
        admission_spy.assert_not_called()
        self.assertEqual(probe.calls, [])

    def test_replayed_request_never_reaches_execution_admission(self) -> None:
        """v0.3.470 note: the default preview is DNS, so this dispatch now
        reaches real execution once admitted -- `subprocess.run` is mocked
        deterministically, never a real DNS query."""
        import subprocess as subprocess_module

        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        store = _FakeReplayStore()
        envelope = _real_envelope(signing_key)
        probe = _RecordingLocalReadinessProbe(
            _ready_receipt_for(envelope.request.operation_kind)
        )

        def _make_server() -> GuestAgentSignedDispatchRpcServer:
            return GuestAgentSignedDispatchRpcServer(
                build_guest_server_tls_context(guest_config),
                guest_config,
                verification_key=signing_key.public_key(),
                replay_protector=GuestAgentReplayProtector(store),
                clock=lambda: NOW,
                local_runtime_probe=probe,
            )

        with (
            mock.patch.object(
                transport_module,
                "admit_guest_agent_execution",
                wraps=admit_guest_agent_execution,
            ) as admission_spy,
            mock.patch.object(
                subprocess_module,
                "run",
                return_value=subprocess_module.CompletedProcess(
                    args=(), returncode=0, stdout="1.2.3.4\n", stderr=""
                ),
            ) as run,
        ):
            first_server = _make_server()
            first_port = first_server.bind()
            thread1, outcome1 = _run_server(first_server)
            client1 = GuestAgentSignedDispatchRpcClient(
                build_host_client_tls_context(host_config), host_config, first_port
            )
            client1.send_signed_dispatch(envelope)
            thread1.join(timeout=5.0)
            self.assertNotIn("error", outcome1, msg=outcome1.get("error"))
            self.assertEqual(admission_spy.call_count, 1)

            second_server = _make_server()
            second_port = second_server.bind()
            thread2, outcome2 = _run_server(second_server)
            client2 = GuestAgentSignedDispatchRpcClient(
                build_host_client_tls_context(host_config), host_config, second_port
            )
            response2 = client2.send_signed_dispatch(envelope)
            thread2.join(timeout=5.0)
            self.assertNotIn("error", outcome2, msg=outcome2.get("error"))
            self.assertEqual(response2.status, GuestAgentResponseStatus.REPLAY_REJECTED)
            # The replay never added a second call: admission ran exactly
            # once, for the first-seen dispatch only, and the DNS executor
            # itself ran at most once overall -- never retried for the
            # replay.
            self.assertEqual(admission_spy.call_count, 1)
            run.assert_called_once()

    def test_readiness_unavailable_never_reaches_execution_admission(self) -> None:
        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        envelope = _real_envelope(signing_key)
        probe = _RecordingLocalReadinessProbe(
            _unavailable_receipt_for(envelope.request.operation_kind)
        )
        server = GuestAgentSignedDispatchRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            verification_key=signing_key.public_key(),
            replay_protector=GuestAgentReplayProtector(_FakeReplayStore()),
            clock=lambda: NOW,
            local_runtime_probe=probe,
        )
        port = server.bind()
        with mock.patch.object(
            transport_module,
            "admit_guest_agent_execution",
            wraps=admit_guest_agent_execution,
        ) as admission_spy:
            thread, outcome = _run_server(server)
            client = GuestAgentSignedDispatchRpcClient(
                build_host_client_tls_context(host_config), host_config, port
            )
            response = client.send_signed_dispatch(envelope)
            thread.join(timeout=5.0)
        self.assertNotIn("error", outcome, msg=outcome.get("error"))
        self.assertEqual(response.status, GuestAgentResponseStatus.DECLINED)
        admission_spy.assert_not_called()

    def test_ready_first_seen_dns_request_reaches_admission_exactly_once(
        self,
    ) -> None:
        """v0.3.470 note: this exact scenario (readiness READY, admission
        succeeds, DNS operation) now reaches real execution and returns
        SUCCESS instead of the pre-v0.3.470 DECLINED -- `subprocess.run` is
        mocked deterministically, never a real DNS query. The admission
        plumbing proof below (exactly one call, correct arguments, a
        genuine non-stub admission) is unchanged from v0.3.468."""
        import subprocess as subprocess_module

        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        envelope = _real_envelope(signing_key, preview=_preview())
        probe = _RecordingLocalReadinessProbe(
            _ready_receipt_for(envelope.request.operation_kind)
        )
        server = GuestAgentSignedDispatchRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            verification_key=signing_key.public_key(),
            replay_protector=GuestAgentReplayProtector(_FakeReplayStore()),
            clock=lambda: NOW,
            local_runtime_probe=probe,
        )
        port = server.bind()
        with (
            mock.patch.object(
                transport_module,
                "admit_guest_agent_execution",
                wraps=admit_guest_agent_execution,
            ) as admission_spy,
            mock.patch.object(
                subprocess_module,
                "run",
                return_value=subprocess_module.CompletedProcess(
                    args=(), returncode=0, stdout="1.2.3.4\n", stderr=""
                ),
            ),
        ):
            thread, outcome = _run_server(server)
            client = GuestAgentSignedDispatchRpcClient(
                build_host_client_tls_context(host_config), host_config, port
            )
            response = client.send_signed_dispatch(envelope)
            thread.join(timeout=5.0)
        self.assertNotIn("error", outcome, msg=outcome.get("error"))
        self.assertEqual(response.status, GuestAgentResponseStatus.SUCCESS)
        self.assertEqual(response.output_lines, ("1.2.3.4",))
        admission_spy.assert_called_once()
        verified_arg, ready_arg = admission_spy.call_args[0]
        self.assertEqual(verified_arg.request.request_id, envelope.request.request_id)
        self.assertIs(
            ready_arg.prepared_invocation.operation_kind,
            envelope.request.operation_kind,
        )
        # `wraps=admit_guest_agent_execution` means the spy still calls the
        # real function and returns its real result -- proving this is a
        # genuine admission, not a stub -- confirmed directly against the
        # real function with the exact same arguments the server passed.
        real_result = admit_guest_agent_execution(verified_arg, ready_arg)
        self.assertIsInstance(real_result, GuestAgentExecutionBoundaryReceipt)

    def test_ready_https_request_also_reaches_admission_still_declined(self) -> None:
        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        envelope = _real_envelope(signing_key, preview=_https_preview())
        probe = _RecordingLocalReadinessProbe(
            _ready_receipt_for(envelope.request.operation_kind)
        )
        server = GuestAgentSignedDispatchRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            verification_key=signing_key.public_key(),
            replay_protector=GuestAgentReplayProtector(_FakeReplayStore()),
            clock=lambda: NOW,
            local_runtime_probe=probe,
        )
        port = server.bind()
        with mock.patch.object(
            transport_module,
            "admit_guest_agent_execution",
            wraps=admit_guest_agent_execution,
        ) as admission_spy:
            thread, outcome = _run_server(server)
            client = GuestAgentSignedDispatchRpcClient(
                build_host_client_tls_context(host_config), host_config, port
            )
            response = client.send_signed_dispatch(envelope)
            thread.join(timeout=5.0)
        self.assertNotIn("error", outcome, msg=outcome.get("error"))
        self.assertEqual(response.status, GuestAgentResponseStatus.DECLINED)
        admission_spy.assert_called_once()

    def test_default_server_never_calls_admission_without_custom_probe(
        self,
    ) -> None:
        """A server constructed without `local_runtime_probe` (the default
        `UnavailableGuestAgentLocalReadinessProbe`, fails closed) must
        never reach execution admission at all."""
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
        with mock.patch.object(
            transport_module,
            "admit_guest_agent_execution",
            wraps=admit_guest_agent_execution,
        ) as admission_spy:
            thread, outcome = _run_server(server)
            client = GuestAgentSignedDispatchRpcClient(
                build_host_client_tls_context(host_config), host_config, port
            )
            response = client.send_signed_dispatch(envelope)
            thread.join(timeout=5.0)
        self.assertNotIn("error", outcome, msg=outcome.get("error"))
        self.assertEqual(response.status, GuestAgentResponseStatus.DECLINED)
        admission_spy.assert_not_called()


def _completed(*, returncode: int = 0, stdout: str = "", stderr: str = ""):
    import subprocess as subprocess_module

    return subprocess_module.CompletedProcess(
        args=(), returncode=returncode, stdout=stdout, stderr=stderr
    )


class DnsRpcExecutionTests(_LoopbackMtlsFixture):
    """v0.3.470: the first executable signed-dispatch RPC path, for
    `DNS_RECORD_LOOKUP` only.

    EXECUTION ADMISSION != EXECUTION SUCCESS. Every positive test proves a
    real local `dig` process (mocked deterministically -- never a real DNS
    query) is reached exactly once, with the exact admitted argv and
    timeout, strictly after the full existing authority chain succeeds.
    Every negative/adversarial test proves the executor is unreachable
    (zero calls) for any gate failure, and that `FAILED`/`DECLINED` never
    leak raw stderr or exception text onto the wire.
    """

    def test_valid_first_seen_dns_request_reaches_executor_exactly_once(
        self,
    ) -> None:
        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        envelope = _real_envelope(signing_key, preview=_preview())
        probe = _RecordingLocalReadinessProbe(
            _ready_receipt_for(envelope.request.operation_kind)
        )
        server = GuestAgentSignedDispatchRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            verification_key=signing_key.public_key(),
            replay_protector=GuestAgentReplayProtector(_FakeReplayStore()),
            clock=lambda: NOW,
            local_runtime_probe=probe,
        )
        port = server.bind()
        with (
            mock.patch.object(
                transport_module,
                "execute_guest_agent_dns_record_lookup",
                wraps=execute_guest_agent_dns_record_lookup,
            ) as executor_spy,
            mock.patch("subprocess.run") as run,
        ):
            run.return_value = _completed(stdout="1.2.3.4\n")
            thread, outcome = _run_server(server)
            client = GuestAgentSignedDispatchRpcClient(
                build_host_client_tls_context(host_config), host_config, port
            )
            response = client.send_signed_dispatch(envelope)
            thread.join(timeout=5.0)
        self.assertNotIn("error", outcome, msg=outcome.get("error"))
        executor_spy.assert_called_once()
        (admission_arg,) = executor_spy.call_args[0]
        self.assertIs(
            admission_arg.runtime_ready_invocation.prepared_invocation.operation_kind,
            ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
        )
        self.assertEqual(response.status, GuestAgentResponseStatus.SUCCESS)

    def test_exit_zero_is_success(self) -> None:
        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        envelope = _real_envelope(signing_key, preview=_preview())
        probe = _RecordingLocalReadinessProbe(
            _ready_receipt_for(envelope.request.operation_kind)
        )
        server = GuestAgentSignedDispatchRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            verification_key=signing_key.public_key(),
            replay_protector=GuestAgentReplayProtector(_FakeReplayStore()),
            clock=lambda: NOW,
            local_runtime_probe=probe,
        )
        port = server.bind()
        with mock.patch(
            "subprocess.run", return_value=_completed(stdout="93.184.216.34\n")
        ):
            thread, outcome = _run_server(server)
            client = GuestAgentSignedDispatchRpcClient(
                build_host_client_tls_context(host_config), host_config, port
            )
            response = client.send_signed_dispatch(envelope)
            thread.join(timeout=5.0)
        self.assertNotIn("error", outcome, msg=outcome.get("error"))
        self.assertEqual(response.status, GuestAgentResponseStatus.SUCCESS)
        self.assertEqual(response.output_lines, ("93.184.216.34",))
        self.assertEqual(response.output_trust, KALI_OPERATION_OUTPUT_TRUST)

    def test_empty_stdout_exit_zero_is_success_with_empty_output(self) -> None:
        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        envelope = _real_envelope(signing_key, preview=_preview())
        probe = _RecordingLocalReadinessProbe(
            _ready_receipt_for(envelope.request.operation_kind)
        )
        server = GuestAgentSignedDispatchRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            verification_key=signing_key.public_key(),
            replay_protector=GuestAgentReplayProtector(_FakeReplayStore()),
            clock=lambda: NOW,
            local_runtime_probe=probe,
        )
        port = server.bind()
        with mock.patch("subprocess.run", return_value=_completed(stdout="")):
            thread, outcome = _run_server(server)
            client = GuestAgentSignedDispatchRpcClient(
                build_host_client_tls_context(host_config), host_config, port
            )
            response = client.send_signed_dispatch(envelope)
            thread.join(timeout=5.0)
        self.assertNotIn("error", outcome, msg=outcome.get("error"))
        self.assertEqual(response.status, GuestAgentResponseStatus.SUCCESS)
        self.assertEqual(response.output_lines, ())

    def test_nonzero_exit_is_failed(self) -> None:
        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        envelope = _real_envelope(signing_key, preview=_preview())
        probe = _RecordingLocalReadinessProbe(
            _ready_receipt_for(envelope.request.operation_kind)
        )
        server = GuestAgentSignedDispatchRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            verification_key=signing_key.public_key(),
            replay_protector=GuestAgentReplayProtector(_FakeReplayStore()),
            clock=lambda: NOW,
            local_runtime_probe=probe,
        )
        port = server.bind()
        with mock.patch(
            "subprocess.run",
            return_value=_completed(
                returncode=1, stderr="top secret internal failure detail"
            ),
        ):
            thread, outcome = _run_server(server)
            client = GuestAgentSignedDispatchRpcClient(
                build_host_client_tls_context(host_config), host_config, port
            )
            response = client.send_signed_dispatch(envelope)
            thread.join(timeout=5.0)
        self.assertNotIn("error", outcome, msg=outcome.get("error"))
        self.assertEqual(response.status, GuestAgentResponseStatus.FAILED)
        self.assertEqual(response.output_lines, ())
        self.assertNotIn("top secret internal failure detail", response.detail)

    def test_timeout_is_failed(self) -> None:
        import subprocess as subprocess_module

        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        envelope = _real_envelope(signing_key, preview=_preview())
        probe = _RecordingLocalReadinessProbe(
            _ready_receipt_for(envelope.request.operation_kind)
        )
        server = GuestAgentSignedDispatchRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            verification_key=signing_key.public_key(),
            replay_protector=GuestAgentReplayProtector(_FakeReplayStore()),
            clock=lambda: NOW,
            local_runtime_probe=probe,
        )
        port = server.bind()
        with mock.patch(
            "subprocess.run",
            side_effect=subprocess_module.TimeoutExpired(cmd="dig", timeout=5.0),
        ):
            thread, outcome = _run_server(server)
            client = GuestAgentSignedDispatchRpcClient(
                build_host_client_tls_context(host_config), host_config, port
            )
            response = client.send_signed_dispatch(envelope)
            thread.join(timeout=5.0)
        self.assertNotIn("error", outcome, msg=outcome.get("error"))
        self.assertEqual(response.status, GuestAgentResponseStatus.FAILED)
        self.assertEqual(response.output_lines, ())

    def test_oserror_is_failed_without_leaking_exception_text(self) -> None:
        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        envelope = _real_envelope(signing_key, preview=_preview())
        probe = _RecordingLocalReadinessProbe(
            _ready_receipt_for(envelope.request.operation_kind)
        )
        server = GuestAgentSignedDispatchRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            verification_key=signing_key.public_key(),
            replay_protector=GuestAgentReplayProtector(_FakeReplayStore()),
            clock=lambda: NOW,
            local_runtime_probe=probe,
        )
        port = server.bind()
        with mock.patch(
            "subprocess.run",
            side_effect=FileNotFoundError("/some/secret/internal/path"),
        ):
            thread, outcome = _run_server(server)
            client = GuestAgentSignedDispatchRpcClient(
                build_host_client_tls_context(host_config), host_config, port
            )
            response = client.send_signed_dispatch(envelope)
            thread.join(timeout=5.0)
        self.assertNotIn("error", outcome, msg=outcome.get("error"))
        self.assertEqual(response.status, GuestAgentResponseStatus.FAILED)
        self.assertEqual(response.output_lines, ())
        self.assertNotIn("/some/secret/internal/path", response.detail)

    def test_stderr_never_appears_on_wire_on_success(self) -> None:
        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        envelope = _real_envelope(signing_key, preview=_preview())
        probe = _RecordingLocalReadinessProbe(
            _ready_receipt_for(envelope.request.operation_kind)
        )
        server = GuestAgentSignedDispatchRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            verification_key=signing_key.public_key(),
            replay_protector=GuestAgentReplayProtector(_FakeReplayStore()),
            clock=lambda: NOW,
            local_runtime_probe=probe,
        )
        port = server.bind()
        with mock.patch(
            "subprocess.run",
            return_value=_completed(
                stdout="1.2.3.4\n", stderr="stderr leak canary text"
            ),
        ):
            thread, outcome = _run_server(server)
            client = GuestAgentSignedDispatchRpcClient(
                build_host_client_tls_context(host_config), host_config, port
            )
            response = client.send_signed_dispatch(envelope)
            thread.join(timeout=5.0)
        self.assertNotIn("error", outcome, msg=outcome.get("error"))
        self.assertEqual(response.status, GuestAgentResponseStatus.SUCCESS)
        self.assertNotIn("stderr leak canary text", response.output_lines)
        self.assertNotIn("stderr leak canary text", response.detail)

    def test_https_request_never_reaches_executor_and_stays_declined(self) -> None:
        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        envelope = _real_envelope(signing_key, preview=_https_preview())
        probe = _RecordingLocalReadinessProbe(
            _ready_receipt_for(envelope.request.operation_kind)
        )
        server = GuestAgentSignedDispatchRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            verification_key=signing_key.public_key(),
            replay_protector=GuestAgentReplayProtector(_FakeReplayStore()),
            clock=lambda: NOW,
            local_runtime_probe=probe,
        )
        port = server.bind()
        with (
            mock.patch.object(
                transport_module,
                "execute_guest_agent_dns_record_lookup",
                wraps=execute_guest_agent_dns_record_lookup,
            ) as executor_spy,
            mock.patch("subprocess.run") as run,
        ):
            thread, outcome = _run_server(server)
            client = GuestAgentSignedDispatchRpcClient(
                build_host_client_tls_context(host_config), host_config, port
            )
            response = client.send_signed_dispatch(envelope)
            thread.join(timeout=5.0)
        self.assertNotIn("error", outcome, msg=outcome.get("error"))
        self.assertEqual(response.status, GuestAgentResponseStatus.DECLINED)
        executor_spy.assert_not_called()
        run.assert_not_called()

    def test_v1_request_never_reaches_executor(self) -> None:
        from research.GuestAgentProtocol import GuestAgentRequest

        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        v1_request = GuestAgentRequest(
            protocol_version=GuestAgentProtocolVersion.V1,
            request_id="v1-executor",
            nonce="v1-executor-nonce",
            operation_kind=_preview().operation_kind,
            operation_digest="a" * 64,
            logical_inputs=(("hostname", "example.com"), ("dns_record_type", "A")),
        )
        envelope = _sign_arbitrary_request_for_test(
            v1_request, signing_key=signing_key, now=NOW
        )
        probe = _RecordingLocalReadinessProbe(
            _ready_receipt_for(v1_request.operation_kind)
        )
        server = GuestAgentSignedDispatchRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            verification_key=signing_key.public_key(),
            replay_protector=GuestAgentReplayProtector(_FakeReplayStore()),
            clock=lambda: NOW,
            local_runtime_probe=probe,
        )
        port = server.bind()
        with (
            mock.patch.object(
                transport_module,
                "execute_guest_agent_dns_record_lookup",
                wraps=execute_guest_agent_dns_record_lookup,
            ) as executor_spy,
            mock.patch("subprocess.run") as run,
        ):
            thread, outcome = _run_server(server)
            client = GuestAgentSignedDispatchRpcClient(
                build_host_client_tls_context(host_config), host_config, port
            )
            response = client.send_signed_dispatch(envelope)
            thread.join(timeout=5.0)
        self.assertNotIn("error", outcome, msg=outcome.get("error"))
        self.assertEqual(response.status, GuestAgentResponseStatus.DECLINED)
        executor_spy.assert_not_called()
        run.assert_not_called()

    def test_readiness_unavailable_never_reaches_executor(self) -> None:
        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        envelope = _real_envelope(signing_key, preview=_preview())
        probe = _RecordingLocalReadinessProbe(
            _unavailable_receipt_for(envelope.request.operation_kind)
        )
        server = GuestAgentSignedDispatchRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            verification_key=signing_key.public_key(),
            replay_protector=GuestAgentReplayProtector(_FakeReplayStore()),
            clock=lambda: NOW,
            local_runtime_probe=probe,
        )
        port = server.bind()
        with (
            mock.patch.object(
                transport_module,
                "execute_guest_agent_dns_record_lookup",
                wraps=execute_guest_agent_dns_record_lookup,
            ) as executor_spy,
            mock.patch("subprocess.run") as run,
        ):
            thread, outcome = _run_server(server)
            client = GuestAgentSignedDispatchRpcClient(
                build_host_client_tls_context(host_config), host_config, port
            )
            response = client.send_signed_dispatch(envelope)
            thread.join(timeout=5.0)
        self.assertNotIn("error", outcome, msg=outcome.get("error"))
        self.assertEqual(response.status, GuestAgentResponseStatus.DECLINED)
        executor_spy.assert_not_called()
        run.assert_not_called()

    def test_invalid_signature_never_reaches_executor(self) -> None:
        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        wrong_key = Ed25519PrivateKey.generate()
        envelope = _real_envelope(signing_key, preview=_preview())
        probe = _RecordingLocalReadinessProbe(
            _ready_receipt_for(envelope.request.operation_kind)
        )
        server = GuestAgentSignedDispatchRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            # A verification key that does NOT match the signing key --
            # the real Ed25519 signature check must fail.
            verification_key=wrong_key.public_key(),
            replay_protector=GuestAgentReplayProtector(_FakeReplayStore()),
            clock=lambda: NOW,
            local_runtime_probe=probe,
        )
        port = server.bind()
        with (
            mock.patch.object(
                transport_module,
                "execute_guest_agent_dns_record_lookup",
                wraps=execute_guest_agent_dns_record_lookup,
            ) as executor_spy,
            mock.patch("subprocess.run") as run,
        ):
            thread, outcome = _run_server(server)
            client = GuestAgentSignedDispatchRpcClient(
                build_host_client_tls_context(host_config), host_config, port
            )
            with self.assertRaises(GuestAgentSignedDispatchRpcTransportError):
                client.send_signed_dispatch(envelope)
            thread.join(timeout=5.0)
        executor_spy.assert_not_called()
        run.assert_not_called()

    def test_replayed_request_never_reaches_executor_twice(self) -> None:
        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        store = _FakeReplayStore()
        envelope = _real_envelope(signing_key, preview=_preview())
        probe = _RecordingLocalReadinessProbe(
            _ready_receipt_for(envelope.request.operation_kind)
        )

        def _make_server() -> GuestAgentSignedDispatchRpcServer:
            return GuestAgentSignedDispatchRpcServer(
                build_guest_server_tls_context(guest_config),
                guest_config,
                verification_key=signing_key.public_key(),
                replay_protector=GuestAgentReplayProtector(store),
                clock=lambda: NOW,
                local_runtime_probe=probe,
            )

        with (
            mock.patch.object(
                transport_module,
                "execute_guest_agent_dns_record_lookup",
                wraps=execute_guest_agent_dns_record_lookup,
            ) as executor_spy,
            mock.patch("subprocess.run", return_value=_completed(stdout="1.2.3.4\n")),
        ):
            first_server = _make_server()
            first_port = first_server.bind()
            thread1, outcome1 = _run_server(first_server)
            client1 = GuestAgentSignedDispatchRpcClient(
                build_host_client_tls_context(host_config), host_config, first_port
            )
            response1 = client1.send_signed_dispatch(envelope)
            thread1.join(timeout=5.0)
            self.assertNotIn("error", outcome1, msg=outcome1.get("error"))
            self.assertEqual(response1.status, GuestAgentResponseStatus.SUCCESS)
            self.assertEqual(executor_spy.call_count, 1)

            second_server = _make_server()
            second_port = second_server.bind()
            thread2, outcome2 = _run_server(second_server)
            client2 = GuestAgentSignedDispatchRpcClient(
                build_host_client_tls_context(host_config), host_config, second_port
            )
            response2 = client2.send_signed_dispatch(envelope)
            thread2.join(timeout=5.0)
            self.assertNotIn("error", outcome2, msg=outcome2.get("error"))
            self.assertEqual(response2.status, GuestAgentResponseStatus.REPLAY_REJECTED)
            self.assertEqual(executor_spy.call_count, 1)

    def test_exact_argv_and_timeout_passed_to_subprocess(self) -> None:
        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        envelope = _real_envelope(
            signing_key, preview=_preview(hostname="example.com", max_seconds=7.0)
        )
        probe = _RecordingLocalReadinessProbe(
            _ready_receipt_for(envelope.request.operation_kind)
        )
        server = GuestAgentSignedDispatchRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            verification_key=signing_key.public_key(),
            replay_protector=GuestAgentReplayProtector(_FakeReplayStore()),
            clock=lambda: NOW,
            local_runtime_probe=probe,
        )
        port = server.bind()
        with mock.patch(
            "subprocess.run", return_value=_completed(stdout="1.2.3.4\n")
        ) as run:
            thread, outcome = _run_server(server)
            client = GuestAgentSignedDispatchRpcClient(
                build_host_client_tls_context(host_config), host_config, port
            )
            client.send_signed_dispatch(envelope)
            thread.join(timeout=5.0)
        self.assertNotIn("error", outcome, msg=outcome.get("error"))
        run.assert_called_once()
        argv = run.call_args[0][0]
        self.assertEqual(
            argv, ("/usr/bin/dig", "+time=5", "+tries=1", "+short", "example.com", "A")
        )
        self.assertEqual(run.call_args.kwargs["timeout"], 7.0)

    def test_response_write_failure_does_not_cause_second_executor_call(self) -> None:
        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        envelope = _real_envelope(signing_key, preview=_preview())
        probe = _RecordingLocalReadinessProbe(
            _ready_receipt_for(envelope.request.operation_kind)
        )
        server = GuestAgentSignedDispatchRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            verification_key=signing_key.public_key(),
            replay_protector=GuestAgentReplayProtector(_FakeReplayStore()),
            clock=lambda: NOW,
            local_runtime_probe=probe,
        )
        port = server.bind()

        # Both the CLIENT (writing the outgoing request) and the SERVER
        # (writing its response) call this same imported name. The first
        # call must genuinely write real bytes to the real socket (or the
        # server's own frame read would simply time out waiting for data
        # that was never sent) -- only the SECOND call (the server's
        # response write, reached only after the executor already ran)
        # is forced to fail.
        real_write = transport_module.write_guest_agent_rpc_frame
        write_call_count = {"n": 0}
        write_lock = threading.Lock()

        def _write_side_effect(sock, payload):
            with write_lock:
                write_call_count["n"] += 1
                call_number = write_call_count["n"]
            if call_number == 1:
                return real_write(sock, payload)
            raise OSError("forced response-write failure for test")

        with (
            mock.patch.object(
                transport_module,
                "execute_guest_agent_dns_record_lookup",
                wraps=execute_guest_agent_dns_record_lookup,
            ) as executor_spy,
            mock.patch("subprocess.run", return_value=_completed(stdout="1.2.3.4\n")),
            mock.patch.object(
                transport_module,
                "write_guest_agent_rpc_frame",
                side_effect=_write_side_effect,
            ),
        ):
            thread, outcome = _run_server(server)
            client = GuestAgentSignedDispatchRpcClient(
                build_host_client_tls_context(host_config), host_config, port
            )
            with self.assertRaises(GuestAgentSignedDispatchRpcTransportError):
                client.send_signed_dispatch(envelope)
            thread.join(timeout=5.0)
        # The executor still ran exactly once (the operation may already
        # have occurred); the server never retries it merely because the
        # response write itself then failed.
        executor_spy.assert_called_once()
        self.assertIn("error", outcome)

    def test_default_server_never_reaches_executor(self) -> None:
        """Default construction (no `local_runtime_probe`) must remain
        non-executing: zero DNS target execution with no caller-supplied
        probe."""
        host_config = self.host_config()
        guest_config = self.guest_config()
        signing_key = Ed25519PrivateKey.generate()
        envelope = _real_envelope(signing_key, preview=_preview())
        server = GuestAgentSignedDispatchRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            verification_key=signing_key.public_key(),
            replay_protector=GuestAgentReplayProtector(_FakeReplayStore()),
            clock=lambda: NOW,
        )
        port = server.bind()
        with (
            mock.patch.object(
                transport_module,
                "execute_guest_agent_dns_record_lookup",
                wraps=execute_guest_agent_dns_record_lookup,
            ) as executor_spy,
            mock.patch("subprocess.run") as run,
        ):
            thread, outcome = _run_server(server)
            client = GuestAgentSignedDispatchRpcClient(
                build_host_client_tls_context(host_config), host_config, port
            )
            response = client.send_signed_dispatch(envelope)
            thread.join(timeout=5.0)
        self.assertNotIn("error", outcome, msg=outcome.get("error"))
        self.assertEqual(response.status, GuestAgentResponseStatus.DECLINED)
        executor_spy.assert_not_called()
        run.assert_not_called()

    def test_max_bounded_success_response_fits_rpc_frame(self) -> None:
        detail = "x" * MAX_RESPONSE_DETAIL_LENGTH
        output_lines = tuple(
            ("y" * MAX_KALI_OPERATION_OUTPUT_LINE_CHARACTERS)
            for _ in range(MAX_KALI_OPERATION_OUTPUT_LINES)
        )
        response = GuestAgentResponse(
            protocol_version=GuestAgentProtocolVersion.V2,
            request_id="r" * 200,
            status=GuestAgentResponseStatus.SUCCESS,
            detail=detail,
            output_lines=output_lines,
        )
        data = canonical_guest_agent_response_bytes(response)
        self.assertLess(len(data), MAX_GUEST_AGENT_RPC_FRAME_SIZE)
        # Comfortable headroom, not a coincidental near-miss.
        self.assertLess(len(data), MAX_GUEST_AGENT_RPC_FRAME_SIZE - 100_000)


class DnsRpcStructuralSecurityTests(unittest.TestCase):
    """AST-level proof that the one real executor call is hardcoded,
    narrowly guarded, and that no generic executor/process/network
    channel was introduced anywhere in the RPC transport module."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.source = TRANSPORT_MODULE_FILE.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_exactly_one_execute_guest_agent_dns_record_lookup_call_site(self) -> None:
        calls = [
            node
            for node in ast.walk(self.tree)
            if isinstance(node, ast.Call)
            and (
                (
                    isinstance(node.func, ast.Name)
                    and node.func.id == "execute_guest_agent_dns_record_lookup"
                )
                or (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "execute_guest_agent_dns_record_lookup"
                )
            )
        ]
        self.assertEqual(len(calls), 1)

    def test_executor_call_is_guarded_by_dns_operation_kind_check(self) -> None:
        """The one executor call site is inside an `if ... is
        ResearchKaliOperationKind.DNS_RECORD_LOOKUP:` block -- a single
        explicit comparison, never built by enumerating the enum."""
        serve_def = None
        for node in ast.walk(self.tree):
            if (
                isinstance(node, ast.FunctionDef)
                and node.name == "serve_one_signed_dispatch"
            ):
                serve_def = node
                break
        self.assertIsNotNone(serve_def)
        candidate_ifs = [
            node
            for node in ast.walk(serve_def)  # type: ignore[arg-type]
            if isinstance(node, ast.If)
            and any(
                isinstance(inner, ast.Call)
                and (
                    (
                        isinstance(inner.func, ast.Name)
                        and inner.func.id == "execute_guest_agent_dns_record_lookup"
                    )
                    or (
                        isinstance(inner.func, ast.Attribute)
                        and inner.func.attr == "execute_guest_agent_dns_record_lookup"
                    )
                )
                for inner in ast.walk(node)
            )
        ]
        self.assertTrue(candidate_ifs)
        guarding_if = min(candidate_ifs, key=lambda node: len(list(ast.walk(node))))
        test_source = ast.unparse(guarding_if.test)
        self.assertIn("DNS_RECORD_LOOKUP", test_source)
        self.assertIn(" is ", test_source)

    def test_executor_call_is_guarded_by_boundary_receipt_none_check(self) -> None:
        serve_def = None
        for node in ast.walk(self.tree):
            if (
                isinstance(node, ast.FunctionDef)
                and node.name == "serve_one_signed_dispatch"
            ):
                serve_def = node
                break
        self.assertIsNotNone(serve_def)
        candidate_ifs = [
            node
            for node in ast.walk(serve_def)  # type: ignore[arg-type]
            if isinstance(node, ast.If)
            and any(
                isinstance(inner, ast.Call)
                and (
                    (
                        isinstance(inner.func, ast.Name)
                        and inner.func.id == "execute_guest_agent_dns_record_lookup"
                    )
                    or (
                        isinstance(inner.func, ast.Attribute)
                        and inner.func.attr == "execute_guest_agent_dns_record_lookup"
                    )
                )
                for inner in ast.walk(node)
            )
        ]
        self.assertTrue(candidate_ifs)
        matching_guards = [
            node
            for node in candidate_ifs
            if "_boundary_receipt" in ast.unparse(node.test)
        ]
        self.assertTrue(
            matching_guards,
            "no enclosing if-block test mentions _boundary_receipt",
        )
        test_source = ast.unparse(matching_guards[0].test)
        self.assertIn("is not None", test_source)

    def test_readiness_admission_executor_in_source_order(self) -> None:
        readiness_line = self._first_call_lineno("check_guest_agent_runtime_readiness")
        admission_line = self._first_call_lineno("admit_guest_agent_execution")
        executor_line = self._first_call_lineno("execute_guest_agent_dns_record_lookup")
        self.assertGreater(readiness_line, 0)
        self.assertGreater(admission_line, 0)
        self.assertGreater(executor_line, 0)
        self.assertLess(readiness_line, admission_line)
        self.assertLess(admission_line, executor_line)

    def _first_call_lineno(self, name_fragment: str) -> int:
        matches = []
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name) and func.id == name_fragment:
                matches.append(node.lineno)
            elif isinstance(func, ast.Attribute) and func.attr == name_fragment:
                matches.append(node.lineno)
        return min(matches) if matches else -1

    def test_no_generic_handler_or_executor_registry(self) -> None:
        forbidden_identifiers = {
            "handler",
            "executor_callback",
            "run_callback",
            "process_adapter",
            "executor_registry",
            "capability_dispatcher",
        }
        names = {
            node.id for node in ast.walk(self.tree) if isinstance(node, ast.Name)
        } | {node.arg for node in ast.walk(self.tree) if isinstance(node, ast.arg)}
        self.assertFalse(names & forbidden_identifiers, names & forbidden_identifiers)

    def test_no_curl_https_executor_or_dangerous_identifiers(self) -> None:
        forbidden_identifiers = {
            "curl",
            "ssh",
            "vmrun",
            "wsl",
            "eval",
            "exec",
            "GuestAgentCapabilityExecutor",
            "GuestAgentHttpsExecutor",
            "GuestAgentDnsExecutor",
            "ResearchDnsLookupResultParser",
        }
        names = {
            node.id for node in ast.walk(self.tree) if isinstance(node, ast.Name)
        } | {
            node.attr for node in ast.walk(self.tree) if isinstance(node, ast.Attribute)
        }
        self.assertFalse(names & forbidden_identifiers, names & forbidden_identifiers)

    def test_no_evidence_claim_memory_identifiers(self) -> None:
        forbidden_identifiers = {
            "ResearchEvidenceRecord",
            "create_claim",
            "accept_source",
            "write_memory",
            "SecurityFinding",
        }
        names = {
            node.id for node in ast.walk(self.tree) if isinstance(node, ast.Name)
        } | {
            node.attr for node in ast.walk(self.tree) if isinstance(node, ast.Attribute)
        }
        self.assertFalse(names & forbidden_identifiers, names & forbidden_identifiers)

    def test_no_dynamic_import_eval_exec_os_system_popen(self) -> None:
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in (
                    "eval",
                    "exec",
                    "__import__",
                ):
                    self.fail(f"forbidden call found: {node.func.id}")
                if isinstance(node.func, ast.Attribute) and node.func.attr in (
                    "system",
                    "Popen",
                ):
                    self.fail(f"forbidden call found: {node.func.attr}")

    def test_no_shell_true_anywhere(self) -> None:
        self.assertNotIn("shell=True", self.source)
        self.assertNotIn("shell = True", self.source)


class DnsRpcNoHiddenCallerTests(unittest.TestCase):
    """Repo-wide proof the new real executor has zero production callers
    beyond the one hardcoded RPC call site this milestone adds."""

    def test_no_bootstrap_cognitive_engine_chat_or_desktop_caller(self) -> None:
        src_dir = SRC_DIR
        forbidden_names = (
            "execute_guest_agent_dns_record_lookup",
            "GuestAgentDnsExecutionAdapter",
        )
        offending_files = []
        for path in src_dir.rglob("*.py"):
            if path.name in (
                "GuestAgentDnsExecutionAdapter.py",
                "GuestAgentSignedDispatchRpcTransport.py",
            ):
                continue
            text = path.read_text(encoding="utf-8")
            if any(name in text for name in forbidden_names):
                offending_files.append(str(path))
        self.assertEqual(offending_files, [])


if __name__ == "__main__":
    unittest.main()
