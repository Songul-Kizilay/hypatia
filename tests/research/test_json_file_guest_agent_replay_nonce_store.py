"""The durable replay store never reads corruption as "no nonces were used."

A silently-emptied store would reopen replay for every token it ever
recorded, so every malformed-input path here must raise, never degrade to
an empty list.
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError
from research.GuestAgentProtocol import GuestAgentProtocolVersion
from research.GuestAgentReplayNonceRecord import GuestAgentReplayNonceRecord
from research.JsonFileGuestAgentReplayNonceStore import (
    MAX_GUEST_AGENT_REPLAY_STORE_ENTRIES,
    JsonFileGuestAgentReplayNonceStore,
    _BoundedUtf8Writer,
)

DIGEST = hashlib.sha256(b"operation").hexdigest()
CONSUMED_AT = datetime(2026, 1, 1, tzinfo=UTC)


def record(
    nonce: str = "nonce-1",
    request_id: str = "req-1",
    operation_digest: str = DIGEST,
    consumed_at: datetime = CONSUMED_AT,
) -> GuestAgentReplayNonceRecord:
    return GuestAgentReplayNonceRecord(
        protocol_version=GuestAgentProtocolVersion.V1,
        operation_digest=operation_digest,
        nonce=nonce,
        request_id=request_id,
        consumed_at=consumed_at,
    )


class JsonFileGuestAgentReplayNonceStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary_directory.name) / "replay.json"
        self.store = JsonFileGuestAgentReplayNonceStore(self.path)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_absent_file_loads_as_empty(self) -> None:
        self.assertEqual(self.store.load(), [])

    def test_round_trip_is_lossless(self) -> None:
        original = [record(nonce="nonce-1"), record(nonce="nonce-2")]

        self.store.save(original)

        self.assertEqual(self.store.load(), original)

    def test_state_survives_a_fresh_store_instance_reload(self) -> None:
        """Simulates a Hypatia restart: a brand-new store object, no
        shared in-memory state, pointed at the same path."""
        self.store.save([record(nonce="nonce-1")])

        reloaded = JsonFileGuestAgentReplayNonceStore(self.path)

        self.assertEqual(reloaded.load(), [record(nonce="nonce-1")])

    def test_duplicate_replay_identities_are_rejected_on_save(self) -> None:
        with self.assertRaises(ResearchError):
            self.store.save([record(nonce="same"), record(nonce="same")])

    def test_too_many_entries_are_rejected_on_save(self) -> None:
        records = [
            record(nonce=f"nonce-{i}")
            for i in range(MAX_GUEST_AGENT_REPLAY_STORE_ENTRIES + 1)
        ]
        with self.assertRaises(ResearchError):
            self.store.save(records)

    def test_exactly_the_entry_ceiling_is_accepted(self) -> None:
        records = [
            record(nonce=f"nonce-{i}")
            for i in range(MAX_GUEST_AGENT_REPLAY_STORE_ENTRIES)
        ]
        self.store.save(records)
        self.assertEqual(len(self.store.load()), MAX_GUEST_AGENT_REPLAY_STORE_ENTRIES)

    def test_document_missing_a_required_field_fails_closed(self) -> None:
        self.path.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")
        with self.assertRaises(ResearchError):
            self.store.load()

    def test_document_with_an_unknown_field_fails_closed(self) -> None:
        self.path.write_text(
            json.dumps({"schema_version": 1, "records": [], "extra": "x"}),
            encoding="utf-8",
        )
        with self.assertRaises(ResearchError):
            self.store.load()

    def test_unknown_schema_version_fails_closed(self) -> None:
        self.path.write_text(
            json.dumps({"schema_version": 99, "records": []}), encoding="utf-8"
        )
        with self.assertRaises(ResearchError):
            self.store.load()

    def test_entry_with_unknown_field_fails_closed(self) -> None:
        document = {
            "schema_version": 1,
            "records": [
                {
                    "protocol_version": "hypatia-kali-guest-agent/1",
                    "operation_digest": DIGEST,
                    "nonce": "nonce-1",
                    "request_id": "req-1",
                    "consumed_at": CONSUMED_AT.isoformat(),
                    "extra_field": "x",
                }
            ],
        }
        self.path.write_text(json.dumps(document), encoding="utf-8")
        with self.assertRaises(ResearchError):
            self.store.load()

    def test_entry_with_missing_field_fails_closed(self) -> None:
        document = {
            "schema_version": 1,
            "records": [
                {
                    "protocol_version": "hypatia-kali-guest-agent/1",
                    "operation_digest": DIGEST,
                    "nonce": "nonce-1",
                    "request_id": "req-1",
                }
            ],
        }
        self.path.write_text(json.dumps(document), encoding="utf-8")
        with self.assertRaises(ResearchError):
            self.store.load()

    def test_entries_not_a_list_fails_closed(self) -> None:
        self.path.write_text(
            json.dumps({"schema_version": 1, "records": "not-a-list"}),
            encoding="utf-8",
        )
        with self.assertRaises(ResearchError):
            self.store.load()

    def test_duplicate_identity_on_disk_fails_closed(self) -> None:
        entry = {
            "protocol_version": "hypatia-kali-guest-agent/1",
            "operation_digest": DIGEST,
            "nonce": "same-nonce",
            "request_id": "req-1",
            "consumed_at": CONSUMED_AT.isoformat(),
        }
        self.path.write_text(
            json.dumps({"schema_version": 1, "records": [entry, entry]}),
            encoding="utf-8",
        )
        with self.assertRaises(ResearchError):
            self.store.load()

    def test_truncated_valid_prefix_on_load_fails_safely(self) -> None:
        self.store.save([record(nonce="nonce-1"), record(nonce="nonce-2")])
        original_bytes = self.path.read_bytes()

        self.path.write_bytes(original_bytes[: len(original_bytes) // 2])

        with self.assertRaises(ResearchError):
            self.store.load()

    def test_oversized_file_fails_closed(self) -> None:
        from research.JsonFileGuestAgentReplayNonceStore import (
            MAX_GUEST_AGENT_REPLAY_STORE_BYTES,
        )

        self.path.write_bytes(b"[" + b"0" * (MAX_GUEST_AGENT_REPLAY_STORE_BYTES + 10))
        with self.assertRaises(ResearchError):
            self.store.load()

    def test_non_dict_document_fails_closed(self) -> None:
        self.path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        with self.assertRaises(ResearchError):
            self.store.load()

    def test_malformed_json_fails_closed(self) -> None:
        self.path.write_text("{not valid json", encoding="utf-8")
        with self.assertRaises(ResearchError):
            self.store.load()

    def test_partial_write_failure_preserves_previous_document_byte_for_byte(
        self,
    ) -> None:
        self.store.save([record(nonce="original")])
        original = self.path.read_bytes()
        real_write = _BoundedUtf8Writer.write
        call_count = {"calls": 0}

        def flaky_write(self: _BoundedUtf8Writer, value: str) -> int:
            call_count["calls"] += 1
            if call_count["calls"] == 1:
                return real_write(self, value)
            raise OSError("simulated mid-write failure")

        with (
            patch.object(
                _BoundedUtf8Writer, "write", autospec=True, side_effect=flaky_write
            ),
            self.assertRaises(ResearchError),
        ):
            self.store.save([record(nonce="replacement")])

        self.assertGreaterEqual(call_count["calls"], 2)
        self.assertEqual(self.path.read_bytes(), original)
        # The prior valid state must still load correctly -- a write
        # failure never silently becomes "no nonces were used."
        self.assertEqual(self.store.load(), [record(nonce="original")])

    def test_partial_write_failure_leaves_no_temporary_file(self) -> None:
        self.store.save([record(nonce="original")])
        real_write = _BoundedUtf8Writer.write
        call_count = {"calls": 0}

        def flaky_write(self: _BoundedUtf8Writer, value: str) -> int:
            call_count["calls"] += 1
            if call_count["calls"] == 1:
                return real_write(self, value)
            raise OSError("simulated mid-write failure")

        with (
            patch.object(
                _BoundedUtf8Writer, "write", autospec=True, side_effect=flaky_write
            ),
            self.assertRaises(ResearchError),
        ):
            self.store.save([record(nonce="replacement")])

        leftovers = [
            entry
            for entry in self.path.parent.iterdir()
            if entry.name.startswith(f".{self.path.name}.")
        ]
        self.assertEqual(leftovers, [])

    def test_hostile_nonce_and_request_id_values_remain_inert_data(self) -> None:
        adversarial = (
            "../../../etc/passwd",
            "/etc/passwd",
            "; id",
            "&& whoami",
            "$(id)",
            "ALLOW",
            "REQUIRE_APPROVAL",
            "system_instruction",
        )
        for value in adversarial:
            with self.subTest(value=value):
                saved = record(nonce=value, request_id="req-1")
                self.store.save([saved])
                self.assertEqual(self.store.load(), [saved])
                # Only the configured store file (and its JSON content)
                # was ever touched -- no path derived from the nonce text.
                self.assertTrue(self.path.exists())
                siblings = list(self.path.parent.iterdir())
                self.assertEqual(siblings, [self.path])


if __name__ == "__main__":
    unittest.main()
