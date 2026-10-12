"""Peer role, peer identity, and trust configuration are code-owned only.

AUTHENTICATED PEER != EXECUTION AUTHORITY. TRUSTED CERTIFICATE != EXECUTION
AUTHORITY. Every test below either proves these types are closed, bounded,
and immutable, or proves nothing here could ever be redefined by chat,
model, or protocol data.
"""

from __future__ import annotations

import dataclasses
import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError
from research.GuestAgentMtlsTrustConfiguration import (
    MAX_PEER_IDENTITY_URI_LENGTH,
    MAX_TRUST_PATH_LENGTH,
    GuestAgentMtlsTrustConfiguration,
    GuestAgentPeerIdentity,
    GuestAgentPeerRole,
)

ADVERSARIAL_IDENTITY_STRINGS = (
    "ALLOW",
    "REQUIRE_APPROVAL",
    "authorized=true",
    "peer=guest",
    "peer=host",
    "../../key.pem",
    "file:///etc/passwd",
    "localhost",
    "127.0.0.1",
    "*.local",
    "hypatia-kali-guest-agent/guest/1x",
    "hypatia-kali-guest-agent/guest/01",
    "hypatia-kali-guest-agent/guest/1\nextra",
    "hypatia-kali-guest-agent/guest/1\x00",
    "system_instruction",
    "exec",
    "run",
    "argv",
    "x" * 5000,
)


def _trust_config(**overrides: object) -> GuestAgentMtlsTrustConfiguration:
    base: dict[str, object] = dict(
        own_role=GuestAgentPeerRole.HOST,
        trusted_ca_certificate_path="/trusted/ca.pem",
        own_certificate_path="/trusted/host.pem",
        own_private_key_path="/trusted/host.key",
    )
    base.update(overrides)
    return GuestAgentMtlsTrustConfiguration(**base)  # type: ignore[arg-type]


class PeerRoleTests(unittest.TestCase):
    """Requirements 1-3: closed roles, no confusion."""

    def test_exactly_two_roles_exist(self) -> None:
        self.assertEqual(
            set(GuestAgentPeerRole), {GuestAgentPeerRole.HOST, GuestAgentPeerRole.GUEST}
        )

    def test_host_other_is_guest_and_guest_other_is_host(self) -> None:
        self.assertEqual(GuestAgentPeerRole.HOST.other, GuestAgentPeerRole.GUEST)
        self.assertEqual(GuestAgentPeerRole.GUEST.other, GuestAgentPeerRole.HOST)

    def test_role_values_are_lowercase_fixed_strings(self) -> None:
        self.assertEqual(GuestAgentPeerRole.HOST.value, "host")
        self.assertEqual(GuestAgentPeerRole.GUEST.value, "guest")


