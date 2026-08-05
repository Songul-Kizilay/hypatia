"""Structural tests for the SessionStore persistence contract."""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from session.SessionRecord import SessionRecord
from session.SessionRegistrySnapshot import SessionRegistrySnapshot
from session.SessionStore import SessionStore


class FakeSessionStore:
    """Minimal in-memory implementation used to exercise the protocol."""

    def __init__(self) -> None:
        self.snapshot: SessionRegistrySnapshot | None = None

    def load(self) -> SessionRegistrySnapshot | None:
        if self.snapshot is None:
            return None

        return SessionRegistrySnapshot(
            active_session_id=self.snapshot.active_session_id,
            sessions=tuple(self.snapshot.sessions),
        )

    def save(self, snapshot: SessionRegistrySnapshot) -> None:
        self.snapshot = SessionRegistrySnapshot(
            active_session_id=snapshot.active_session_id,
            sessions=tuple(snapshot.sessions),
        )


class SessionStoreTests(unittest.TestCase):
    def test_missing_snapshot_can_be_loaded(self) -> None:
        store: SessionStore = FakeSessionStore()

        self.assertIsNone(store.load())

    def test_saved_snapshot_can_be_loaded(self) -> None:
        store: SessionStore = FakeSessionStore()
        snapshot = SessionRegistrySnapshot(
            active_session_id="default",
            sessions=(
                SessionRecord(
                    session_id="default",
                    created_at=datetime(2026, 8, 4, 15, 0, tzinfo=UTC),
                ),
            ),
        )

        store.save(snapshot)

        self.assertEqual(store.load(), snapshot)

    def test_store_does_not_retain_the_caller_snapshot(self) -> None:
        store = FakeSessionStore()
        snapshot = SessionRegistrySnapshot(
            active_session_id="default",
            sessions=(),
        )

        store.save(snapshot)

        self.assertIsNot(store.snapshot, snapshot)
        self.assertIsNot(store.load(), store.snapshot)


if __name__ == "__main__":
    unittest.main()
