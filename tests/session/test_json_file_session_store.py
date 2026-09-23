"""Unit tests for JSON-backed session registry snapshot persistence."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import SessionError
from session.JsonFileSessionStore import (
    MAX_SESSION_ID_CHARACTERS,
    JsonFileSessionStore,
)
from session.SessionRecord import SessionRecord
from session.SessionRegistrySnapshot import SessionRegistrySnapshot


class JsonFileSessionStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary_directory.name) / "sessions.json"
        self.store = JsonFileSessionStore(self.path)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_missing_file_loads_as_none(self) -> None:
        self.assertIsNone(self.store.load())

    def test_valid_snapshot_loads(self) -> None:
        snapshot = self._snapshot()
        self._write_document(self._document(snapshot))

        self.assertEqual(self.store.load(), snapshot)

    def test_save_and_load_round_trip_preserves_session_order(self) -> None:
        snapshot = self._snapshot(active_session_id="work-1")

        self.store.save(snapshot)

        self.assertEqual(self.store.load(), snapshot)
        loaded_snapshot = self.store.load()
        assert loaded_snapshot is not None
        self.assertEqual(
            [session.session_id for session in loaded_snapshot.sessions],
            ["default", "work-1"],
        )

    def test_case_sensitive_session_ids_are_preserved(self) -> None:
        snapshot = SessionRegistrySnapshot(
            active_session_id="Work-1",
            sessions=(
                self._record("default"),
                self._record("Work-1"),
                self._record("work-1"),
            ),
        )

        self.store.save(snapshot)

        loaded_snapshot = self.store.load()
        assert loaded_snapshot is not None
        self.assertEqual(
            [session.session_id for session in loaded_snapshot.sessions],
            ["default", "Work-1", "work-1"],
        )

    def test_duplicate_session_ids_raise_session_error(self) -> None:
        self._write_document(
            {
                "schema_version": 1,
                "active_session_id": "default",
                "sessions": [self._session_document("default")] * 2,
            }
        )

        with self.assertRaises(SessionError):
            self.store.load()

    def test_missing_default_session_raises_session_error(self) -> None:
        self._write_document(
            {
                "schema_version": 1,
                "active_session_id": "work-1",
                "sessions": [self._session_document("work-1")],
            }
        )

        with self.assertRaises(SessionError):
            self.store.load()

    def test_unknown_active_session_raises_session_error(self) -> None:
        self._write_document(
            {
                "schema_version": 1,
                "active_session_id": "unknown",
                "sessions": [self._session_document("default")],
            }
        )

        with self.assertRaises(SessionError):
            self.store.load()

    def test_empty_sessions_raise_session_error(self) -> None:
        self._write_document(
            {"schema_version": 1, "active_session_id": "default", "sessions": []}
        )

        with self.assertRaises(SessionError):
            self.store.load()

    def test_whitespace_padded_session_id_raises_session_error(self) -> None:
        self._write_document(
            {
                "schema_version": 1,
                "active_session_id": "default",
                "sessions": [
                    self._session_document("default"),
                    self._session_document(" work-1 "),
                ],
            }
        )

        with self.assertRaises(SessionError):
            self.store.load()

    def test_timezone_naive_datetime_raises_session_error(self) -> None:
        session = self._session_document("default")
        session["created_at"] = "2026-08-04T15:00:00"
        self._write_document(
            {
                "schema_version": 1,
                "active_session_id": "default",
                "sessions": [session],
            }
        )

        with self.assertRaises(SessionError):
            self.store.load()

    def test_malformed_json_raises_session_error(self) -> None:
        self.path.write_text("{invalid", encoding="utf-8")

        with self.assertRaises(SessionError):
            self.store.load()

    def test_unsupported_schema_raises_session_error_without_coercion(self) -> None:
        for schema_version in (2, True):
            with self.subTest(schema_version=schema_version):
                self._write_document(
                    {
                        "schema_version": schema_version,
                        "active_session_id": "default",
                        "sessions": [],
                    }
                )

                with self.assertRaisesRegex(SessionError, "unsupported schema"):
                    self.store.load()

    def test_oversized_file_is_rejected_before_json_decoding(self) -> None:
        self.path.write_bytes(b"{}")

        with (
            patch("session.JsonFileSessionStore.MAX_SESSION_STORE_BYTES", 1),
            patch(
                "session.JsonFileSessionStore.json.loads",
                side_effect=AssertionError("Oversized JSON must not be decoded."),
            ),
        ):
            with self.assertRaisesRegex(SessionError, "too large"):
                self.store.load()

    def test_load_uses_open_descriptor_without_preflight_stat(self) -> None:
        snapshot = self._snapshot()
        self.store.save(snapshot)

        with patch.object(
            Path,
            "stat",
            side_effect=AssertionError("Session load must not preflight file size."),
        ):
            loaded = self.store.load()

        self.assertEqual(loaded, snapshot)

    def test_session_bound_is_checked_before_parse_and_serialization(self) -> None:
        snapshot = self._snapshot()
        self._write_document(self._document(snapshot))

        with (
            patch("session.JsonFileSessionStore.MAX_SESSIONS", 1),
            patch.object(
                self.store,
                "_parse_session",
                side_effect=AssertionError("Oversized sessions must not be parsed."),
            ),
        ):
            with self.assertRaisesRegex(SessionError, "too many sessions"):
                self.store.load()

        with (
            patch("session.JsonFileSessionStore.MAX_SESSIONS", 1),
            patch.object(
                self.store,
                "_serialize_session",
                side_effect=AssertionError(
                    "Oversized sessions must not be serialized."
                ),
            ),
        ):
            with self.assertRaisesRegex(SessionError, "too many sessions"):
                self.store.save(snapshot)

    def test_session_id_bound_applies_on_load_and_before_serialization(self) -> None:
        maximum_id = "s" * MAX_SESSION_ID_CHARACTERS
        maximum_snapshot = SessionRegistrySnapshot(
            active_session_id=maximum_id,
            sessions=(self._record("default"), self._record(maximum_id)),
        )
        self.store.save(maximum_snapshot)
        self.assertEqual(self.store.load(), maximum_snapshot)

        oversized_id = "s" * (MAX_SESSION_ID_CHARACTERS + 1)
        oversized_snapshot = SessionRegistrySnapshot(
            active_session_id="default",
            sessions=(self._record("default"), self._record(oversized_id)),
        )
        self._write_document(self._document(oversized_snapshot))

        with self.assertRaisesRegex(SessionError, "session_id.*too long"):
            self.store.load()
        with patch.object(
            self.store,
            "_serialize_session",
            side_effect=AssertionError("Oversized IDs must not be serialized."),
        ):
            with self.assertRaisesRegex(SessionError, "session_id.*too long"):
                self.store.save(oversized_snapshot)

    def test_exact_count_and_utf8_byte_bounds_preserve_the_snapshot(self) -> None:
        snapshot = SessionRegistrySnapshot(
            active_session_id="çalışma-ş",
            sessions=(self._record("default"), self._record("çalışma-ş")),
        )

        with patch("session.JsonFileSessionStore.MAX_SESSIONS", 2):
            self.store.save(snapshot)
            self.assertEqual(self.store.load(), snapshot)
        exact_snapshot = self.path.read_bytes()

        with patch(
            "session.JsonFileSessionStore.MAX_SESSION_STORE_BYTES",
            len(exact_snapshot),
        ):
            self.store.save(snapshot)

        self.assertEqual(self.path.read_bytes(), exact_snapshot)
        with patch(
            "session.JsonFileSessionStore.MAX_SESSION_STORE_BYTES",
            len(exact_snapshot) - 1,
        ):
            with self.assertRaisesRegex(SessionError, "too large"):
                self.store.save(snapshot)

        self.assertEqual(self.path.read_bytes(), exact_snapshot)
        self.assertEqual(list(self.path.parent.glob(f".{self.path.name}.*.tmp")), [])

    def test_truncated_valid_prefix_on_load_fails_safely(self) -> None:
        self.store.save(self._snapshot(active_session_id="work-1"))
        original_bytes = self.path.read_bytes()

        self.path.write_bytes(original_bytes[: len(original_bytes) // 2])

        with self.assertRaises(SessionError):
            self.store.load()

    def test_save_creates_a_missing_parent_directory(self) -> None:
        nested_path = self.path.parent / "nested" / "sessions.json"

        JsonFileSessionStore(nested_path).save(self._snapshot())

        self.assertTrue(nested_path.exists())

    def test_failed_replace_preserves_existing_file_and_cleans_temporary_file(
        self,
    ) -> None:
        original_snapshot = self._snapshot()
        self.store.save(original_snapshot)
        module = import_module("session.JsonFileSessionStore")

        with patch.object(module.os, "replace", side_effect=OSError("replace failed")):
            with self.assertRaises(SessionError):
                self.store.save(self._snapshot(active_session_id="work-1"))

        self.assertEqual(self.store.load(), original_snapshot)
        self.assertEqual(list(self.path.parent.glob(f".{self.path.name}.*.tmp")), [])

    def test_invalid_snapshot_does_not_write_to_disk(self) -> None:
        original_snapshot = self._snapshot()
        self.store.save(original_snapshot)
        invalid_snapshot = SessionRegistrySnapshot(
            active_session_id="default",
            sessions=(self._record("work-1"),),
        )

        with self.assertRaises(SessionError):
            self.store.save(invalid_snapshot)

        self.assertEqual(self.store.load(), original_snapshot)

    def test_saving_a_timezone_naive_datetime_raises_session_error(self) -> None:
        snapshot = SessionRegistrySnapshot(
            active_session_id="default",
            sessions=(
                SessionRecord(
                    session_id="default",
                    created_at=datetime(2026, 8, 4, 15, 0),
                ),
            ),
        )

        with self.assertRaises(SessionError):
            self.store.save(snapshot)

        self.assertFalse(self.path.exists())

    def _write_document(self, document: dict[str, object]) -> None:
        self.path.write_text(json.dumps(document), encoding="utf-8")

    def _snapshot(
        self, *, active_session_id: str = "default"
    ) -> SessionRegistrySnapshot:
        return SessionRegistrySnapshot(
            active_session_id=active_session_id,
            sessions=(self._record("default"), self._record("work-1")),
        )

    @staticmethod
    def _record(session_id: str) -> SessionRecord:
        return SessionRecord(
            session_id=session_id,
            created_at=datetime(2026, 8, 4, 15, 0, tzinfo=UTC),
        )

    def _document(self, snapshot: SessionRegistrySnapshot) -> dict[str, object]:
        return {
            "schema_version": 1,
            "active_session_id": snapshot.active_session_id,
            "sessions": [
                self._session_document(session.session_id, session.created_at)
                for session in snapshot.sessions
            ],
        }

    @staticmethod
    def _session_document(
        session_id: str,
        created_at: datetime | None = None,
    ) -> dict[str, str]:
        return {
            "session_id": session_id,
            "created_at": (
                created_at or datetime(2026, 8, 4, 15, 0, tzinfo=UTC)
            ).isoformat(),
        }


if __name__ == "__main__":
    unittest.main()
