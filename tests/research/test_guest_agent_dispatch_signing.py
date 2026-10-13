"""HOST-side dispatch-proof signing (`research.GuestAgentDispatchSigning`).

Proves: a signed envelope cannot be created without a real, consumed
`GuestAgentHostDispatchGrant`; the high-level API cannot sign an
arbitrary `GuestAgentRequest`; the grant remains one-shot through
signing (including under real concurrency); the dispatch signing key
remains a completely separate security domain from the mTLS identity
key; and no HMAC/shared-secret/home-grown-crypto/OpenSSL-subprocess
pathway exists anywhere in this module.
"""

from __future__ import annotations

import ast
import sys
import threading
import unittest
from datetime import UTC, datetime
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # noqa: E402
    Ed25519PrivateKey,
)

from core.Exceptions import ResearchError  # noqa: E402
from research.GuestAgentDispatchProof import (  # noqa: E402
    DISPATCH_PROOF_GUEST_AUDIENCE_IDENTITY,
    DISPATCH_PROOF_HOST_ISSUER_IDENTITY,
    GuestAgentDispatchProofVersion,
)
from research.GuestAgentDispatchSigning import (  # noqa: E402
    GuestAgentDispatchSigningError,
    create_signed_dispatch_envelope,
)
from research.GuestAgentHostAuthorizationHandoff import (  # noqa: E402
    consume_authorization_for_guest_agent_dispatch,
)
from research.GuestAgentProtocol import GuestAgentProtocolVersion  # noqa: E402
from tests.research.test_guest_agent_host_authorization_handoff import (  # noqa: E402
    FakeAuthorizationStore,
    _authorize,
    _https_preview,
    _preview,
)

SIGNING_MODULE_FILE = SRC_DIR / "research" / "GuestAgentDispatchSigning.py"

NOW = datetime(2026, 9, 7, 12, tzinfo=UTC)


def _real_grant(preview=None, *, authorization_id: str = "auth-1"):
    preview = preview or _preview()
    authorization = _authorize(preview, authorization_id=authorization_id)
    store = FakeAuthorizationStore([authorization])
    return consume_authorization_for_guest_agent_dispatch(
        store, authorization_id, preview, now=NOW
    )


class GrantRequirementTests(unittest.TestCase):
    """Requirement 1-2: a real grant is required; arbitrary requests cannot
    be signed through the high-level API."""

    def test_signing_requires_a_real_grant_object(self) -> None:
        signing_key = Ed25519PrivateKey.generate()
        for bad_grant in (None, "not a grant", object(), 12345):
            with self.subTest(value=bad_grant):
                with self.assertRaises(GuestAgentDispatchSigningError):
                    create_signed_dispatch_envelope(
                        bad_grant,  # type: ignore[arg-type]
                        request_id="r1",
                        nonce="n1",
                        signing_key=signing_key,
                        now=NOW,
                    )

    def test_high_level_api_has_no_arbitrary_request_parameter(self) -> None:
        import inspect

        parameters = set(inspect.signature(create_signed_dispatch_envelope).parameters)
        forbidden = {
            "request",
            "guest_agent_request",
            "operation_kind",
            "operation_digest",
            "logical_inputs",
            "hostname",
            "dns_record_type",
            "resolved_address",
        }
        self.assertEqual(parameters & forbidden, set())
        self.assertEqual(
            parameters, {"grant", "request_id", "nonce", "signing_key", "now"}
        )


class ConsumptionOrderingTests(unittest.TestCase):
    """Requirement 3: the existing consumed-authorization-before-grant
    ordering (v0.3.463) is untouched by this milestone."""

    def test_signing_still_requires_a_grant_produced_after_real_consumption(
        self,
    ) -> None:
        preview = _preview()
        authorization = _authorize(preview)
        store = FakeAuthorizationStore([authorization])
        grant = consume_authorization_for_guest_agent_dispatch(
            store, authorization.authorization_id, preview, now=NOW
        )
        self.assertEqual(store.current, [])
        envelope = create_signed_dispatch_envelope(
            grant,
            request_id="r1",
            nonce="n1",
            signing_key=Ed25519PrivateKey.generate(),
            now=NOW,
        )
        self.assertEqual(envelope.request.operation_digest, preview.operation_digest)


