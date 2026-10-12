"""Guest-Agent channel authentication enforcement foundation, v0.3.459.

AUTHENTICATED PEER != EXECUTION AUTHORITY. AUTHENTICATED CHANNEL != EXECUTION
AUTHORITY. AUTHENTICATED CHANNEL != OPERATION AUTHORIZATION. TLS CONTEXT
CONFIGURED != PEER AUTHENTICATED. TLS HANDSHAKE SUCCESS != APPLICATION
IDENTITY MATCH. CERTIFICATE CHAIN VALID != CORRECT APPLICATION PEER. Every
test below proves one of those claims structurally -- never by trusting a
docstring -- for `research.GuestAgentPeerAuthenticator`.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError
from research.GuestAgentMtlsTrustConfiguration import (
    GuestAgentMtlsTrustConfiguration,
    GuestAgentPeerIdentity,
    GuestAgentPeerRole,
)
from research.GuestAgentPeerAuthenticator import (
    GuestAgentAuthenticatedPeer,
    GuestAgentChannelAuthenticationResult,
    GuestAgentChannelAuthenticationStatus,
    authenticate_peer,
)
from research.GuestAgentPeerCertificateIdentity import (
    GuestAgentPeerCertificateIdentityObservation,
)

NEW_MODULE_PATHS = (
    SRC_DIR / "research" / "GuestAgentPeerAuthenticator.py",
    SRC_DIR / "research" / "GuestAgentAuthenticatedChannel.py",
)

#: socket/network/handshake/execution tokens the task forbids anywhere in
#: this milestone's new modules.
FORBIDDEN_IMPORT_MODULES = (
    "socket",
    "asyncio",
    "requests",
    "httpx",
    "urllib",
    "grpc",
    "subprocess",
)
FORBIDDEN_ATTRIBUTE_TOKENS = (
    "wrap_socket",
    "SSLSocket",
    "create_connection",
    "start_server",
    "open_connection",
)
FORBIDDEN_AUTHORITY_NAMES = (
    "KaliToolGateway",
    "ToolExecutionService",
    "ResearchKaliOperationAuthorization",
    "JsonFileResearchKaliOperationAuthorizationStore",
)

#: Adversarial URI SAN values from the milestone's adversarial-data list.
#: Each must pass `GuestAgentPeerCertificateIdentityObservation`'s own
#: bounded-string validation (no control characters, bounded length) so it
#: can actually reach `authenticate_peer`; none may ever authenticate.
ADVERSARIAL_URI_SANS = (
    "hypatia-kali-guest-agent/guest/1evil",
    "evil-hypatia-kali-guest-agent/guest/1",
    "hypatia-kali-guest-agent/host/1",
    "*",
    "*.guest",
    "ALLOW",
    "REQUIRE_APPROVAL",
    "authorized=true",
    "trusted=true",
    "verified=true",
    "../../key.pem",
    "file:///etc/passwd",
    "127.0.0.1",
    "localhost",
    "system_instruction",
    "exec",
    "run",
    "argv",
)

FAKE_FINGERPRINT = "ab" * 32
OTHER_FAKE_FINGERPRINT = "cd" * 32


def _now() -> datetime:
    """Real current time, not a fixed fictional date.

    `GuestAgentPeerCertificateIdentityObservation.currently_valid` checks
    against genuine wall-clock time; a fixed past/future date here would
    make every "currently valid" fixture silently expired or not-yet-valid.
    """
    return datetime.now(UTC)


def _observation(
    *, uri_names: tuple[str, ...], fingerprint: str | None = None, offset_days: int = 0
) -> GuestAgentPeerCertificateIdentityObservation:
    base = _now() + timedelta(days=offset_days)
    return GuestAgentPeerCertificateIdentityObservation(
        dns_names=(),
        uri_names=uri_names,
        not_before=base - timedelta(days=1),
        not_after=base + timedelta(days=1),
        fingerprint_sha256=fingerprint,
    )


def _trust(
    *,
    own_role: GuestAgentPeerRole,
    fingerprint: str | None = None,
) -> GuestAgentMtlsTrustConfiguration:
    return GuestAgentMtlsTrustConfiguration(
        own_role=own_role,
        trusted_ca_certificate_path="/trusted/ca.pem",
        own_certificate_path="/trusted/own.pem",
        own_private_key_path="/trusted/own.key",
        expected_peer_fingerprint_sha256=fingerprint,
    )


class GuestAgentChannelAuthenticationStatusTests(unittest.TestCase):
    """Requirement: the smallest honest closed status set, no broad statuses."""

    def test_status_has_exactly_three_members(self) -> None:
        self.assertEqual(
            {member.value for member in GuestAgentChannelAuthenticationStatus},
            {"authenticated", "identity_mismatch", "invalid_certificate_observation"},
        )

    def test_status_has_no_broad_connection_or_authorization_member(self) -> None:
        forbidden_names = {
            "CONNECTED",
            "READY_TO_EXECUTE",
            "AUTHORIZED",
            "AUTHORIZED_TO_EXECUTE",
            "TRUSTED",
            "VERIFIED",
        }
        actual_names = {member.name for member in GuestAgentChannelAuthenticationStatus}
        self.assertEqual(actual_names & forbidden_names, set())

    def test_status_members_are_closed_against_unknown_value_construction(self) -> None:
        with self.assertRaises(ValueError):
            GuestAgentChannelAuthenticationStatus("authorized_to_execute")


class GuestAgentAuthenticatedPeerConstructionPrivacyTests(unittest.TestCase):
    """Requirement: an authenticated peer cannot be forged by a public caller."""

    def test_direct_construction_with_wrong_token_object_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentAuthenticatedPeer(
                own_role=GuestAgentPeerRole.HOST,
                peer_identity=GuestAgentPeerIdentity.for_role(GuestAgentPeerRole.GUEST),
                _authentication_token=object(),
            )

    def test_direct_construction_with_none_token_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentAuthenticatedPeer(
                own_role=GuestAgentPeerRole.HOST,
                peer_identity=GuestAgentPeerIdentity.for_role(GuestAgentPeerRole.GUEST),
                _authentication_token=None,
            )

    def test_direct_construction_with_boolean_true_token_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentAuthenticatedPeer(
                own_role=GuestAgentPeerRole.HOST,
                peer_identity=GuestAgentPeerIdentity.for_role(GuestAgentPeerRole.GUEST),
                _authentication_token=True,
            )

    def test_direct_construction_with_string_token_is_rejected(self) -> None:
        for forged in ("authenticated", "trusted", "verified=true"):
            with self.subTest(forged=forged):
                with self.assertRaises(ResearchError):
                    GuestAgentAuthenticatedPeer(
                        own_role=GuestAgentPeerRole.HOST,
                        peer_identity=GuestAgentPeerIdentity.for_role(
                            GuestAgentPeerRole.GUEST
                        ),
                        _authentication_token=forged,
                    )

    def test_omitting_the_token_entirely_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            GuestAgentAuthenticatedPeer(  # type: ignore[call-arg]
                own_role=GuestAgentPeerRole.HOST,
                peer_identity=GuestAgentPeerIdentity.for_role(GuestAgentPeerRole.GUEST),
            )

    def test_construction_fields_are_keyword_only(self) -> None:
        with self.assertRaises(TypeError):
            GuestAgentAuthenticatedPeer(  # type: ignore[misc]
                GuestAgentPeerRole.HOST,
                GuestAgentPeerIdentity.for_role(GuestAgentPeerRole.GUEST),
                object(),
            )

    def test_authenticate_peer_is_the_only_public_source_of_a_valid_token(self) -> None:
        """The private sentinel is module-private; the only way a test (or
        any other caller) can obtain a genuinely valid authenticated peer
        is by going through `authenticate_peer` itself."""
        host_trust = _trust(own_role=GuestAgentPeerRole.HOST)
        observation = _observation(uri_names=("hypatia-kali-guest-agent/guest/1",))
        result = authenticate_peer(observation, host_trust)
        self.assertIsInstance(result.authenticated_peer, GuestAgentAuthenticatedPeer)


class GuestAgentAuthenticatedPeerFieldsTests(unittest.TestCase):
    """Requirement: the authenticated peer carries no authority of any kind."""

    def _authenticated_peer(self) -> GuestAgentAuthenticatedPeer:
        host_trust = _trust(own_role=GuestAgentPeerRole.HOST)
        observation = _observation(uri_names=("hypatia-kali-guest-agent/guest/1",))
        result = authenticate_peer(observation, host_trust)
        assert result.authenticated_peer is not None
        return result.authenticated_peer

    def test_field_set_contains_only_role_and_identity_and_token(self) -> None:
        field_names = {
            field.name for field in dataclasses.fields(GuestAgentAuthenticatedPeer)
        }
        self.assertEqual(
            field_names, {"own_role", "peer_identity", "_authentication_token"}
        )

    def test_field_set_contains_no_authority_scope_or_credential_token(self) -> None:
        forbidden_substrings = (
            "scope",
            "authoriz",
            "credential",
            "key",
            "secret",
            "permission",
            "execute",
            "capability",
        )
        field_names = {
            field.name for field in dataclasses.fields(GuestAgentAuthenticatedPeer)
        }
        for forbidden in forbidden_substrings:
            with self.subTest(token=forbidden):
                self.assertFalse(
                    any(
                        forbidden in name
                        for name in field_names
                        if name != "_authentication_token"
                    )
                )

    def test_authenticated_peer_is_frozen(self) -> None:
        peer = self._authenticated_peer()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            peer.own_role = GuestAgentPeerRole.GUEST  # type: ignore[misc]

    def test_peer_role_is_a_derived_property_not_a_settable_field(self) -> None:
        peer = self._authenticated_peer()
        self.assertEqual(peer.peer_role, GuestAgentPeerRole.GUEST)
        field_names = {
            field.name for field in dataclasses.fields(GuestAgentAuthenticatedPeer)
        }
        self.assertNotIn("peer_role", field_names)


class AuthenticatePeerRoleDirectionTests(unittest.TestCase):
    """Requirement: test both role directions; a role must never satisfy
    the wrong side's expected identity, including self-claiming reflection."""

    def test_host_side_authenticates_a_genuine_guest_identity(self) -> None:
        host_trust = _trust(own_role=GuestAgentPeerRole.HOST)
        observation = _observation(uri_names=("hypatia-kali-guest-agent/guest/1",))
        result = authenticate_peer(observation, host_trust)
        self.assertEqual(
            result.status, GuestAgentChannelAuthenticationStatus.AUTHENTICATED
        )
        assert result.authenticated_peer is not None
        self.assertEqual(result.authenticated_peer.own_role, GuestAgentPeerRole.HOST)
        self.assertEqual(result.authenticated_peer.peer_role, GuestAgentPeerRole.GUEST)

    def test_guest_side_authenticates_a_genuine_host_identity(self) -> None:
        guest_trust = _trust(own_role=GuestAgentPeerRole.GUEST)
        observation = _observation(uri_names=("hypatia-kali-guest-agent/host/1",))
        result = authenticate_peer(observation, guest_trust)
        self.assertEqual(
            result.status, GuestAgentChannelAuthenticationStatus.AUTHENTICATED
        )
        assert result.authenticated_peer is not None
        self.assertEqual(result.authenticated_peer.own_role, GuestAgentPeerRole.GUEST)
        self.assertEqual(result.authenticated_peer.peer_role, GuestAgentPeerRole.HOST)

    def test_host_identity_never_satisfies_the_host_side_expected_peer(self) -> None:
        """A HOST certificate must never satisfy the host-side expected
        peer identity (reflection/self-claim attack)."""
        host_trust = _trust(own_role=GuestAgentPeerRole.HOST)
        observation = _observation(uri_names=("hypatia-kali-guest-agent/host/1",))
        result = authenticate_peer(observation, host_trust)
        self.assertEqual(
            result.status, GuestAgentChannelAuthenticationStatus.IDENTITY_MISMATCH
        )
        self.assertIsNone(result.authenticated_peer)

    def test_guest_identity_never_satisfies_the_guest_side_expected_peer(self) -> None:
        """A GUEST certificate must never satisfy the guest-side expected
        peer identity (reflection/self-claim attack)."""
        guest_trust = _trust(own_role=GuestAgentPeerRole.GUEST)
        observation = _observation(uri_names=("hypatia-kali-guest-agent/guest/1",))
        result = authenticate_peer(observation, guest_trust)
        self.assertEqual(
            result.status, GuestAgentChannelAuthenticationStatus.IDENTITY_MISMATCH
        )
        self.assertIsNone(result.authenticated_peer)

    def test_unrelated_uri_never_authenticates_either_side(self) -> None:
        for role in (GuestAgentPeerRole.HOST, GuestAgentPeerRole.GUEST):
            with self.subTest(own_role=role):
                trust = _trust(own_role=role)
                observation = _observation(uri_names=("hypatia-unrelated-service/1",))
                result = authenticate_peer(observation, trust)
                self.assertEqual(
                    result.status,
                    GuestAgentChannelAuthenticationStatus.IDENTITY_MISMATCH,
                )


