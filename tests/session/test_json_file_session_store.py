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
from session.JsonFileSessionStore import JsonFileSessionStore
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
        self.assertEqual(
            [session.session_id for session in self.store.load().sessions],
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

        self.assertEqual(
            [session.session_id for session in self.store.load().sessions],
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

    def test_unsupported_schema_raises_session_error(self) -> None:
        self._write_document(
            {"schema_version": 2, "active_session_id": "default", "sessions": []}
        )

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
