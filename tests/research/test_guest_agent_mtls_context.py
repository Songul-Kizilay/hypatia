"""Strict mTLS `SSLContext` construction never has a fail-open branch.

TLS HANDSHAKE SUCCESS != EXECUTION AUTHORITY. mTLS CONNECTED != PERMISSION
TO EXECUTE. Every test below either proves both builder functions produce
a genuinely mutual, strict configuration, or proves there is no socket, no
network, and no verification-disable path anywhere in this module.
"""

from __future__ import annotations

import ast
import ssl
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError
from research.GuestAgentMtlsContext import (
    build_guest_server_tls_context,
    build_host_client_tls_context,
)
from research.GuestAgentMtlsTrustConfiguration import (
    GuestAgentMtlsTrustConfiguration,
    GuestAgentPeerRole,
)

NEW_MTLS_MODULE_PATHS = (
    SRC_DIR / "research" / "GuestAgentMtlsTrustConfiguration.py",
    SRC_DIR / "research" / "GuestAgentPeerCertificateIdentity.py",
    SRC_DIR / "research" / "GuestAgentMtlsContext.py",
)


def _host_config(**overrides: object) -> GuestAgentMtlsTrustConfiguration:
    base: dict[str, object] = dict(
        own_role=GuestAgentPeerRole.HOST,
        trusted_ca_certificate_path="/trusted/ca.pem",
        own_certificate_path="/trusted/host.pem",
        own_private_key_path="/trusted/host.key",
    )
    base.update(overrides)
    return GuestAgentMtlsTrustConfiguration(**base)  # type: ignore[arg-type]


def _guest_config(**overrides: object) -> GuestAgentMtlsTrustConfiguration:
    base: dict[str, object] = dict(
        own_role=GuestAgentPeerRole.GUEST,
        trusted_ca_certificate_path="/trusted/ca.pem",
        own_certificate_path="/trusted/guest.pem",
        own_private_key_path="/trusted/guest.key",
    )
    base.update(overrides)
    return GuestAgentMtlsTrustConfiguration(**base)  # type: ignore[arg-type]


class _MockedLoading(unittest.TestCase):
    """Common fixture: mock the two filesystem-touching SSLContext methods
    so every test here runs without any real certificate/key file."""

    def setUp(self) -> None:
        self._load_verify_patch = patch.object(ssl.SSLContext, "load_verify_locations")
        self._load_chain_patch = patch.object(ssl.SSLContext, "load_cert_chain")
        self.load_verify_locations = self._load_verify_patch.start()
        self.load_cert_chain = self._load_chain_patch.start()
        self.addCleanup(self._load_verify_patch.stop)
        self.addCleanup(self._load_chain_patch.stop)


class HostClientContextTests(_MockedLoading):
    """Requirements 18, 19, 24, 25: client authenticates the server and is
    itself authenticated; TLS minimum is explicit."""

    def test_requires_a_host_role_configuration(self) -> None:
        with self.assertRaises(ResearchError):
            build_host_client_tls_context(_guest_config())

    def test_requires_a_bounded_configuration_type(self) -> None:
        with self.assertRaises(ResearchError):
            build_host_client_tls_context("not a config")  # type: ignore[arg-type]

    def test_verify_mode_is_cert_required(self) -> None:
        context = build_host_client_tls_context(_host_config())
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)

    def test_check_hostname_is_explicitly_disabled_not_merely_unset(self) -> None:
        """`check_hostname` is for `dNSName` SANs (and legacy CN) only --
        it never matches a `URI` SAN, so leaving it `True` here would look
        like an identity check without performing one. Identity is
        checked post-handshake instead, via
        `research.GuestAgentPeerCertificateIdentity.peer_identity_matches`,
        symmetrically with the guest-server side.
        """
        context = build_host_client_tls_context(_host_config())
        self.assertFalse(context.check_hostname)
        # Still fully verifies the certificate chain -- disabling the
        # (inapplicable) hostname check never weakens CA trust enforcement.
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)

    def test_tls_minimum_and_maximum_are_both_explicitly_tls13(self) -> None:
        context = build_host_client_tls_context(_host_config())
        self.assertEqual(context.minimum_version, ssl.TLSVersion.TLSv1_3)
        self.assertEqual(context.maximum_version, ssl.TLSVersion.TLSv1_3)

    def test_compression_is_disabled(self) -> None:
        context = build_host_client_tls_context(_host_config())
        self.assertTrue(bool(context.options & ssl.OP_NO_COMPRESSION))

    def test_key_logging_is_never_enabled(self) -> None:
        context = build_host_client_tls_context(_host_config())
        self.assertIsNone(context.keylog_filename)

    def test_loads_the_exact_configured_trust_and_identity_paths(self) -> None:
        config = _host_config(
            trusted_ca_certificate_path="/custom/ca.pem",
            own_certificate_path="/custom/host.pem",
            own_private_key_path="/custom/host.key",
        )
        build_host_client_tls_context(config)
        self.load_verify_locations.assert_called_once_with(cafile="/custom/ca.pem")
        self.load_cert_chain.assert_called_once_with(
            certfile="/custom/host.pem", keyfile="/custom/host.key"
        )

    def test_presents_its_own_certificate_not_only_verifying_the_server(
        self,
    ) -> None:
        """A client that sends no certificate is not mutual TLS -- this
        proves `load_cert_chain` (presenting the client's own identity) is
        always called, not merely `load_verify_locations`."""
        build_host_client_tls_context(_host_config())
        self.load_cert_chain.assert_called_once()


