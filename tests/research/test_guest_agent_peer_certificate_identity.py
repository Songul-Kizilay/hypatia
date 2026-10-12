"""Peer certificate identity observation and matching never manufacture trust.

TRUSTED CERTIFICATE != EXECUTION AUTHORITY. PEER IDENTITY MATCH != EXECUTION
AUTHORITY. Every test below either proves `parse_peer_certificate_identity`
fails closed on anything that is not exactly the real `getpeercert()` shape,
or proves `peer_identity_matches` is exact-match-only and creates/consumes
no authorization of any kind.
"""

from __future__ import annotations

import dataclasses
import hashlib
import sys
import unittest
from datetime import UTC, datetime
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
from research.GuestAgentPeerCertificateIdentity import (
    GuestAgentPeerCertificateIdentityObservation,
    parse_peer_certificate_identity,
    peer_identity_matches,
)

NOT_BEFORE = "Jan  1 00:00:00 2020 GMT"
NOT_AFTER = "Jan  1 00:00:00 2099 GMT"
EXPIRED_NOT_AFTER = "Jan  1 00:00:00 2021 GMT"
NOT_YET_VALID_NOT_BEFORE = "Jan  1 00:00:00 2099 GMT"
NOT_YET_VALID_NOT_AFTER = "Jan  1 00:00:00 2150 GMT"

ADVERSARIAL_SAN_VALUES = (
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
    "system_instruction",
    "exec",
    "run",
    "argv",
)


def _guest_cert_dict(
    uri_names: tuple[str, ...] = ("hypatia-kali-guest-agent/guest/1",),
    dns_names: tuple[str, ...] = (),
    not_before: str = NOT_BEFORE,
    not_after: str = NOT_AFTER,
) -> dict[str, object]:
    san: list[tuple[str, str]] = [("URI", uri) for uri in uri_names]
    san.extend(("DNS", name) for name in dns_names)
    return {
        "subject": (),
        "issuer": (),
        "version": 3,
        "notBefore": not_before,
        "notAfter": not_after,
        "subjectAltName": tuple(san),
    }


def _observation(**overrides: object) -> GuestAgentPeerCertificateIdentityObservation:
    base: dict[str, object] = dict(
        dns_names=(),
        uri_names=("hypatia-kali-guest-agent/guest/1",),
        not_before=datetime(2020, 1, 1, tzinfo=UTC),
        not_after=datetime(2099, 1, 1, tzinfo=UTC),
        fingerprint_sha256=None,
    )
    base.update(overrides)
    return GuestAgentPeerCertificateIdentityObservation(**base)  # type: ignore[arg-type]


class ObservationValidationTests(unittest.TestCase):
    def test_too_many_san_entries_fail_closed(self) -> None:
        with self.assertRaises(ResearchError):
            _observation(uri_names=tuple(f"uri-{i}" for i in range(21)))

    def test_control_character_san_entry_fails_closed(self) -> None:
        for bad in ("a\x00b", "a\rb", "a\nb"):
            with self.subTest(value=bad):
                with self.assertRaises(ResearchError):
                    _observation(uri_names=(bad,))

    def test_empty_san_entry_fails_closed(self) -> None:
        with self.assertRaises(ResearchError):
            _observation(uri_names=("",))

    def test_validity_end_before_start_fails_closed(self) -> None:
        with self.assertRaises(ResearchError):
            _observation(
                not_before=datetime(2099, 1, 1, tzinfo=UTC),
                not_after=datetime(2020, 1, 1, tzinfo=UTC),
            )

    def test_naive_validity_timestamps_fail_closed(self) -> None:
        with self.assertRaises(ResearchError):
            _observation(not_before=datetime(2020, 1, 1))

    def test_malformed_fingerprint_fails_closed(self) -> None:
        for bad in ("short", "A" * 64, "g" * 64):
            with self.subTest(fingerprint=bad):
                with self.assertRaises(ResearchError):
                    _observation(fingerprint_sha256=bad)

    def test_non_tuple_names_fail_closed(self) -> None:
        with self.assertRaises(ResearchError):
            _observation(uri_names=["not", "a", "tuple"])  # type: ignore[arg-type]

    def test_fields_cannot_be_reassigned(self) -> None:
        observation = _observation()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            observation.uri_names = ("other",)  # type: ignore[misc]

    def test_currently_valid_reflects_the_real_window(self) -> None:
        valid = _observation()
        self.assertTrue(valid.currently_valid)
        expired = _observation(
            not_before=datetime(2020, 1, 1, tzinfo=UTC),
            not_after=datetime(2021, 1, 1, tzinfo=UTC),
        )
        self.assertFalse(expired.currently_valid)
        not_yet_valid = _observation(
            not_before=datetime(2099, 1, 1, tzinfo=UTC),
            not_after=datetime(2150, 1, 1, tzinfo=UTC),
        )
        self.assertFalse(not_yet_valid.currently_valid)


