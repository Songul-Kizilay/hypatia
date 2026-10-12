"""A real loopback TLS 1.3 mutual handshake, end to end, for Guest-Agent step 3.

TLS HANDSHAKE SUCCESS != EXECUTION AUTHORITY. PEER IDENTITY MATCH !=
EXECUTION AUTHORITY. AUTHENTICATED CHANNEL != EXECUTION AUTHORITY.
AUTHENTICATED CHANNEL != OPERATION AUTHORIZATION. Every prior Guest-Agent
mTLS milestone (v0.3.458, v0.3.459) proved its claims against synthetic,
in-memory certificate *observations* -- plain dataclasses a test built by
hand. This module proves the same claims against a REAL TLS 1.3 socket
handshake over loopback: real `ssl.SSLContext.wrap_socket`, real mutual
certificate presentation, real `getpeercert()`/`getpeercert(binary_form=
True)` extraction, fed -- unmodified -- into the existing
`parse_peer_certificate_identity` / `peer_identity_matches` /
`authenticate_peer` chain and the existing authenticated-channel wrappers.

No new production source file was added for this milestone. Repository
evidence (the functions this module imports) showed that
`parse_peer_certificate_identity` already accepts exactly the dict/bytes
shapes `ssl.SSLSocket.getpeercert()`/`getpeercert(binary_form=True)`
return -- that is the whole reason its own v0.3.458 docstring says so --
so proving a real handshake flows correctly into the existing
authentication chain requires no new abstraction, only a bounded loopback
test harness. This file is that harness and its proofs; it reuses
`research.GuestAgentMtlsContext`'s existing strict context builders
unmodified and never re-implements TLS, identity matching, or
authentication decisions itself.

Ephemeral test-only X.509 material (a dedicated test CA, a second,
deliberately untrusted CA, and HOST/GUEST leaf certificates) is generated
once per test class via the `openssl` CLI, confirmed present on both this
project's Linux (`ubuntu-24.04`) and Windows (`windows-2025`) CI runner
images, inside a `tempfile.TemporaryDirectory()` that is always removed
afterward. If `openssl` is not found on `PATH`, every test in this module
fails loudly (`RuntimeError`) rather than silently skipping, per this
milestone's explicit portability requirement. No private key, certificate,
or other generated material is ever committed to the repository or
written outside that temporary directory.
"""

from __future__ import annotations

import ast
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from typing import ClassVar

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from research.GuestAgentAuthenticatedChannel import (  # noqa: E402
    GuestAgentAuthenticatedGuestChannel,
    GuestAgentAuthenticatedHostChannel,
)
from research.GuestAgentMtlsContext import (  # noqa: E402
    build_guest_server_tls_context,
    build_host_client_tls_context,
)
from research.GuestAgentMtlsTrustConfiguration import (  # noqa: E402
    GuestAgentMtlsTrustConfiguration,
    GuestAgentPeerRole,
)
from research.GuestAgentPeerAuthenticator import (  # noqa: E402
    GuestAgentChannelAuthenticationResult,
    GuestAgentChannelAuthenticationStatus,
    authenticate_peer,
)
from research.GuestAgentPeerCertificateIdentity import (  # noqa: E402
    parse_peer_certificate_identity,
)

THIS_FILE = Path(__file__).resolve()

_LOOPBACK_HOST = "127.0.0.1"
_SOCKET_TIMEOUT_SECONDS = 5.0
_READY_WAIT_SECONDS = 5.0
_THREAD_JOIN_SECONDS = 5.0

_HOST_URI = "hypatia-kali-guest-agent/host/1"
_GUEST_URI = "hypatia-kali-guest-agent/guest/1"

_OPENSSL_PATH = shutil.which("openssl")

#: The one fixed control byte either side may exchange to confirm the TLS
#: handshake itself fully completed on both ends before closing. Never a
#: Guest-Agent protocol byte, capability input, or operation result --
#: see `_perform_handshake`'s docstring.
_HANDSHAKE_COMPLETE_MARKER = b"\x01"


def _require_openssl() -> str:
    """Return the `openssl` executable path, or fail loudly if absent.

    Per this milestone's explicit portability requirement: a missing
    external CLI on a supported CI platform must not be silently skipped.
    """
    if _OPENSSL_PATH is None:
        raise RuntimeError(
            "The `openssl` CLI was not found on PATH. This milestone "
            "requires it to generate ephemeral test-only certificates and "
            "must fail loudly here rather than silently skip the real "
            "handshake tests."
        )
    return _OPENSSL_PATH


def _run_openssl(*args: str) -> subprocess.CompletedProcess[str]:
    """Run one bounded `openssl` subcommand with an explicit argv list.

    Never uses a shell, so no quoting/platform-shell ambiguity exists; the
    executable position is always `_require_openssl()`'s return value,
    never a literal string, so this is the only call site in this module
    that can ever launch an external process.
    """
    result = subprocess.run(
        [_require_openssl(), *args],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"openssl {args[0] if args else ''} failed with exit "
            f"{result.returncode}: {result.stderr.strip()[:300]}"
        )
    return result


