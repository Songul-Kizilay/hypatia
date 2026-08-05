"""Unit tests for immutable session domain models."""

from __future__ import annotations

import sys
import unittest
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from session.SessionRecord import SessionRecord
from session.SessionRegistrySnapshot import SessionRegistrySnapshot


class SessionModelTests(unittest.TestCase):
    def test_session_record_retains_its_fields(self) -> None:
        created_at = datetime(2026, 8, 4, 15, 0, tzinfo=UTC)

        record = SessionRecord(session_id="Work-1", created_at=created_at)

        self.assertEqual(record.session_id, "Work-1")
        self.assertEqual(record.created_at, created_at)

    def test_session_record_is_immutable(self) -> None:
        record = SessionRecord(
            session_id="default",
            created_at=datetime(2026, 8, 4, 15, 0, tzinfo=UTC),
        )

        with self.assertRaises(FrozenInstanceError):
            record.session_id = "work-1"  # type: ignore[misc]

    def test_registry_snapshot_preserves_active_session_and_order(self) -> None:
        default = SessionRecord(
            session_id="default",
            created_at=datetime(2026, 8, 4, 15, 0, tzinfo=UTC),
        )
        work = SessionRecord(
            session_id="Work-1",
            created_at=datetime(2026, 8, 4, 15, 1, tzinfo=UTC),
        )

        snapshot = SessionRegistrySnapshot(
            active_session_id="Work-1",
            sessions=(default, work),
        )

        self.assertEqual(snapshot.active_session_id, "Work-1")
        self.assertEqual(snapshot.sessions, (default, work))

    def test_registry_snapshot_sessions_are_a_tuple(self) -> None:
        snapshot = SessionRegistrySnapshot(
            active_session_id="default",
            sessions=(),
        )

        self.assertIsInstance(snapshot.sessions, tuple)
        with self.assertRaises(FrozenInstanceError):
            snapshot.sessions = ()  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