class AuthenticatePeerValidityWindowTests(unittest.TestCase):
    """Requirement: expired and not-yet-valid observations fail closed."""

    def test_expired_observation_is_an_identity_mismatch(self) -> None:
        host_trust = _trust(own_role=GuestAgentPeerRole.HOST)
        far_past = _now() - timedelta(days=400)
        observation = GuestAgentPeerCertificateIdentityObservation(
            dns_names=(),
            uri_names=("hypatia-kali-guest-agent/guest/1",),
            not_before=far_past - timedelta(days=1),
            not_after=far_past + timedelta(days=1),
            fingerprint_sha256=None,
        )
        result = authenticate_peer(observation, host_trust)
        self.assertEqual(
            result.status, GuestAgentChannelAuthenticationStatus.IDENTITY_MISMATCH
        )

    def test_not_yet_valid_observation_is_an_identity_mismatch(self) -> None:
        host_trust = _trust(own_role=GuestAgentPeerRole.HOST)
        far_future = _now() + timedelta(days=400)
        observation = GuestAgentPeerCertificateIdentityObservation(
            dns_names=(),
            uri_names=("hypatia-kali-guest-agent/guest/1",),
            not_before=far_future - timedelta(days=1),
            not_after=far_future + timedelta(days=1),
            fingerprint_sha256=None,
        )
        result = authenticate_peer(observation, host_trust)
        self.assertEqual(
            result.status, GuestAgentChannelAuthenticationStatus.IDENTITY_MISMATCH
        )