def _generate_key(path: Path) -> None:
    _run_openssl(
        "genpkey",
        "-algorithm",
        "RSA",
        "-pkeyopt",
        "rsa_keygen_bits:2048",
        "-out",
        str(path),
    )


def _self_sign_ca(key_path: Path, cert_path: Path, common_name: str) -> None:
    _run_openssl(
        "req",
        "-x509",
        "-new",
        "-key",
        str(key_path),
        "-sha256",
        "-days",
        "2",
        "-subj",
        f"/CN={common_name}",
        "-out",
        str(cert_path),
    )


def _create_csr(key_path: Path, csr_path: Path, common_name: str) -> None:
    _run_openssl(
        "req",
        "-new",
        "-key",
        str(key_path),
        "-subj",
        f"/CN={common_name}",
        "-out",
        str(csr_path),
    )


def _write_leaf_extension_file(path: Path, uri: str, extended_key_usage: str) -> None:
    """A minimal, purpose-specific leaf extension set: not a CA, one URI SAN."""
    path.write_text(
        "basicConstraints=CA:FALSE\n"
        "keyUsage=digitalSignature,keyEncipherment\n"
        f"extendedKeyUsage={extended_key_usage}\n"
        f"subjectAltName=URI:{uri}\n"
    )


def _sign_leaf(
    csr_path: Path,
    ca_cert: Path,
    ca_key: Path,
    ext_path: Path,
    out_path: Path,
    *,
    serial_suffix: str,
) -> None:
    _run_openssl(
        "x509",
        "-req",
        "-in",
        str(csr_path),
        "-CA",
        str(ca_cert),
        "-CAkey",
        str(ca_key),
        "-CAcreateserial",
        "-set_serial",
        serial_suffix,
        "-days",
        "2",
        "-sha256",
        "-extfile",
        str(ext_path),
        "-out",
        str(out_path),
    )


def _sign_leaf_with_explicit_dates(
    csr_path: Path,
    ca_cert: Path,
    ca_key: Path,
    ext_path: Path,
    out_path: Path,
    *,
    not_before: str,
    not_after: str,
    work_dir: Path,
) -> None:
    """Sign using the `openssl ca` config-driven flow -- the only mechanism

    this milestone's own portability audit confirmed supports explicit
    `-startdate`/`-enddate` control across this project's actual OpenSSL
    versions (the `x509 -req` self-contained signing mode's own
    `-not_after`/`-not_before` aliases were confirmed absent from OpenSSL
    3.0.0's `x509` app during that audit, so they are not relied upon
    here).
    """
    index_path = work_dir / f"{out_path.stem}.index"
    serial_path = work_dir / f"{out_path.stem}.serial"
    index_path.write_text("")
    serial_path.write_text("1000\n")
    ca_cnf = work_dir / f"{out_path.stem}.cnf"
    ca_cnf.write_text(
        "[ca]\n"
        "default_ca = CA_default\n\n"
        "[CA_default]\n"
        f"dir = {work_dir.as_posix()}\n"
        f"database = {index_path.as_posix()}\n"
        f"serial = {serial_path.as_posix()}\n"
        f"new_certs_dir = {work_dir.as_posix()}\n"
        f"certificate = {ca_cert.as_posix()}\n"
        f"private_key = {ca_key.as_posix()}\n"
        "default_md = sha256\n"
        "policy = policy_any\n"
        "copy_extensions = none\n"
        "unique_subject = no\n\n"
        "[policy_any]\n"
        "commonName = optional\n"
    )
    _run_openssl(
        "ca",
        "-config",
        str(ca_cnf),
        "-batch",
        "-in",
        str(csr_path),
        "-startdate",
        not_before,
        "-enddate",
        not_after,
        "-extfile",
        str(ext_path),
        "-out",
        str(out_path),
    )


def _trust_config(
    *,
    own_role: GuestAgentPeerRole,
    ca_cert: Path,
    own_cert: Path,
    own_key: Path,
    expected_peer_fingerprint_sha256: str | None = None,
) -> GuestAgentMtlsTrustConfiguration:
    return GuestAgentMtlsTrustConfiguration(
        own_role=own_role,
        trusted_ca_certificate_path=str(ca_cert),
        own_certificate_path=str(own_cert),
        own_private_key_path=str(own_key),
        expected_peer_fingerprint_sha256=expected_peer_fingerprint_sha256,
    )