class GuestServerContextTests(_MockedLoading):
    """Requirements 20, 21, 23: server requires and verifies a client
    certificate -- never CERT_NONE."""

    def test_requires_a_guest_role_configuration(self) -> None:
        with self.assertRaises(ResearchError):
            build_guest_server_tls_context(_host_config())

    def test_raw_server_context_defaults_to_cert_none(self) -> None:
        """Ground truth for why this builder must override the default:
        a bare `PROTOCOL_TLS_SERVER` context accepts anonymous clients."""
        raw = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.assertEqual(raw.verify_mode, ssl.CERT_NONE)

    def test_verify_mode_is_cert_required_not_the_default_cert_none(self) -> None:
        context = build_guest_server_tls_context(_guest_config())
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertNotEqual(context.verify_mode, ssl.CERT_NONE)

    def test_tls_minimum_and_maximum_are_both_explicitly_tls13(self) -> None:
        context = build_guest_server_tls_context(_guest_config())
        self.assertEqual(context.minimum_version, ssl.TLSVersion.TLSv1_3)
        self.assertEqual(context.maximum_version, ssl.TLSVersion.TLSv1_3)

    def test_compression_is_disabled(self) -> None:
        context = build_guest_server_tls_context(_guest_config())
        self.assertTrue(bool(context.options & ssl.OP_NO_COMPRESSION))

    def test_key_logging_is_never_enabled(self) -> None:
        context = build_guest_server_tls_context(_guest_config())
        self.assertIsNone(context.keylog_filename)

    def test_loads_the_exact_configured_trust_and_identity_paths(self) -> None:
        config = _guest_config(
            trusted_ca_certificate_path="/custom/ca.pem",
            own_certificate_path="/custom/guest.pem",
            own_private_key_path="/custom/guest.key",
        )
        build_guest_server_tls_context(config)
        self.load_verify_locations.assert_called_once_with(cafile="/custom/ca.pem")
        self.load_cert_chain.assert_called_once_with(
            certfile="/custom/guest.pem", keyfile="/custom/guest.key"
        )

    def test_requires_a_client_certificate_this_is_what_makes_it_mutual(
        self,
    ) -> None:
        """A server configuration that validates itself but accepts
        anonymous clients is not mTLS -- this proves `verify_mode` is
        always forced to `CERT_REQUIRED`, never left at the insecure
        default."""
        context = build_guest_server_tls_context(_guest_config())
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)


class NoFailOpenConfigurationTests(unittest.TestCase):
    """Requirements 21-23, 26, 27: no CERT_NONE, no unverified helper, no
    disable-verification fallback, no plaintext fallback, anywhere."""

    def test_no_cert_none_assignment_exists_in_the_module_source(self) -> None:
        """Checked by the real AST attribute references, not by scanning
        prose -- this module's own docstring correctly *names*
        `CERT_NONE` while explaining the insecure default it overrides,
        and that explanation (a string literal, never an `ast.Attribute`
        node) must not itself trip this check.
        """
        path = SRC_DIR / "research" / "GuestAgentMtlsContext.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        referenced_attributes = {
            node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
        }
        self.assertNotIn("CERT_NONE", referenced_attributes)

    def test_no_unverified_context_helper_is_used(self) -> None:
        """Checked by the real AST call targets, not by scanning prose --
        this module's own docstring correctly *names*
        `ssl.create_default_context` while explaining why it is avoided
        (it would auto-load the OS's global CA bundle), and that
        explanation must not itself trip this check.
        """
        path = SRC_DIR / "research" / "GuestAgentMtlsContext.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        forbidden_calls = {"_create_unverified_context", "create_default_context"}
        called_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute):
                    called_names.add(func.attr)
                elif isinstance(func, ast.Name):
                    called_names.add(func.id)
        self.assertEqual(called_names & forbidden_calls, set())

    def test_no_development_mode_parameter_exists_on_either_builder(self) -> None:
        import inspect

        for builder in (build_host_client_tls_context, build_guest_server_tls_context):
            signature = inspect.signature(builder)
            for name in signature.parameters:
                with self.subTest(builder=builder.__name__, parameter=name):
                    self.assertNotIn("dev", name.lower())
                    self.assertNotIn("insecure", name.lower())
                    self.assertNotIn("skip_verif", name.lower())
                    self.assertNotIn("disable", name.lower())

    def test_both_builders_always_reach_the_same_strict_verify_mode(self) -> None:
        """There is exactly one configuration outcome per role -- no
        parameterized branch could produce a weaker one."""
        with (
            patch.object(ssl.SSLContext, "load_verify_locations"),
            patch.object(ssl.SSLContext, "load_cert_chain"),
        ):
            host_context = build_host_client_tls_context(_host_config())
            guest_context = build_guest_server_tls_context(_guest_config())
        self.assertEqual(host_context.verify_mode, ssl.CERT_REQUIRED)
        self.assertEqual(guest_context.verify_mode, ssl.CERT_REQUIRED)