class AuthenticatePeerFingerprintTests(unittest.TestCase):
    """Requirement: optional fingerprint pinning, exact match only."""

    def test_matching_pinned_fingerprint_authenticates(self) -> None:
        host_trust = _trust(
            own_role=GuestAgentPeerRole.HOST, fingerprint=FAKE_FINGERPRINT
        )
        observation = _observation(
            uri_names=("hypatia-kali-guest-agent/guest/1",),
            fingerprint=FAKE_FINGERPRINT,
        )
        result = authenticate_peer(observation, host_trust)
        self.assertEqual(
            result.status, GuestAgentChannelAuthenticationStatus.AUTHENTICATED
        )

    def test_mismatched_pinned_fingerprint_is_an_identity_mismatch(self) -> None:
        host_trust = _trust(
            own_role=GuestAgentPeerRole.HOST, fingerprint=FAKE_FINGERPRINT
        )
        observation = _observation(
            uri_names=("hypatia-kali-guest-agent/guest/1",),
            fingerprint=OTHER_FAKE_FINGERPRINT,
        )
        result = authenticate_peer(observation, host_trust)
        self.assertEqual(
            result.status, GuestAgentChannelAuthenticationStatus.IDENTITY_MISMATCH
        )

    def test_missing_fingerprint_against_pinned_configuration_mismatches(self) -> None:
        host_trust = _trust(
            own_role=GuestAgentPeerRole.HOST, fingerprint=FAKE_FINGERPRINT
        )
        observation = _observation(
            uri_names=("hypatia-kali-guest-agent/guest/1",), fingerprint=None
        )
        result = authenticate_peer(observation, host_trust)
        self.assertEqual(
            result.status, GuestAgentChannelAuthenticationStatus.IDENTITY_MISMATCH
        )

    def test_no_pinning_configured_authenticates_on_identity_alone(self) -> None:
        host_trust = _trust(own_role=GuestAgentPeerRole.HOST, fingerprint=None)
        observation = _observation(
            uri_names=("hypatia-kali-guest-agent/guest/1",), fingerprint=None
        )
        result = authenticate_peer(observation, host_trust)
        self.assertEqual(
            result.status, GuestAgentChannelAuthenticationStatus.AUTHENTICATED
        )