class OneShotPreservationTests(unittest.TestCase):
    """Requirements 4-6: grant one-shot semantics survive through signing,
    including under real concurrency."""

    def test_grant_remains_one_shot_after_signing(self) -> None:
        grant = _real_grant()
        signing_key = Ed25519PrivateKey.generate()
        create_signed_dispatch_envelope(
            grant, request_id="r1", nonce="n1", signing_key=signing_key, now=NOW
        )
        self.assertTrue(grant.already_materialized)
        with self.assertRaises(ResearchError):
            grant.materialize_request(request_id="r2", nonce="n2")

    def test_one_grant_creates_at_most_one_signed_envelope(self) -> None:
        grant = _real_grant()
        signing_key = Ed25519PrivateKey.generate()
        create_signed_dispatch_envelope(
            grant, request_id="r1", nonce="n1", signing_key=signing_key, now=NOW
        )
        with self.assertRaises(GuestAgentDispatchSigningError):
            create_signed_dispatch_envelope(
                grant, request_id="r2", nonce="n2", signing_key=signing_key, now=NOW
            )

    def test_concurrent_envelope_creation_yields_exactly_one_success(self) -> None:
        grant = _real_grant()
        signing_key = Ed25519PrivateKey.generate()
        successes: list[object] = []
        failures: list[Exception] = []
        lock = threading.Lock()

        def _attempt(index: int) -> None:
            try:
                envelope = create_signed_dispatch_envelope(
                    grant,
                    request_id=f"r{index}",
                    nonce=f"n{index}",
                    signing_key=signing_key,
                    now=NOW,
                )
                with lock:
                    successes.append(envelope)
            except GuestAgentDispatchSigningError as error:
                with lock:
                    failures.append(error)

        threads = [threading.Thread(target=_attempt, args=(i,)) for i in range(16)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5.0)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(failures), 15)


class RequestDerivationTests(unittest.TestCase):
    """Requirements 7-8: request derives from the exact validated preview;
    protocol_version is V1."""

    def test_request_derives_from_exact_validated_preview(self) -> None:
        preview = _preview(hostname="signing.example.com")
        grant = _real_grant(preview)
        envelope = create_signed_dispatch_envelope(
            grant,
            request_id="r1",
            nonce="n1",
            signing_key=Ed25519PrivateKey.generate(),
            now=NOW,
        )
        self.assertEqual(
            dict(envelope.request.logical_inputs)["hostname"], "signing.example.com"
        )
        self.assertEqual(envelope.request.operation_digest, preview.operation_digest)

    def test_https_preview_also_derives_correctly(self) -> None:
        preview = _https_preview(resolved_address="203.0.113.9")
        grant = _real_grant(preview)
        envelope = create_signed_dispatch_envelope(
            grant,
            request_id="r1",
            nonce="n1",
            signing_key=Ed25519PrivateKey.generate(),
            now=NOW,
        )
        self.assertEqual(
            dict(envelope.request.logical_inputs)["resolved_address"], "203.0.113.9"
        )

    def test_protocol_version_is_v1(self) -> None:
        grant = _real_grant()
        envelope = create_signed_dispatch_envelope(
            grant,
            request_id="r1",
            nonce="n1",
            signing_key=Ed25519PrivateKey.generate(),
            now=NOW,
        )
        self.assertIs(envelope.request.protocol_version, GuestAgentProtocolVersion.V1)