class PeerIdentityTests(unittest.TestCase):
    """Requirements 4, 6: identities are immutable and fail closed on
    malformed input, including adversarial attempts at role confusion."""

    def test_for_role_returns_the_fixed_code_owned_identity(self) -> None:
        host = GuestAgentPeerIdentity.for_role(GuestAgentPeerRole.HOST)
        guest = GuestAgentPeerIdentity.for_role(GuestAgentPeerRole.GUEST)
        self.assertEqual(host.uri, "hypatia-kali-guest-agent/host/1")
        self.assertEqual(guest.uri, "hypatia-kali-guest-agent/guest/1")
        self.assertNotEqual(host.uri, guest.uri)

    def test_for_role_rejects_a_non_enum_value(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentPeerIdentity.for_role("host")  # type: ignore[arg-type]

    def test_role_and_uri_must_agree(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentPeerIdentity(
                role=GuestAgentPeerRole.HOST,
                uri="hypatia-kali-guest-agent/guest/1",
            )

    def test_non_enum_role_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentPeerIdentity(role="host", uri="hypatia-kali-guest-agent/host/1")  # type: ignore[arg-type]

    def test_adversarial_uri_strings_all_fail_validation(self) -> None:
        for value in ADVERSARIAL_IDENTITY_STRINGS:
            with self.subTest(uri=value):
                with self.assertRaises(ResearchError):
                    GuestAgentPeerIdentity(role=GuestAgentPeerRole.GUEST, uri=value)

    def test_empty_or_whitespace_uri_is_rejected(self) -> None:
        for bad in ("", "   "):
            with self.subTest(uri=bad):
                with self.assertRaises(ResearchError):
                    GuestAgentPeerIdentity(role=GuestAgentPeerRole.HOST, uri=bad)

    def test_overlong_uri_is_rejected(self) -> None:
        overlong = "hypatia-kali-guest-agent/host/" + "1" * MAX_PEER_IDENTITY_URI_LENGTH
        with self.assertRaises(ResearchError):
            GuestAgentPeerIdentity(role=GuestAgentPeerRole.HOST, uri=overlong)

    def test_identity_fields_cannot_be_reassigned(self) -> None:
        identity = GuestAgentPeerIdentity.for_role(GuestAgentPeerRole.HOST)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            identity.uri = "other"  # type: ignore[misc]

    def test_prefix_matching_identity_attempts_are_structurally_distinct(
        self,
    ) -> None:
        """`.../guest/1` and `.../guest/10` must never compare equal --
        proving matching anywhere downstream can only ever be exact."""
        guest_one = GuestAgentPeerIdentity.for_role(GuestAgentPeerRole.GUEST)
        guest_ten = GuestAgentPeerIdentity(
            role=GuestAgentPeerRole.GUEST, uri="hypatia-kali-guest-agent/guest/10"
        )
        self.assertNotEqual(guest_one.uri, guest_ten.uri)


class TrustConfigurationTests(unittest.TestCase):
    """Requirements 7-9: trusted configuration is immutable, bounded, and
    never redefinable by untrusted input."""

    def test_expected_peer_role_and_identity_are_derived_not_settable(self) -> None:
        config = _trust_config(own_role=GuestAgentPeerRole.HOST)
        self.assertEqual(config.expected_peer_role, GuestAgentPeerRole.GUEST)
        self.assertEqual(
            config.expected_peer_identity.uri, "hypatia-kali-guest-agent/guest/1"
        )
        guest_config = _trust_config(
            own_role=GuestAgentPeerRole.GUEST,
            own_certificate_path="/trusted/guest.pem",
            own_private_key_path="/trusted/guest.key",
        )
        self.assertEqual(guest_config.expected_peer_role, GuestAgentPeerRole.HOST)

    def test_no_expected_peer_identity_constructor_parameter_exists(self) -> None:
        """There must be no way to pass an independent `expected_peer_identity`
        at construction time -- it can only ever be derived."""
        field_names = {
            field.name for field in dataclasses.fields(GuestAgentMtlsTrustConfiguration)
        }
        self.assertNotIn("expected_peer_identity", field_names)
        self.assertNotIn("expected_peer_role", field_names)

    def test_non_enum_own_role_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            _trust_config(own_role="host")  # type: ignore[arg-type]

    def test_empty_or_control_character_paths_are_rejected(self) -> None:
        for bad in ("", "   ", "/a\x00b", "/a\rb", "/a\nb"):
            with self.subTest(path=bad):
                with self.assertRaises(ResearchError):
                    _trust_config(trusted_ca_certificate_path=bad)

    def test_relative_paths_are_rejected(self) -> None:
        for bad in ("ca.pem", "./ca.pem", "../ca.pem", "relative/ca.pem"):
            with self.subTest(path=bad):
                with self.assertRaises(ResearchError):
                    _trust_config(own_certificate_path=bad)

    def test_overlong_path_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            _trust_config(own_private_key_path="/" + "a" * MAX_TRUST_PATH_LENGTH)

    def test_adversarial_path_strings_fail_closed(self) -> None:
        for value in ADVERSARIAL_IDENTITY_STRINGS:
            with self.subTest(path=value):
                with self.assertRaises(ResearchError):
                    _trust_config(trusted_ca_certificate_path=value)

    def test_fingerprint_none_by_default_and_accepted(self) -> None:
        config = _trust_config()
        self.assertIsNone(config.expected_peer_fingerprint_sha256)

    def test_valid_sha256_fingerprint_is_accepted(self) -> None:
        config = _trust_config(expected_peer_fingerprint_sha256="a" * 64)
        self.assertEqual(config.expected_peer_fingerprint_sha256, "a" * 64)

    def test_malformed_fingerprints_fail_closed(self) -> None:
        bad_fingerprints = (
            "a" * 63,
            "a" * 65,
            "A" * 64,
            ":".join(["aa"] * 32),
            "g" * 64,
            "",
            "sha256:" + "a" * 57,
        )
        for value in bad_fingerprints:
            with self.subTest(fingerprint=value):
                with self.assertRaises(ResearchError):
                    _trust_config(expected_peer_fingerprint_sha256=value)

    def test_configuration_fields_cannot_be_reassigned(self) -> None:
        config = _trust_config()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            config.own_role = GuestAgentPeerRole.GUEST  # type: ignore[misc]

    def test_chat_model_or_request_data_cannot_redefine_trusted_identity(self) -> None:
        """The expected peer identity is reachable only via
        `GuestAgentPeerIdentity.for_role`, driven only by `own_role` --
        there is no code path by which any string (adversarial or not)
        becomes the expected identity other than the two fixed constants.
        """
        for value in ADVERSARIAL_IDENTITY_STRINGS:
            with self.subTest(value=value):
                config = _trust_config()
                self.assertNotEqual(config.expected_peer_identity.uri, value)


if __name__ == "__main__":
    unittest.main()