class AuthenticatePeerMalformedObservationTests(unittest.TestCase):
    """Requirement: malformed observation fails closed without an exception
    leaking through this application boundary."""

    def test_none_observation_is_invalid_certificate_observation(self) -> None:
        host_trust = _trust(own_role=GuestAgentPeerRole.HOST)
        result = authenticate_peer(None, host_trust)
        self.assertEqual(
            result.status,
            GuestAgentChannelAuthenticationStatus.INVALID_CERTIFICATE_OBSERVATION,
        )
        self.assertIsNone(result.authenticated_peer)

    def test_wrong_type_observation_is_invalid_certificate_observation(self) -> None:
        host_trust = _trust(own_role=GuestAgentPeerRole.HOST)
        for garbage in (
            "not-an-observation",
            42,
            {"uri_names": ("x",)},
            object(),
            True,
        ):
            with self.subTest(garbage=garbage):
                result = authenticate_peer(garbage, host_trust)
                self.assertEqual(
                    result.status,
                    GuestAgentChannelAuthenticationStatus.INVALID_CERTIFICATE_OBSERVATION,
                )

    def test_invalid_trust_configuration_raises_rather_than_returns_status(
        self,
    ) -> None:
        observation = _observation(uri_names=("hypatia-kali-guest-agent/guest/1",))
        for garbage in (None, "not-a-config", 42, object(), True):
            with self.subTest(garbage=garbage):
                with self.assertRaises(ResearchError):
                    authenticate_peer(observation, garbage)  # type: ignore[arg-type]