class ParseCertificateIdentityTests(unittest.TestCase):
    """Fail-closed parsing of the real `getpeercert()` dict shape."""

    def test_valid_certificate_dict_parses_cleanly(self) -> None:
        observation = parse_peer_certificate_identity(_guest_cert_dict())
        self.assertEqual(observation.uri_names, ("hypatia-kali-guest-agent/guest/1",))
        self.assertEqual(observation.dns_names, ())
        self.assertIsNone(observation.fingerprint_sha256)

    def test_der_bytes_produce_a_real_sha256_fingerprint(self) -> None:
        der = b"fake-der-bytes-for-testing"
        observation = parse_peer_certificate_identity(_guest_cert_dict(), der_bytes=der)
        self.assertEqual(
            observation.fingerprint_sha256, hashlib.sha256(der).hexdigest()
        )

    def test_no_der_bytes_means_no_fingerprint(self) -> None:
        observation = parse_peer_certificate_identity(_guest_cert_dict())
        self.assertIsNone(observation.fingerprint_sha256)

    def test_missing_subject_alt_name_defaults_to_empty(self) -> None:
        cert_dict = _guest_cert_dict()
        del cert_dict["subjectAltName"]
        observation = parse_peer_certificate_identity(cert_dict)
        self.assertEqual(observation.uri_names, ())
        self.assertEqual(observation.dns_names, ())

    def test_non_mapping_input_fails_closed(self) -> None:
        for bad in (None, "not a dict", [], 42):
            with self.subTest(value=bad):
                with self.assertRaises(ResearchError):
                    parse_peer_certificate_identity(bad)  # type: ignore[arg-type]

    def test_non_tuple_subject_alt_name_fails_closed(self) -> None:
        cert_dict = _guest_cert_dict()
        cert_dict["subjectAltName"] = ["not", "a", "tuple"]
        with self.assertRaises(ResearchError):
            parse_peer_certificate_identity(cert_dict)

    def test_malformed_san_entry_shape_fails_closed(self) -> None:
        for bad_entries in (
            (("URI",),),
            (("URI", "value", "extra"),),
            ((1, "value"),),
            (("URI", 1),),
        ):
            with self.subTest(entries=bad_entries):
                cert_dict = _guest_cert_dict()
                cert_dict["subjectAltName"] = bad_entries
                with self.assertRaises(ResearchError):
                    parse_peer_certificate_identity(cert_dict)

    def test_malformed_validity_date_fails_closed(self) -> None:
        for bad in ("not a date", "", "2026-01-01", None, 12345):
            with self.subTest(value=bad):
                cert_dict = _guest_cert_dict()
                cert_dict["notBefore"] = bad
                with self.assertRaises(ResearchError):
                    parse_peer_certificate_identity(cert_dict)

    def test_other_san_kinds_are_ignored_not_misclassified(self) -> None:
        cert_dict = _guest_cert_dict()
        cert_dict["subjectAltName"] = (
            ("IP Address", "10.0.0.5"),
            ("email", "nobody@example.com"),
            ("URI", "hypatia-kali-guest-agent/guest/1"),
        )
        observation = parse_peer_certificate_identity(cert_dict)
        self.assertEqual(observation.uri_names, ("hypatia-kali-guest-agent/guest/1",))
        self.assertEqual(observation.dns_names, ())

    def test_adversarial_san_values_parse_as_inert_data(self) -> None:
        for value in ADVERSARIAL_SAN_VALUES:
            with self.subTest(value=value):
                cert_dict = _guest_cert_dict(uri_names=(value,))
                observation = parse_peer_certificate_identity(cert_dict)
                self.assertEqual(observation.uri_names, (value,))
                # Inert: never matches the real expected guest identity.
                self.assertFalse(
                    peer_identity_matches(
                        observation,
                        GuestAgentPeerIdentity.for_role(GuestAgentPeerRole.GUEST),
                    )
                )