class ProofFieldTests(unittest.TestCase):
    """Requirements 9-19: proof version, request digest, issuer/audience,
    caller cannot override expiry/issuer/audience, bounded window,
    timezone-aware timestamps."""

    def _envelope(self, **overrides: object):
        grant = overrides.pop("grant", None) or _real_grant()
        signing_key = overrides.pop("signing_key", None) or Ed25519PrivateKey.generate()
        now = overrides.pop("now", NOW)
        return create_signed_dispatch_envelope(
            grant,
            request_id=str(overrides.pop("request_id", "r1")),
            nonce=str(overrides.pop("nonce", "n1")),
            signing_key=signing_key,
            now=now,  # type: ignore[arg-type]
        )

    def test_proof_version_is_fixed_v1(self) -> None:
        envelope = self._envelope()
        self.assertIs(
            envelope.proof.metadata.proof_version, GuestAgentDispatchProofVersion.V1
        )

    def test_request_sha256_uses_canonical_encoder(self) -> None:
        import hashlib

        from research.GuestAgentProtocolSerialization import (
            canonical_guest_agent_request_bytes,
        )

        envelope = self._envelope()
        expected = hashlib.sha256(
            canonical_guest_agent_request_bytes(envelope.request)
        ).hexdigest()
        self.assertEqual(envelope.proof.metadata.request_sha256, expected)

    def test_canonicalizer_import_resolves_to_the_existing_module(self) -> None:
        from research.GuestAgentProtocolSerialization import (
            canonical_guest_agent_request_bytes,
        )

        self.assertEqual(
            canonical_guest_agent_request_bytes.__module__,
            "research.GuestAgentProtocolSerialization",
        )

    def test_request_sha256_is_lowercase_64_char_hex(self) -> None:

        envelope = self._envelope()
        self.assertRegex(envelope.proof.metadata.request_sha256, r"^[0-9a-f]{64}$")

    def test_issuer_is_exact_host_identity(self) -> None:
        envelope = self._envelope()
        self.assertEqual(
            envelope.proof.metadata.issuer_identity, DISPATCH_PROOF_HOST_ISSUER_IDENTITY
        )

    def test_audience_is_exact_guest_identity(self) -> None:
        envelope = self._envelope()
        self.assertEqual(
            envelope.proof.metadata.audience_identity,
            DISPATCH_PROOF_GUEST_AUDIENCE_IDENTITY,
        )

    def test_caller_cannot_override_issuer_or_audience(self) -> None:
        import inspect

        parameters = set(inspect.signature(create_signed_dispatch_envelope).parameters)
        self.assertNotIn("issuer", parameters)
        self.assertNotIn("issuer_identity", parameters)
        self.assertNotIn("audience", parameters)
        self.assertNotIn("audience_identity", parameters)

    def test_caller_cannot_choose_arbitrary_expiry(self) -> None:
        import inspect

        parameters = set(inspect.signature(create_signed_dispatch_envelope).parameters)
        self.assertNotIn("expires_at", parameters)
        self.assertNotIn("expiry", parameters)
        self.assertNotIn("validity_seconds", parameters)

    def test_validity_window_is_bounded(self) -> None:
        from research.GuestAgentDispatchProof import (
            MAX_DISPATCH_PROOF_VALIDITY_SECONDS,
        )

        envelope = self._envelope()
        duration = (
            envelope.proof.metadata.expires_at - envelope.proof.metadata.issued_at
        ).total_seconds()
        self.assertEqual(duration, MAX_DISPATCH_PROOF_VALIDITY_SECONDS)

    def test_issued_at_is_timezone_aware(self) -> None:
        envelope = self._envelope()
        self.assertIsNotNone(envelope.proof.metadata.issued_at.utcoffset())

    def test_expires_at_is_timezone_aware(self) -> None:
        envelope = self._envelope()
        self.assertIsNotNone(envelope.proof.metadata.expires_at.utcoffset())

    def test_issued_at_equals_supplied_now(self) -> None:
        envelope = self._envelope(now=NOW)
        self.assertEqual(envelope.proof.metadata.issued_at, NOW)

    def test_naive_now_rejected(self) -> None:
        with self.assertRaises(GuestAgentDispatchSigningError):
            self._envelope(now=datetime(2026, 9, 7, 12))


class SigningKeyTypeTests(unittest.TestCase):
    """Requirement 26: malformed private key fails closed."""

    def test_non_ed25519_signing_key_rejected(self) -> None:
        grant = _real_grant()
        for bad_key in (None, b"not a key", "not a key", 12345, object()):
            with self.subTest(value=bad_key):
                with self.assertRaises(GuestAgentDispatchSigningError):
                    create_signed_dispatch_envelope(
                        grant,
                        request_id="r1",
                        nonce="n1",
                        signing_key=bad_key,  # type: ignore[arg-type]
                        now=NOW,
                    )

    def test_rsa_key_rejected_as_wrong_type(self) -> None:
        from cryptography.hazmat.primitives.asymmetric import rsa

        grant = _real_grant()
        rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        with self.assertRaises(GuestAgentDispatchSigningError):
            create_signed_dispatch_envelope(
                grant,
                request_id="r1",
                nonce="n1",
                signing_key=rsa_key,  # type: ignore[arg-type]
                now=NOW,
            )