class AuthenticatePeerAdversarialIdentityTests(unittest.TestCase):
    """Requirement: adversarial test data must never grant authenticated status."""

    def test_adversarial_uri_sans_never_authenticate(self) -> None:
        host_trust = _trust(own_role=GuestAgentPeerRole.HOST)
        for adversarial in ADVERSARIAL_URI_SANS:
            with self.subTest(uri=adversarial):
                observation = _observation(uri_names=(adversarial,))
                result = authenticate_peer(observation, host_trust)
                self.assertNotEqual(
                    result.status, GuestAgentChannelAuthenticationStatus.AUTHENTICATED
                )

    def test_control_characters_in_a_san_are_rejected_before_reaching_authentication(
        self,
    ) -> None:
        """The observation type's own bounded-string validation already
        fails closed on hostile SAN text; confirm that boundary still
        holds rather than assuming it."""
        with self.assertRaises(ResearchError):
            _observation(uri_names=("hypatia-kali-guest-agent/guest/1\r\nevil",))

    def test_overlong_san_is_rejected_before_reaching_authentication(self) -> None:
        with self.assertRaises(ResearchError):
            _observation(uri_names=("a" * 10_000,))

    def test_expected_identity_plus_adversarial_extra_san_still_authenticates(
        self,
    ) -> None:
        """A certificate naming both the real identity and an adversarial
        extra URI still authenticates -- exact tuple membership, not
        exclusivity -- but the adversarial entry alone never would."""
        host_trust = _trust(own_role=GuestAgentPeerRole.HOST)
        observation = _observation(
            uri_names=("hypatia-kali-guest-agent/guest/1", "evil-extra-identity")
        )
        result = authenticate_peer(observation, host_trust)
        self.assertEqual(
            result.status, GuestAgentChannelAuthenticationStatus.AUTHENTICATED
        )