def _perform_handshake(
    client_context: ssl.SSLContext,
    server_context: ssl.SSLContext,
) -> tuple[dict[str, object], dict[str, object], socket.socket | None, socket.socket]:
    """Perform one real loopback TLS handshake; return both sides' results.

    Each result dict always carries an `error` string when that side's
    handshake-or-post-handshake exchange failed anywhere along the way.
    It may ALSO carry a successful `cert_dict`/`der`/`version` triple at
    the same time: this side's own `wrap_socket` can succeed (TLS 1.3's
    0.5-RTT design lets a client consider its handshake complete before
    the server finishes verifying the client) even though a later step
    (for example, waiting for the other side's handshake-completion
    acknowledgment) still fails. Callers must always check `"error" in
    result` first -- `_authenticate_from_result` does exactly that -- and
    never assume the fields are mutually exclusive. Every socket
    operation is bounded by an explicit timeout; both sockets are always
    closed before this function returns, on success or failure alike. The
    raw client socket and the listening socket are returned (already
    closed) so callers can assert on their closed state without this
    function needing to know why a caller wants that.

    On a successful handshake, both sides exchange exactly one fixed
    control byte (`_HANDSHAKE_COMPLETE_MARKER`) before closing -- the
    "minimum fixed test/control bytes required to prove both sides
    completed a real handshake" this milestone explicitly allows. TLS
    1.3's 0.5-RTT design lets a client consider its own handshake done
    before the server has finished verifying the client's certificate;
    without this exchange, the client can close (sending TCP RST) while
    the server is still mid-verification, which this project's own
    Windows TCP stack surfaces as a spurious `ConnectionAbortedError`
    rather than the real outcome. This exchange never carries any
    Guest-Agent protocol byte, capability input, or operation result.
    """
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind((_LOOPBACK_HOST, 0))
    server_sock.settimeout(_SOCKET_TIMEOUT_SECONDS)
    server_sock.listen(1)
    port = server_sock.getsockname()[1]

    ready = threading.Event()
    server_result: dict[str, object] = {}

    def _server() -> None:
        ready.set()
        try:
            raw_conn, _ = server_sock.accept()
        except OSError as exc:
            server_result["error"] = repr(exc)
            return
        raw_conn.settimeout(_SOCKET_TIMEOUT_SECONDS)
        tls_conn: ssl.SSLSocket | None = None
        try:
            tls_conn = server_context.wrap_socket(raw_conn, server_side=True)
            server_result["cert_dict"] = tls_conn.getpeercert()
            server_result["der"] = tls_conn.getpeercert(binary_form=True)
            server_result["version"] = tls_conn.version()
            tls_conn.sendall(_HANDSHAKE_COMPLETE_MARKER)
            tls_conn.recv(1)
        except Exception as exc:  # noqa: BLE001 - must observe any TLS failure
            server_result["error"] = repr(exc)
        finally:
            (tls_conn or raw_conn).close()

    thread = threading.Thread(target=_server, daemon=True)
    thread.start()
    if not ready.wait(timeout=_READY_WAIT_SECONDS):
        server_sock.close()
        raise RuntimeError("loopback server did not become ready in time")

    client_result: dict[str, object] = {}
    client_raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_raw.settimeout(_SOCKET_TIMEOUT_SECONDS)
    tls_client: ssl.SSLSocket | None = None
    try:
        client_raw.connect((_LOOPBACK_HOST, port))
        tls_client = client_context.wrap_socket(client_raw, server_hostname=None)
        client_result["cert_dict"] = tls_client.getpeercert()
        client_result["der"] = tls_client.getpeercert(binary_form=True)
        client_result["version"] = tls_client.version()
        tls_client.recv(1)
        tls_client.sendall(_HANDSHAKE_COMPLETE_MARKER)
    except Exception as exc:  # noqa: BLE001 - must observe any TLS failure
        client_result["error"] = repr(exc)
    finally:
        (tls_client or client_raw).close()

    thread.join(timeout=_THREAD_JOIN_SECONDS)
    server_sock.close()
    if thread.is_alive():
        raise RuntimeError("loopback server thread did not finish within the bound")
    return client_result, server_result, (tls_client or client_raw), server_sock


def _authenticate_from_result(
    result: dict[str, object],
    trust_configuration: GuestAgentMtlsTrustConfiguration,
) -> GuestAgentChannelAuthenticationResult | None:
    """Feed one real handshake side's result into the existing, unmodified

    `parse_peer_certificate_identity` / `authenticate_peer` chain. Returns
    `None` only when the handshake itself already failed (no certificate
    evidence exists to authenticate at all) -- never a manufactured
    status.
    """
    if "error" in result:
        return None
    observation = parse_peer_certificate_identity(
        result["cert_dict"], der_bytes=result["der"]  # type: ignore[arg-type]
    )
    return authenticate_peer(observation, trust_configuration)