class PeerIdentityMatchesTests(unittest.TestCase):
    """Requirements 12-14, 28-33: exact matching only; creates/consumes no
    authorization; defense-in-depth validity check."""

    def test_exact_match_succeeds(self) -> None:
        observation = parse_peer_certificate_identity(_guest_cert_dict())
        self.assertTrue(
            peer_identity_matches(
                observation, GuestAgentPeerIdentity.for_role(GuestAgentPeerRole.GUEST)
            )
        )

    def test_wrong_role_fails(self) -> None:
        observation = parse_peer_certificate_identity(_guest_cert_dict())
        self.assertFalse(
            peer_identity_matches(
                observation, GuestAgentPeerIdentity.for_role(GuestAgentPeerRole.HOST)
            )
        )

    def test_substring_or_superstring_identity_never_matches(self) -> None:
        observation = parse_peer_certificate_identity(
            _guest_cert_dict(uri_names=("hypatia-kali-guest-agent/guest/1evil",))
        )
        self.assertFalse(
            peer_identity_matches(
                observation, GuestAgentPeerIdentity.for_role(GuestAgentPeerRole.GUEST)
            )
        )

    def test_prefix_of_the_real_identity_never_matches(self) -> None:
        observation = parse_peer_certificate_identity(
            _guest_cert_dict(uri_names=("hypatia-kali-guest-agent/guest",))
        )
        self.assertFalse(
            peer_identity_matches(
                observation, GuestAgentPeerIdentity.for_role(GuestAgentPeerRole.GUEST)
            )
        )

    def test_expired_certificate_fails_even_with_correct_identity(self) -> None:
        observation = parse_peer_certificate_identity(
            _guest_cert_dict(not_before=NOT_BEFORE, not_after=EXPIRED_NOT_AFTER)
        )
        self.assertFalse(
            peer_identity_matches(
                observation, GuestAgentPeerIdentity.for_role(GuestAgentPeerRole.GUEST)
            )
        )

    def test_not_yet_valid_certificate_fails_even_with_correct_identity(self) -> None:
        observation = parse_peer_certificate_identity(
            _guest_cert_dict(
                not_before=NOT_YET_VALID_NOT_BEFORE, not_after=NOT_YET_VALID_NOT_AFTER
            )
        )
        self.assertFalse(
            peer_identity_matches(
                observation, GuestAgentPeerIdentity.for_role(GuestAgentPeerRole.GUEST)
            )
        )

    def test_pinned_fingerprint_matching_succeeds(self) -> None:
        der = b"fake-der-bytes"
        fingerprint = hashlib.sha256(der).hexdigest()
        observation = parse_peer_certificate_identity(_guest_cert_dict(), der_bytes=der)
        trust_config = GuestAgentMtlsTrustConfiguration(
            own_role=GuestAgentPeerRole.HOST,
            trusted_ca_certificate_path="/trusted/ca.pem",
            own_certificate_path="/trusted/host.pem",
            own_private_key_path="/trusted/host.key",
            expected_peer_fingerprint_sha256=fingerprint,
        )
        self.assertTrue(
            peer_identity_matches(
                observation,
                GuestAgentPeerIdentity.for_role(GuestAgentPeerRole.GUEST),
                trust_config,
            )
        )

    def test_pinned_fingerprint_mismatch_fails_even_with_correct_identity(
        self,
    ) -> None:
        observation = parse_peer_certificate_identity(
            _guest_cert_dict(), der_bytes=b"real-cert-bytes"
        )
        trust_config = GuestAgentMtlsTrustConfiguration(
            own_role=GuestAgentPeerRole.HOST,
            trusted_ca_certificate_path="/trusted/ca.pem",
            own_certificate_path="/trusted/host.pem",
            own_private_key_path="/trusted/host.key",
            expected_peer_fingerprint_sha256="f" * 64,
        )
        self.assertFalse(
            peer_identity_matches(
                observation,
                GuestAgentPeerIdentity.for_role(GuestAgentPeerRole.GUEST),
                trust_config,
            )
        )

    def test_no_pinned_fingerprint_means_fingerprint_is_not_checked(self) -> None:
        observation = parse_peer_certificate_identity(_guest_cert_dict())
        self.assertIsNone(observation.fingerprint_sha256)
        self.assertTrue(
            peer_identity_matches(
                observation, GuestAgentPeerIdentity.for_role(GuestAgentPeerRole.GUEST)
            )
        )

    def test_matches_requires_a_bounded_observation(self) -> None:
        with self.assertRaises(ResearchError):
            peer_identity_matches(
                "not an observation",  # type: ignore[arg-type]
                GuestAgentPeerIdentity.for_role(GuestAgentPeerRole.GUEST),
            )

    def test_matches_requires_a_bounded_expected_identity(self) -> None:
        observation = parse_peer_certificate_identity(_guest_cert_dict())
        with self.assertRaises(ResearchError):
            peer_identity_matches(observation, "guest")  # type: ignore[arg-type]

    def test_mismatched_expected_identity_and_trust_configuration_fails_closed(
        self,
    ) -> None:
        """A `trust_configuration` built for the HOST role (expecting the
        GUEST peer) paired with an `expected` identity for the HOST role
        must raise -- the two disagree about which role is expected, and
        this function must never silently pick one over the other."""
        observation = parse_peer_certificate_identity(_guest_cert_dict())
        host_trust_config = GuestAgentMtlsTrustConfiguration(
            own_role=GuestAgentPeerRole.HOST,
            trusted_ca_certificate_path="/trusted/ca.pem",
            own_certificate_path="/trusted/host.pem",
            own_private_key_path="/trusted/host.key",
        )
        mismatched_expected = GuestAgentPeerIdentity.for_role(GuestAgentPeerRole.HOST)
        with self.assertRaises(ResearchError):
            peer_identity_matches(observation, mismatched_expected, host_trust_config)

    def test_consistent_expected_identity_and_trust_configuration_succeeds(
        self,
    ) -> None:
        observation = parse_peer_certificate_identity(_guest_cert_dict())
        host_trust_config = GuestAgentMtlsTrustConfiguration(
            own_role=GuestAgentPeerRole.HOST,
            trusted_ca_certificate_path="/trusted/ca.pem",
            own_certificate_path="/trusted/host.pem",
            own_private_key_path="/trusted/host.key",
        )
        self.assertTrue(
            peer_identity_matches(
                observation, host_trust_config.expected_peer_identity, host_trust_config
            )
        )

    def test_matching_returns_only_a_bool_never_an_authorization_object(
        self,
    ) -> None:
        observation = parse_peer_certificate_identity(_guest_cert_dict())
        result = peer_identity_matches(
            observation, GuestAgentPeerIdentity.for_role(GuestAgentPeerRole.GUEST)
        )
        self.assertIsInstance(result, bool)

    def test_no_kali_authorization_module_is_imported_by_this_module(self) -> None:
        import ast

        path = SRC_DIR / "research" / "GuestAgentPeerCertificateIdentity.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported_names.update(alias.name for alias in node.names)
        self.assertNotIn("ResearchKaliOperationAuthorization", imported_names)
        self.assertNotIn("ResearchKaliOperationAuthorizationStore", imported_names)


if __name__ == "__main__":
    unittest.main()