class NoSocketOrNetworkTests(unittest.TestCase):
    """Requirements 36-41: zero sockets, network clients, subprocesses, or
    VMware/SSH/WSL activity anywhere in context construction."""

    def test_building_either_context_creates_no_socket(self) -> None:
        with (
            patch.object(ssl.SSLContext, "load_verify_locations"),
            patch.object(ssl.SSLContext, "load_cert_chain"),
            patch("socket.socket") as sock,
            patch("socket.create_connection") as create_connection,
        ):
            build_host_client_tls_context(_host_config())
            build_guest_server_tls_context(_guest_config())
        sock.assert_not_called()
        create_connection.assert_not_called()

    def test_building_either_context_creates_no_subprocess(self) -> None:
        with (
            patch.object(ssl.SSLContext, "load_verify_locations"),
            patch.object(ssl.SSLContext, "load_cert_chain"),
            patch("subprocess.run") as run,
            patch("subprocess.Popen") as popen,
        ):
            build_host_client_tls_context(_host_config())
            build_guest_server_tls_context(_guest_config())
        run.assert_not_called()
        popen.assert_not_called()

    def test_no_real_network_client_module_is_imported(self) -> None:
        forbidden_modules = {
            "requests",
            "httpx",
            "urllib",
            "paramiko",
            "fabric",
        }
        for path in NEW_MTLS_MODULE_PATHS:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imported: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name.split(".")[0] for alias in node.names)
                elif (
                    isinstance(node, ast.ImportFrom) and node.module and node.level == 0
                ):
                    imported.add(node.module.split(".")[0])
            with self.subTest(module=path.name):
                self.assertEqual(imported & forbidden_modules, set())

    def test_no_socket_module_is_imported_by_the_new_mtls_modules(self) -> None:
        """`ssl` is expected and used; raw `socket` is not -- these modules
        build configuration objects only, never a transport."""
        for path in NEW_MTLS_MODULE_PATHS:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imported: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name.split(".")[0] for alias in node.names)
                elif (
                    isinstance(node, ast.ImportFrom) and node.module and node.level == 0
                ):
                    imported.add(node.module.split(".")[0])
            with self.subTest(module=path.name):
                self.assertNotIn("socket", imported)

    def test_no_kali_gateway_or_tool_execution_import_exists(self) -> None:
        forbidden = {"KaliToolGateway", "ToolExecutionService"}
        for path in NEW_MTLS_MODULE_PATHS:
            source = path.read_text(encoding="utf-8")
            for name in forbidden:
                with self.subTest(module=path.name, token=name):
                    self.assertNotIn(name, source)

    def test_no_vmware_ssh_or_wsl_adapter_import_exists(self) -> None:
        forbidden = {
            "VmwareKaliOperationProcessAdapter",
            "WslKaliOperationProcessAdapter",
            "SshVMwareKaliGuestReadinessProbe",
            "VmrunVMwareKaliHostReadinessProbe",
        }
        for path in NEW_MTLS_MODULE_PATHS:
            source = path.read_text(encoding="utf-8")
            for name in forbidden:
                with self.subTest(module=path.name, token=name):
                    self.assertNotIn(name, source)

    def test_no_listening_socket_was_ever_created_at_import_time(self) -> None:
        """Importing these modules must have zero side effects -- re-import
        under a socket patch and confirm nothing was touched."""
        import importlib

        with patch("socket.socket") as sock:
            importlib.reload(sys.modules["research.GuestAgentMtlsContext"])
        sock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