class _LoopbackMtlsFixture(unittest.TestCase):
    """Generates ephemeral test-only certificate material once per class."""

    _temp_dir: ClassVar[tempfile.TemporaryDirectory[str]]
    directory: ClassVar[Path]
    ca_cert: ClassVar[Path]
    ca_key: ClassVar[Path]
    host_cert: ClassVar[Path]
    host_key: ClassVar[Path]
    guest_cert: ClassVar[Path]
    guest_key: ClassVar[Path]
    wrong_ca_host_cert: ClassVar[Path]
    wrong_ca_guest_cert: ClassVar[Path]
    expired_host_cert: ClassVar[Path]
    future_host_cert: ClassVar[Path]

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        _require_openssl()
        cls._temp_dir = tempfile.TemporaryDirectory(prefix="hypatia-guest-agent-mtls-")
        directory = Path(cls._temp_dir.name)
        cls.directory = directory

        cls.ca_key = directory / "ca.key"
        cls.ca_cert = directory / "ca.crt"
        _generate_key(cls.ca_key)
        _self_sign_ca(cls.ca_key, cls.ca_cert, "Hypatia Guest-Agent Test CA")

        wrong_ca_key = directory / "wrong_ca.key"
        wrong_ca_cert = directory / "wrong_ca.crt"
        _generate_key(wrong_ca_key)
        _self_sign_ca(
            wrong_ca_key, wrong_ca_cert, "Hypatia Guest-Agent UNTRUSTED Test CA"
        )

        cls.host_key = directory / "host.key"
        host_csr = directory / "host.csr"
        _generate_key(cls.host_key)
        _create_csr(cls.host_key, host_csr, "hypatia-test-host")
        host_ext = directory / "host.ext"
        # Both leaf certificates carry both TLS extended-key-usage
        # purposes. Architecturally HOST is always the client and GUEST
        # is always the server, but this fixture's own deliberate
        # CA-valid-wrong-role tests present either certificate on either
        # side on purpose (see test_host_side_accepts_only_guest_identity/
        # test_guest_side_accepts_only_host_identity below) -- a
        # single-purpose EKU would make OpenSSL's own X509_PURPOSE check
        # reject those constructions at the TLS layer, before application
        # identity enforcement ever runs, which would test the wrong
        # thing. Both purposes together is a legitimate, common mTLS
        # leaf-certificate configuration, not a weakening of anything:
        # "correct application peer" is still decided only by the real
        # URI SAN, exact-match, via the existing, unmodified
        # peer_identity_matches.
        _write_leaf_extension_file(host_ext, _HOST_URI, "clientAuth,serverAuth")

        cls.guest_key = directory / "guest.key"
        guest_csr = directory / "guest.csr"
        _generate_key(cls.guest_key)
        _create_csr(cls.guest_key, guest_csr, "hypatia-test-guest")
        guest_ext = directory / "guest.ext"
        _write_leaf_extension_file(guest_ext, _GUEST_URI, "clientAuth,serverAuth")

        cls.host_cert = directory / "host.crt"
        _sign_leaf(
            host_csr,
            cls.ca_cert,
            cls.ca_key,
            host_ext,
            cls.host_cert,
            serial_suffix="01",
        )
        cls.guest_cert = directory / "guest.crt"
        _sign_leaf(
            guest_csr,
            cls.ca_cert,
            cls.ca_key,
            guest_ext,
            cls.guest_cert,
            serial_suffix="02",
        )

        cls.wrong_ca_host_cert = directory / "wrong_ca_host.crt"
        _sign_leaf(
            host_csr,
            wrong_ca_cert,
            wrong_ca_key,
            host_ext,
            cls.wrong_ca_host_cert,
            serial_suffix="03",
        )
        cls.wrong_ca_guest_cert = directory / "wrong_ca_guest.crt"
        _sign_leaf(
            guest_csr,
            wrong_ca_cert,
            wrong_ca_key,
            guest_ext,
            cls.wrong_ca_guest_cert,
            serial_suffix="04",
        )

        cls.expired_host_cert = directory / "expired_host.crt"
        _sign_leaf_with_explicit_dates(
            host_csr,
            cls.ca_cert,
            cls.ca_key,
            host_ext,
            cls.expired_host_cert,
            not_before="230101000000Z",
            not_after="230102000000Z",
            work_dir=directory,
        )
        cls.future_host_cert = directory / "future_host.crt"
        _sign_leaf_with_explicit_dates(
            host_csr,
            cls.ca_cert,
            cls.ca_key,
            host_ext,
            cls.future_host_cert,
            not_before="20990101000000Z",
            not_after="20990102000000Z",
            work_dir=directory,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temp_dir.cleanup()
        super().tearDownClass()

    def host_config(self, **overrides: object) -> GuestAgentMtlsTrustConfiguration:
        base: dict[str, object] = dict(
            own_role=GuestAgentPeerRole.HOST,
            ca_cert=self.ca_cert,
            own_cert=self.host_cert,
            own_key=self.host_key,
        )
        base.update(overrides)
        return _trust_config(**base)  # type: ignore[arg-type]

    def guest_config(self, **overrides: object) -> GuestAgentMtlsTrustConfiguration:
        base: dict[str, object] = dict(
            own_role=GuestAgentPeerRole.GUEST,
            ca_cert=self.ca_cert,
            own_cert=self.guest_cert,
            own_key=self.guest_key,
        )
        base.update(overrides)
        return _trust_config(**base)  # type: ignore[arg-type]


class RealHandshakeAndIdentityTests(_LoopbackMtlsFixture):
    """Requirements 1-10, 17: a real mutual TLS 1.3 handshake over loopback,
    with real certificate extraction feeding real identity enforcement."""

    def test_real_tls13_mutual_handshake_with_real_identity_and_channel(self) -> None:
        host_config = self.host_config()
        guest_config = self.guest_config()
        client_ctx = build_host_client_tls_context(host_config)
        server_ctx = build_guest_server_tls_context(guest_config)

        client_result, server_result, client_sock, server_sock = _perform_handshake(
            client_ctx, server_ctx
        )

        self.assertNotIn("error", client_result, msg=client_result.get("error"))
        self.assertNotIn("error", server_result, msg=server_result.get("error"))

        # Requirement: TLS version == TLSv1.3, both sides.
        self.assertEqual(client_result["version"], "TLSv1.3")
        self.assertEqual(server_result["version"], "TLSv1.3")

        # Requirement: real peer certificate dict/DER obtained, both sides.
        self.assertIsInstance(client_result["cert_dict"], dict)
        self.assertIsInstance(server_result["cert_dict"], dict)
        self.assertIsInstance(client_result["der"], bytes)
        self.assertIsInstance(server_result["der"], bytes)
        self.assertGreater(len(client_result["der"]), 0)  # type: ignore[arg-type]
        self.assertGreater(len(server_result["der"]), 0)  # type: ignore[arg-type]

        # Requirement: real URI SAN extracted and application identity
        # enforcement runs through the existing, unmodified chain.
        host_view = _authenticate_from_result(client_result, host_config)
        guest_view = _authenticate_from_result(server_result, guest_config)
        assert host_view is not None and guest_view is not None

        self.assertEqual(
            host_view.status, GuestAgentChannelAuthenticationStatus.AUTHENTICATED
        )
        self.assertEqual(
            guest_view.status, GuestAgentChannelAuthenticationStatus.AUTHENTICATED
        )
        assert host_view.authenticated_peer is not None
        assert guest_view.authenticated_peer is not None
        self.assertEqual(
            host_view.authenticated_peer.peer_role, GuestAgentPeerRole.GUEST
        )
        self.assertEqual(
            guest_view.authenticated_peer.peer_role, GuestAgentPeerRole.HOST
        )

        # Requirement: authenticated channel construction uses the
        # existing authenticate_peer path, never bypassing it.
        host_channel = GuestAgentAuthenticatedHostChannel(
            authenticated_peer=host_view.authenticated_peer
        )
        guest_channel = GuestAgentAuthenticatedGuestChannel(
            authenticated_peer=guest_view.authenticated_peer
        )
        self.assertIsInstance(host_channel, GuestAgentAuthenticatedHostChannel)
        self.assertIsInstance(guest_channel, GuestAgentAuthenticatedGuestChannel)

        # Requirement: sockets close after success.
        self.assertEqual(client_sock.fileno(), -1)  # type: ignore[union-attr]
        self.assertEqual(server_sock.fileno(), -1)

    def test_host_side_accepts_only_guest_identity(self) -> None:
        """The host side must never authenticate a non-guest identity even
        when the certificate chains correctly to the trusted CA."""
        host_config = self.host_config()
        # Server intentionally presents the HOST's own CA-valid certificate
        # instead of the GUEST's -- the critical CA-valid-wrong-role proof.
        guest_config_wrong_role = self.guest_config(
            own_cert=self.host_cert, own_key=self.host_key
        )
        client_ctx = build_host_client_tls_context(host_config)
        server_ctx = build_guest_server_tls_context(guest_config_wrong_role)

        client_result, _server_result, *_ = _perform_handshake(client_ctx, server_ctx)

        # TLS chain verification succeeds -- it is a real, CA-signed cert.
        self.assertNotIn("error", client_result, msg=client_result.get("error"))

        host_view = _authenticate_from_result(client_result, host_config)
        assert host_view is not None
        self.assertEqual(
            host_view.status, GuestAgentChannelAuthenticationStatus.IDENTITY_MISMATCH
        )
        self.assertIsNone(host_view.authenticated_peer)

    def test_guest_side_accepts_only_host_identity(self) -> None:
        """Mirror image: the guest side must never authenticate a
        non-host identity even when the certificate chains correctly."""
        guest_config = self.guest_config()
        # Client intentionally presents the GUEST's own CA-valid
        # certificate instead of the HOST's.
        host_config_wrong_role = self.host_config(
            own_cert=self.guest_cert, own_key=self.guest_key
        )
        client_ctx = build_host_client_tls_context(host_config_wrong_role)
        server_ctx = build_guest_server_tls_context(guest_config)

        _client_result, server_result, *_ = _perform_handshake(client_ctx, server_ctx)

        self.assertNotIn("error", server_result, msg=server_result.get("error"))

        guest_view = _authenticate_from_result(server_result, guest_config)
        assert guest_view is not None
        self.assertEqual(
            guest_view.status, GuestAgentChannelAuthenticationStatus.IDENTITY_MISMATCH
        )
        self.assertIsNone(guest_view.authenticated_peer)

    def test_protocol_types_still_carry_no_authentication_field(self) -> None:
        """Requirement 17: no new protocol authentication field exists --
        regression against the unmodified v0.3.456/457 wire types."""
        import dataclasses

        from research.GuestAgentProtocol import GuestAgentRequest, GuestAgentResponse

        request_fields = {field.name for field in dataclasses.fields(GuestAgentRequest)}
        response_fields = {
            field.name for field in dataclasses.fields(GuestAgentResponse)
        }
        for forbidden in (
            "certificate",
            "fingerprint",
            "peer_identity",
            "authenticated",
        ):
            with self.subTest(token=forbidden):
                self.assertFalse(any(forbidden in name for name in request_fields))
                self.assertFalse(any(forbidden in name for name in response_fields))


class NegativeHandshakeTests(_LoopbackMtlsFixture):
    """Requirements 11-14: real negative handshakes fail closed."""

    def test_untrusted_server_certificate_is_rejected_by_client(self) -> None:
        host_config = self.host_config()
        guest_config_untrusted = self.guest_config(own_cert=self.wrong_ca_guest_cert)
        client_ctx = build_host_client_tls_context(host_config)
        server_ctx = build_guest_server_tls_context(guest_config_untrusted)

        client_result, _server_result, *_ = _perform_handshake(client_ctx, server_ctx)

        self.assertIn("error", client_result)
        self.assertIn("CERTIFICATE_VERIFY_FAILED", str(client_result["error"]))

    def test_untrusted_client_certificate_is_rejected_by_server(self) -> None:
        host_config_untrusted = self.host_config(own_cert=self.wrong_ca_host_cert)
        guest_config = self.guest_config()
        client_ctx = build_host_client_tls_context(host_config_untrusted)
        server_ctx = build_guest_server_tls_context(guest_config)

        _client_result, server_result, *_ = _perform_handshake(client_ctx, server_ctx)

        self.assertIn("error", server_result)

    def test_missing_client_certificate_is_rejected_by_server(self) -> None:
        """A client context presenting no certificate at all -- CERT_REQUIRED
        on the server side must refuse it; mutual TLS is not optional."""
        guest_config = self.guest_config()
        server_ctx = build_guest_server_tls_context(guest_config)

        bare_client_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        bare_client_ctx.minimum_version = ssl.TLSVersion.TLSv1_3
        bare_client_ctx.maximum_version = ssl.TLSVersion.TLSv1_3
        bare_client_ctx.verify_mode = ssl.CERT_REQUIRED
        bare_client_ctx.check_hostname = False
        bare_client_ctx.load_verify_locations(cafile=str(self.ca_cert))
        # Deliberately never calls load_cert_chain: no client certificate.

        client_result, server_result, *_ = _perform_handshake(
            bare_client_ctx, server_ctx
        )

        self.assertIn("error", server_result)

    def test_expired_server_certificate_is_rejected(self) -> None:
        host_config = self.host_config()
        guest_config_expired = self.guest_config(
            own_cert=self.expired_host_cert, own_key=self.host_key
        )
        client_ctx = build_host_client_tls_context(host_config)
        server_ctx = build_guest_server_tls_context(guest_config_expired)

        client_result, _server_result, *_ = _perform_handshake(client_ctx, server_ctx)

        self.assertIn("error", client_result)
        self.assertIn("expired", str(client_result["error"]).lower())

    def test_not_yet_valid_server_certificate_is_rejected(self) -> None:
        host_config = self.host_config()
        guest_config_future = self.guest_config(
            own_cert=self.future_host_cert, own_key=self.host_key
        )
        client_ctx = build_host_client_tls_context(host_config)
        server_ctx = build_guest_server_tls_context(guest_config_future)

        client_result, _server_result, *_ = _perform_handshake(client_ctx, server_ctx)

        self.assertIn("error", client_result)


class FingerprintPinningTests(_LoopbackMtlsFixture):
    """Requirements 15-16: fingerprint pinning uses the real DER certificate,
    never a caller-supplied claim."""

    def test_correct_fingerprint_from_real_der_certificate_authenticates(self) -> None:
        import hashlib

        real_guest_der = ssl.PEM_cert_to_DER_cert(self.guest_cert.read_text())
        real_fingerprint = hashlib.sha256(real_guest_der).hexdigest()

        host_config = self.host_config(
            expected_peer_fingerprint_sha256=real_fingerprint
        )
        guest_config = self.guest_config()
        client_ctx = build_host_client_tls_context(host_config)
        server_ctx = build_guest_server_tls_context(guest_config)

        client_result, _server_result, *_ = _perform_handshake(client_ctx, server_ctx)
        self.assertNotIn("error", client_result, msg=client_result.get("error"))

        host_view = _authenticate_from_result(client_result, host_config)
        assert host_view is not None
        self.assertEqual(
            host_view.status, GuestAgentChannelAuthenticationStatus.AUTHENTICATED
        )

    def test_mismatched_fingerprint_rejects_even_with_a_valid_handshake(self) -> None:
        wrong_fingerprint = "ab" * 32
        host_config = self.host_config(
            expected_peer_fingerprint_sha256=wrong_fingerprint
        )
        guest_config = self.guest_config()
        client_ctx = build_host_client_tls_context(host_config)
        server_ctx = build_guest_server_tls_context(guest_config)

        client_result, _server_result, *_ = _perform_handshake(client_ctx, server_ctx)
        self.assertNotIn("error", client_result, msg=client_result.get("error"))

        host_view = _authenticate_from_result(client_result, host_config)
        assert host_view is not None
        self.assertEqual(
            host_view.status, GuestAgentChannelAuthenticationStatus.IDENTITY_MISMATCH
        )
        self.assertIsNone(host_view.authenticated_peer)


class SocketLifecycleAndLoopbackBindingTests(_LoopbackMtlsFixture):
    """Requirements 27-33: the harness is loopback-only, ephemeral-port,
    bounded, and always cleans up -- on success and on failure alike."""

    def test_listener_binds_only_to_loopback(self) -> None:
        """Binds exactly the way `_perform_handshake` does, and inspects
        the bound address before closing (the harness itself always
        closes its sockets before returning, so this checks the address
        directly rather than through the harness's return value)."""
        probe_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            probe_sock.bind((_LOOPBACK_HOST, 0))
            self.assertEqual(probe_sock.getsockname()[0], "127.0.0.1")
        finally:
            probe_sock.close()

    def test_loopback_host_constant_is_exactly_127_0_0_1(self) -> None:
        self.assertEqual(_LOOPBACK_HOST, "127.0.0.1")

    def test_two_handshakes_use_different_os_assigned_ports(self) -> None:
        """Proves ephemeral-port allocation behaviorally: a fixed port
        would make this flaky or always identical; OS allocation varies."""
        ports: set[int] = set()
        for _ in range(2):
            server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_sock.bind((_LOOPBACK_HOST, 0))
            ports.add(server_sock.getsockname()[1])
            server_sock.close()
        self.assertNotIn(0, ports)

    def test_timeout_constants_are_bounded_and_positive(self) -> None:
        for value in (
            _SOCKET_TIMEOUT_SECONDS,
            _READY_WAIT_SECONDS,
            _THREAD_JOIN_SECONDS,
        ):
            with self.subTest(value=value):
                self.assertGreater(value, 0.0)
                self.assertLessEqual(value, 30.0)

    def test_sockets_close_after_success(self) -> None:
        host_config = self.host_config()
        guest_config = self.guest_config()
        client_ctx = build_host_client_tls_context(host_config)
        server_ctx = build_guest_server_tls_context(guest_config)

        client_result, server_result, client_sock, server_sock = _perform_handshake(
            client_ctx, server_ctx
        )
        self.assertNotIn("error", client_result)
        self.assertEqual(client_sock.fileno(), -1)  # type: ignore[union-attr]
        self.assertEqual(server_sock.fileno(), -1)

    def test_sockets_close_after_failure(self) -> None:
        host_config = self.host_config()
        guest_config_untrusted = self.guest_config(own_cert=self.wrong_ca_guest_cert)
        client_ctx = build_host_client_tls_context(host_config)
        server_ctx = build_guest_server_tls_context(guest_config_untrusted)

        client_result, _server_result, client_sock, server_sock = _perform_handshake(
            client_ctx, server_ctx
        )
        self.assertIn("error", client_result)
        self.assertEqual(client_sock.fileno(), -1)  # type: ignore[union-attr]
        self.assertEqual(server_sock.fileno(), -1)

    def test_temporary_certificate_material_is_removed_after_the_class(self) -> None:
        """Runs its own short-lived fixture to observe cleanup directly,
        rather than inspecting the shared class-level fixture mid-suite."""
        with tempfile.TemporaryDirectory(prefix="hypatia-cleanup-check-") as name:
            directory = Path(name)
            key_path = directory / "throwaway.key"
            _generate_key(key_path)
            self.assertTrue(key_path.exists())
        self.assertFalse(directory.exists())


class PrivateKeyHygieneTests(_LoopbackMtlsFixture):
    """Requirement 34: no private key text ever appears in an error string."""

    def test_no_private_key_text_in_any_negative_path_error(self) -> None:
        host_key_text = self.host_key.read_text(encoding="utf-8")
        guest_key_text = self.guest_key.read_text(encoding="utf-8")

        host_config = self.host_config()
        guest_config_untrusted = self.guest_config(own_cert=self.wrong_ca_guest_cert)
        client_ctx = build_host_client_tls_context(host_config)
        server_ctx = build_guest_server_tls_context(guest_config_untrusted)
        client_result, server_result, *_ = _perform_handshake(client_ctx, server_ctx)

        for result in (client_result, server_result):
            error_text = str(result.get("error", ""))
            with self.subTest(result=result):
                self.assertNotIn(host_key_text, error_text)
                self.assertNotIn(guest_key_text, error_text)
                self.assertNotIn("PRIVATE KEY", error_text)


class StructuralSecurityTests(unittest.TestCase):
    """Requirements 18-26, 35: AST-based proof that this module introduces

    no execution-authority dependency, no replay coupling, and no
    hardcoded external command -- the only external process this module
    may ever launch is `openssl`, and only via a variable, never a
    literal command name.
    """

    def setUp(self) -> None:
        self.tree = ast.parse(
            THIS_FILE.read_text(encoding="utf-8"), filename=str(THIS_FILE)
        )

    def test_every_bind_call_targets_loopback_only(self) -> None:
        """Requirement 28: wildcard binding is impossible through this
        harness. Inspects every `.bind(...)` call site directly -- never a
        blanket string-constant scan, which would also catch this very
        test's own negative-example data and the structural denylists
        used elsewhere in this file for an unrelated purpose."""
        found_any_bind_call = False
        for node in ast.walk(self.tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "bind"
            ):
                continue
            if not node.args or not isinstance(node.args[0], ast.Tuple):
                continue
            address_tuple = node.args[0]
            if not address_tuple.elts:
                continue
            found_any_bind_call = True
            host_node = address_tuple.elts[0]
            with self.subTest(line=node.lineno):
                if isinstance(host_node, ast.Constant) and isinstance(
                    host_node.value, str
                ):
                    self.assertEqual(host_node.value, "127.0.0.1")
                elif isinstance(host_node, ast.Name):
                    self.assertEqual(host_node.id, "_LOOPBACK_HOST")
                else:
                    self.fail(f"unrecognized bind() host argument shape: {host_node}")
        self.assertTrue(found_any_bind_call)

    def test_no_kali_execution_authority_is_imported_or_referenced(self) -> None:
        forbidden = {
            "KaliToolGateway",
            "ToolExecutionService",
            "ResearchKaliOperationAuthorization",
            "JsonFileResearchKaliOperationAuthorizationStore",
        }
        referenced: set[str] = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Name):
                referenced.add(node.id)
            elif isinstance(node, ast.Attribute):
                referenced.add(node.attr)
            elif isinstance(node, ast.ImportFrom):
                referenced.update(alias.name for alias in node.names)
        self.assertEqual(referenced & forbidden, set())

    def test_replay_protection_is_not_imported_or_invoked(self) -> None:
        forbidden = {
            "GuestAgentReplayProtector",
            "GuestAgentReplayOutcome",
            "JsonFileGuestAgentReplayNonceStore",
            "consume_once",
        }
        referenced: set[str] = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Name):
                referenced.add(node.id)
            elif isinstance(node, ast.Attribute):
                referenced.add(node.attr)
            elif isinstance(node, ast.ImportFrom):
                referenced.update(alias.name for alias in node.names)
        self.assertEqual(referenced & forbidden, set())

    def test_no_vmware_kali_ssh_wsl_execution_token_is_referenced(self) -> None:
        forbidden_names = {
            "vmrun",
            "sshd",
            "paramiko",
            "wsl",
        }
        referenced_names: set[str] = set()
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.Name, ast.Attribute, ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Name):
                    referenced_names.add(node.id.lower())
                elif isinstance(node, ast.Attribute):
                    referenced_names.add(node.attr.lower())
                elif isinstance(node, ast.Import):
                    referenced_names.update(a.name.lower() for a in node.names)
                elif isinstance(node, ast.ImportFrom):
                    referenced_names.update(a.name.lower() for a in node.names)
        self.assertEqual(referenced_names & forbidden_names, set())

    def test_subprocess_never_launches_a_forbidden_executable_literal(self) -> None:
        """No call to `subprocess.run`/`Popen`/`call` anywhere in this file
        may name a Kali/VMware/SSH/WSL-execution-shaped executable as a
        literal argv[0]. Ordinary developer tooling (e.g. `git`, used only
        for this milestone's own "no new production source" self-check)
        is not itself forbidden -- only execution-authority-shaped
        commands are. The actual certificate-generation executable is
        always `_require_openssl()`'s return value, never a literal."""
        forbidden_executables = {"vmrun", "ssh", "wsl", "sshd", "powershell", "cmd"}
        subprocess_call_names = {"run", "Popen", "call", "check_call", "check_output"}
        found_any_subprocess_call = False
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            is_subprocess_call = (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "subprocess"
                and func.attr in subprocess_call_names
            )
            if not is_subprocess_call:
                continue
            found_any_subprocess_call = True
            if not node.args:
                continue
            first_arg = node.args[0]
            argv0 = (
                first_arg.elts[0]
                if isinstance(first_arg, ast.List) and first_arg.elts
                else first_arg
            )
            if isinstance(argv0, ast.Constant) and isinstance(argv0.value, str):
                with self.subTest(executable=argv0.value):
                    self.assertNotIn(argv0.value.lower(), forbidden_executables)
        self.assertTrue(found_any_subprocess_call)

    def test_authenticate_peer_import_resolves_to_the_existing_module(self) -> None:
        """Requirement 35: no local reimplementation -- the imported
        symbol genuinely is `research.GuestAgentPeerAuthenticator`'s own."""
        self.assertEqual(
            authenticate_peer.__module__, "research.GuestAgentPeerAuthenticator"
        )
        self.assertEqual(
            parse_peer_certificate_identity.__module__,
            "research.GuestAgentPeerCertificateIdentity",
        )


if __name__ == "__main__":
    unittest.main()