class KeyHygieneTests(unittest.TestCase):
    """Requirements 54-56: private signing key bytes never appear in the
    proof, in errors, or in repr/log output."""

    def test_private_key_bytes_never_appear_in_the_proof(self) -> None:
        from cryptography.hazmat.primitives import serialization

        signing_key = Ed25519PrivateKey.generate()
        raw_private = signing_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        grant = _real_grant()
        envelope = create_signed_dispatch_envelope(
            grant, request_id="r1", nonce="n1", signing_key=signing_key, now=NOW
        )
        serialized = (
            repr(envelope) + repr(envelope.proof) + envelope.proof.signature_hex
        )
        self.assertNotIn(raw_private.hex(), serialized)
        self.assertNotIn(str(raw_private), serialized)

    def test_private_key_repr_never_leaks_bytes(self) -> None:
        signing_key = Ed25519PrivateKey.generate()
        self.assertNotIn("private", repr(signing_key).lower().replace("privatekey", ""))

    def test_signing_key_error_does_not_reflect_key_material(self) -> None:
        grant = _real_grant()
        hostile_marker = "ed25519-private-key-material-marker"
        try:
            create_signed_dispatch_envelope(
                grant,
                request_id="r1",
                nonce="n1",
                signing_key=hostile_marker,  # type: ignore[arg-type]
                now=NOW,
            )
            self.fail("expected a signing error")
        except GuestAgentDispatchSigningError as error:
            self.assertNotIn(hostile_marker, str(error))
            self.assertNotIn(hostile_marker, error.failure.reason)


class NoGenericSigningOracleTests(unittest.TestCase):
    """Requirements 51-52: no HMAC/shared-secret, no home-grown crypto, no
    OpenSSL subprocess, no generic signing function."""

    def setUp(self) -> None:
        self.tree = ast.parse(
            SIGNING_MODULE_FILE.read_text(encoding="utf-8"),
            filename=str(SIGNING_MODULE_FILE),
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

    def test_no_hmac_reference(self) -> None:
        self.assertNotIn("hmac", self._referenced_names(self.tree))

    def test_no_subprocess_or_openssl_reference(self) -> None:
        referenced = {name.lower() for name in self._referenced_names(self.tree)}
        self.assertEqual(referenced & {"subprocess", "openssl", "popen"}, set())

    def test_no_generic_sign_bytes_function_is_defined(self) -> None:
        forbidden_names = {
            "sign",
            "sign_bytes",
            "sign_arbitrary_payload",
            "sign_request",
        }
        defined_functions = {
            node.name
            for node in ast.walk(self.tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertEqual(defined_functions & forbidden_names, set())

    def test_only_one_public_function_is_defined_at_module_level(self) -> None:
        public_functions = [
            node.name
            for node in self.tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not node.name.startswith("_")
        ]
        self.assertEqual(public_functions, ["create_signed_dispatch_envelope"])

    def test_no_custom_elliptic_curve_arithmetic_tokens(self) -> None:
        forbidden = {
            "modinv",
            "scalarmult",
            "curve25519_base",
            "point_add",
            "field_mod",
        }
        lowered = {name.lower() for name in self._referenced_names(self.tree)}
        self.assertEqual(lowered & forbidden, set())


class KeyDomainSeparationTests(unittest.TestCase):
    """Requirements 53: dispatch signing key is a separate security domain
    from the mTLS identity key."""

    def setUp(self) -> None:
        self.tree = ast.parse(
            SIGNING_MODULE_FILE.read_text(encoding="utf-8"),
            filename=str(SIGNING_MODULE_FILE),
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

    def test_no_mtls_module_is_imported_or_referenced(self) -> None:
        forbidden = {
            "GuestAgentMtlsContext",
            "GuestAgentMtlsTrustConfiguration",
            "build_host_client_tls_context",
            "build_guest_server_tls_context",
            "own_private_key_path",
        }
        self.assertEqual(self._referenced_names(self.tree) & forbidden, set())

    def test_signing_key_parameter_is_the_only_key_input(self) -> None:
        import inspect

        parameters = inspect.signature(create_signed_dispatch_envelope).parameters
        key_like_params = [name for name in parameters if "key" in name.lower()]
        self.assertEqual(key_like_params, ["signing_key"])


class ReplayIndependenceAtSigningTests(unittest.TestCase):
    """Requirement 60: replay protector is not called during signing."""

    def test_replay_protector_symbols_are_not_referenced(self) -> None:
        tree = ast.parse(
            SIGNING_MODULE_FILE.read_text(encoding="utf-8"),
            filename=str(SIGNING_MODULE_FILE),
        )
        referenced: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                referenced.add(node.id)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                referenced.update(alias.name for alias in node.names)
        forbidden = {
            "GuestAgentReplayProtector",
            "GuestAgentReplayOutcome",
            "consume_once",
        }
        self.assertEqual(referenced & forbidden, set())


if __name__ == "__main__":
    unittest.main()
