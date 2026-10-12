"""A replay record states only that one identity was spent; it grants nothing.

REPLAY ACCEPTED != AUTHORITY TO EXECUTE. REPLAY REJECTED != AUTHORITY
DECISION. Every test below either proves the record's own field-level
guards, or proves the `(protocol_version, operation_digest, nonce)` replay
identity is exactly what two unrelated requests cannot accidentally alias
into.
"""

from __future__ import annotations

import hashlib
import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError
from research.GuestAgentProtocol import GuestAgentProtocolVersion
from research.GuestAgentReplayNonceRecord import GuestAgentReplayNonceRecord

DIGEST_A = hashlib.sha256(b"operation-a").hexdigest()
DIGEST_B = hashlib.sha256(b"operation-b").hexdigest()
CONSUMED_AT = datetime(2026, 1, 1, tzinfo=UTC)


def record(**overrides: object) -> GuestAgentReplayNonceRecord:
    base: dict[str, object] = dict(
        protocol_version=GuestAgentProtocolVersion.V1,
        operation_digest=DIGEST_A,
        nonce="nonce-1",
        request_id="req-1",
        consumed_at=CONSUMED_AT,
    )
    base.update(overrides)
    return GuestAgentReplayNonceRecord(**base)  # type: ignore[arg-type]


class FieldValidationTests(unittest.TestCase):
    def test_non_enum_protocol_version_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            record(protocol_version="hypatia-kali-guest-agent/1")  # type: ignore[arg-type]

    def test_malformed_operation_digest_is_rejected(self) -> None:
        for bad in ("not-a-digest", "", "x" * 63, DIGEST_A.upper()):
            with self.subTest(digest=bad):
                with self.assertRaises(ResearchError):
                    record(operation_digest=bad)

    def test_empty_or_control_character_nonce_is_rejected(self) -> None:
        for bad in ("", "a\x00b", "a\rb", "a\nb"):
            with self.subTest(nonce=bad):
                with self.assertRaises(ResearchError):
                    record(nonce=bad)

    def test_empty_or_control_character_request_id_is_rejected(self) -> None:
        for bad in ("", "a\x00b", "a\nb"):
            with self.subTest(request_id=bad):
                with self.assertRaises(ResearchError):
                    record(request_id=bad)

    def test_overlong_nonce_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            record(nonce="x" * 201)

    def test_overlong_request_id_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            record(request_id="x" * 201)

    def test_naive_consumed_at_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            record(consumed_at=datetime(2026, 1, 1))

    def test_non_utc_consumed_at_is_rejected(self) -> None:
        from datetime import timezone

        with self.assertRaises(ResearchError):
            record(
                consumed_at=datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=2)))
            )

    def test_a_valid_record_constructs_cleanly(self) -> None:
        value = record()
        self.assertEqual(value.operation_digest, DIGEST_A)


class ReplayIdentityTests(unittest.TestCase):
    """The identity is the (protocol_version, operation_digest, nonce)
    triple -- not nonce alone -- so two unrelated requests sharing a nonce
    do not accidentally alias."""

    def test_identity_is_the_three_field_tuple(self) -> None:
        value = record()
        self.assertEqual(
            value.replay_identity,
            (GuestAgentProtocolVersion.V1.value, DIGEST_A, "nonce-1"),
        )

    def test_same_nonce_different_operation_digest_is_a_different_identity(
        self,
    ) -> None:
        first = record(nonce="shared-nonce", operation_digest=DIGEST_A)
        second = record(nonce="shared-nonce", operation_digest=DIGEST_B)
        self.assertNotEqual(first.replay_identity, second.replay_identity)

    def test_same_operation_digest_different_nonce_is_a_different_identity(
        self,
    ) -> None:
        first = record(nonce="nonce-a", operation_digest=DIGEST_A)
        second = record(nonce="nonce-b", operation_digest=DIGEST_A)
        self.assertNotEqual(first.replay_identity, second.replay_identity)

    def test_identical_fields_produce_an_equal_identity(self) -> None:
        first = record()
        second = record()
        self.assertEqual(first.replay_identity, second.replay_identity)


class ImmutabilityTests(unittest.TestCase):
    def test_fields_cannot_be_reassigned(self) -> None:
        import dataclasses

        value = record()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            value.nonce = "other"  # type: ignore[misc]


class NoAuthorityTests(unittest.TestCase):
    def test_record_exposes_no_execution_or_mutation_method(self) -> None:
        forbidden = (
            "execute",
            "invoke",
            "run",
            "dispatch",
            "authorize",
            "authorise",
            "grant",
            "consume",
            "register",
            "mutate",
        )
        for name in forbidden:
            with self.subTest(method=name):
                self.assertFalse(hasattr(GuestAgentReplayNonceRecord, name))


if __name__ == "__main__":
    unittest.main()