class AuthenticatePeerNoCallerControlledBooleanTests(unittest.TestCase):
    """Requirement: no caller-controlled boolean can manufacture authentication."""

    def test_signature_accepts_exactly_observation_and_trust_configuration(
        self,
    ) -> None:
        parameters = inspect.signature(authenticate_peer).parameters
        self.assertEqual(set(parameters), {"observation", "trust_configuration"})

    def test_no_parameter_declares_a_bool_annotation(self) -> None:
        parameters = inspect.signature(authenticate_peer).parameters
        for parameter in parameters.values():
            with self.subTest(parameter=parameter.name):
                self.assertNotEqual(parameter.annotation, bool)

    def test_extra_unexpected_keyword_arguments_are_rejected(self) -> None:
        host_trust = _trust(own_role=GuestAgentPeerRole.HOST)
        observation = _observation(uri_names=("hypatia-kali-guest-agent/guest/1",))
        with self.assertRaises(TypeError):
            authenticate_peer(  # type: ignore[call-arg]
                observation, host_trust, verified=True
            )


class AuthenticatePeerDeterminismTests(unittest.TestCase):
    """Requirement: authentication is a pure, deterministic, stateless decision."""

    def test_repeated_calls_with_identical_input_produce_equal_results(self) -> None:
        host_trust = _trust(own_role=GuestAgentPeerRole.HOST)
        observation = _observation(uri_names=("hypatia-kali-guest-agent/guest/1",))
        first = authenticate_peer(observation, host_trust)
        second = authenticate_peer(observation, host_trust)
        self.assertEqual(first.status, second.status)
        self.assertEqual(first.reason, second.reason)
        self.assertEqual(first.authenticated_peer, second.authenticated_peer)

    def test_result_reason_strings_are_fixed_and_do_not_reflect_input(self) -> None:
        """Error/detail strings are fixed, code-owned, bounded reasons --
        never a reflection of hostile SAN text or any other input."""
        host_trust = _trust(own_role=GuestAgentPeerRole.HOST)
        hostile = "evil-" + ("x" * 150)
        observation = _observation(uri_names=(hostile,))
        result = authenticate_peer(observation, host_trust)
        self.assertNotIn(hostile, result.reason)
        self.assertLess(len(result.reason), 200)


class GuestAgentChannelAuthenticationResultInvariantTests(unittest.TestCase):
    """Requirement: status and authenticated_peer can never disagree."""

    def test_authenticated_status_without_a_peer_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentChannelAuthenticationResult(
                status=GuestAgentChannelAuthenticationStatus.AUTHENTICATED,
                reason="forged",
                authenticated_peer=None,
            )

    def test_non_authenticated_status_with_a_peer_is_rejected(self) -> None:
        host_trust = _trust(own_role=GuestAgentPeerRole.HOST)
        observation = _observation(uri_names=("hypatia-kali-guest-agent/guest/1",))
        real_result = authenticate_peer(observation, host_trust)
        with self.assertRaises(ResearchError):
            GuestAgentChannelAuthenticationResult(
                status=GuestAgentChannelAuthenticationStatus.IDENTITY_MISMATCH,
                reason="forged",
                authenticated_peer=real_result.authenticated_peer,
            )

    def test_empty_or_control_character_reason_is_rejected(self) -> None:
        for bad_reason in ("", "   ", "line\nbreak", "null\x00byte"):
            with self.subTest(reason=bad_reason):
                with self.assertRaises(ResearchError):
                    GuestAgentChannelAuthenticationResult(
                        status=GuestAgentChannelAuthenticationStatus.IDENTITY_MISMATCH,
                        reason=bad_reason,
                        authenticated_peer=None,
                    )


class NoForbiddenImportsOrAuthorityReferencesTests(unittest.TestCase):
    """Requirement: zero network/socket/handshake imports, zero references
    to the Kali execution-authority chain, in either new module -- checked
    structurally via the AST, never via a textual/docstring-fooled search.
    """

    def _parsed(self, path: Path) -> ast.Module:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_no_forbidden_network_module_is_imported(self) -> None:
        for path in NEW_MODULE_PATHS:
            tree = self._parsed(path)
            imported_roots: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported_roots.update(
                        alias.name.split(".")[0] for alias in node.names
                    )
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported_roots.add(node.module.split(".")[0])
            with self.subTest(module=path.name):
                self.assertEqual(imported_roots & set(FORBIDDEN_IMPORT_MODULES), set())

    def test_no_forbidden_socket_or_handshake_attribute_is_referenced(self) -> None:
        for path in NEW_MODULE_PATHS:
            tree = self._parsed(path)
            attribute_names: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute):
                    attribute_names.add(node.attr)
                elif isinstance(node, ast.Name):
                    attribute_names.add(node.id)
            with self.subTest(module=path.name):
                self.assertEqual(
                    attribute_names & set(FORBIDDEN_ATTRIBUTE_TOKENS), set()
                )

    def test_no_kali_execution_authority_type_is_referenced(self) -> None:
        for path in NEW_MODULE_PATHS:
            tree = self._parsed(path)
            referenced_names: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    referenced_names.add(node.id)
                elif isinstance(node, ast.Attribute):
                    referenced_names.add(node.attr)
                elif isinstance(node, ast.ImportFrom):
                    referenced_names.update(alias.name for alias in node.names)
            with self.subTest(module=path.name):
                self.assertEqual(
                    referenced_names & set(FORBIDDEN_AUTHORITY_NAMES), set()
                )

    def test_no_replay_protector_is_imported_by_the_authenticator(self) -> None:
        tree = self._parsed(SRC_DIR / "research" / "GuestAgentPeerAuthenticator.py")
        imported_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported_names.update(alias.name for alias in node.names)
        self.assertEqual(
            imported_names & {"GuestAgentReplayProtector", "GuestAgentReplayOutcome"},
            set(),
        )

    def test_authenticator_module_does_not_expose_a_replay_consume_function(
        self,
    ) -> None:
        import research.GuestAgentPeerAuthenticator as authenticator_module

        self.assertFalse(hasattr(authenticator_module, "consume_once"))
        self.assertFalse(hasattr(authenticator_module, "GuestAgentReplayOutcome"))


class ReplaySubsystemRemainsIndependentAndUnchangedTests(unittest.TestCase):
    """Requirement: replay protection remains independently required; this
    milestone must not couple it to peer authentication."""

    def test_replay_semantics_are_unchanged_by_this_milestone(self) -> None:
        import tempfile

        from research.GuestAgentProtocol import (
            GuestAgentProtocolVersion,
            GuestAgentRequest,
        )
        from research.GuestAgentReplayProtector import (
            GuestAgentReplayOutcome,
            GuestAgentReplayProtector,
        )
        from research.JsonFileGuestAgentReplayNonceStore import (
            JsonFileGuestAgentReplayNonceStore,
        )
        from research.ResearchKaliOperationPreview import ResearchKaliOperationKind

        request = GuestAgentRequest(
            protocol_version=GuestAgentProtocolVersion.V1,
            request_id="req-1",
            nonce="nonce-1",
            operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
            operation_digest="a" * 64,
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "replay.json"
            store = JsonFileGuestAgentReplayNonceStore(path)
            protector = GuestAgentReplayProtector(
                store, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
            )
            first = protector.consume_once(request)
            second = protector.consume_once(request)
        self.assertEqual(first, GuestAgentReplayOutcome.ACCEPTED)
        self.assertEqual(second, GuestAgentReplayOutcome.ALREADY_CONSUMED)

    def test_successful_peer_authentication_does_not_consume_replay_state(self) -> None:
        """Authenticating the same peer repeatedly must never, by itself,
        affect any replay nonce store -- the two mechanisms share no state."""
        host_trust = _trust(own_role=GuestAgentPeerRole.HOST)
        observation = _observation(uri_names=("hypatia-kali-guest-agent/guest/1",))
        first = authenticate_peer(observation, host_trust)
        second = authenticate_peer(observation, host_trust)
        self.assertEqual(
            first.status, GuestAgentChannelAuthenticationStatus.AUTHENTICATED
        )
        self.assertEqual(
            second.status, GuestAgentChannelAuthenticationStatus.AUTHENTICATED
        )


if __name__ == "__main__":
    unittest.main()
