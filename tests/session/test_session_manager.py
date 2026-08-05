"""Unit tests for transactional session registry management."""

from __future__ import annotations

import re
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import SessionError
from eventbus.EventBus import EventBus
from session.SessionManager import SessionManager
from session.SessionRecord import SessionRecord
from session.SessionRegistrySnapshot import SessionRegistrySnapshot


class RecordingSessionStore:
    """In-memory snapshot store that records persistence calls."""

    def __init__(self, snapshot: SessionRegistrySnapshot | None = None) -> None:
        self.snapshot = self._copy(snapshot)
        self.saved_snapshots: list[SessionRegistrySnapshot] = []
        self.save_completed = False

    def load(self) -> SessionRegistrySnapshot | None:
        return self._copy(self.snapshot)

    def save(self, snapshot: SessionRegistrySnapshot) -> None:
        self.save_completed = True
        copied_snapshot = self._copy(snapshot)
        self.saved_snapshots.append(copied_snapshot)
        self.snapshot = copied_snapshot

    @staticmethod
    def _copy(
        snapshot: SessionRegistrySnapshot | None,
    ) -> SessionRegistrySnapshot | None:
        if snapshot is None:
            return None
        return SessionRegistrySnapshot(
            active_session_id=snapshot.active_session_id,
            sessions=tuple(
                SessionRecord(
                    session_id=session.session_id,
                    created_at=session.created_at,
                )
                for session in snapshot.sessions
            ),
        )


class FailingSessionStore(RecordingSessionStore):
    """Persistence fake that can fail independently during reads and writes."""

    def __init__(self, snapshot: SessionRegistrySnapshot | None = None) -> None:
        super().__init__(snapshot)
        self.fail_load = False
        self.fail_save = False

    def load(self) -> SessionRegistrySnapshot | None:
        if self.fail_load:
            raise SessionError("Session load failed.")
        return super().load()

    def save(self, snapshot: SessionRegistrySnapshot) -> None:
        if self.fail_save:
            raise SessionError("Session save failed.")
        super().save(snapshot)


class SessionManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.event_bus = EventBus()
        self.manager = SessionManager(self.event_bus)

    def test_load_missing_snapshot_creates_and_persists_default_registry(self) -> None:
        store = RecordingSessionStore()
        manager = SessionManager(store=store)

        manager.load()

        self.assertEqual(manager.get_active().session_id, "default")
        self.assertEqual(
            [session.session_id for session in manager.list()], ["default"]
        )
        self.assertEqual(store.snapshot.active_session_id, "default")

    def test_load_replaces_the_registry_with_a_valid_snapshot(self) -> None:
        stored_snapshot = self._snapshot(active_session_id="work-1")
        manager = SessionManager(store=RecordingSessionStore(stored_snapshot))

        manager.load()

        self.assertEqual(manager.get_active().session_id, "work-1")
        self.assertEqual(
            [session.session_id for session in manager.list()],
            ["default", "work-1"],
        )

    def test_load_failure_preserves_existing_registry(self) -> None:
        store = FailingSessionStore()
        manager = SessionManager(store=store)
        manager.create("work-1")
        before = manager.list()
        store.fail_load = True

        with self.assertRaises(SessionError):
            manager.load()

        self.assertEqual(manager.list(), before)
        self.assertEqual(manager.get_active().session_id, "default")

    def test_create_normalizes_session_id(self) -> None:
        result = self.manager.create("  Work-1  ")

        self.assertTrue(result.created)
        self.assertEqual(result.session.session_id, "Work-1")

    def test_case_sensitive_sessions_are_distinct(self) -> None:
        self.manager.create("Work-1")
        self.manager.create("work-1")

        self.assertEqual(
            [session.session_id for session in self.manager.list()],
            ["default", "Work-1", "work-1"],
        )

    def test_duplicate_create_is_an_idempotent_no_op(self) -> None:
        store = RecordingSessionStore()
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))
        manager_with_events = SessionManager(self.event_bus, store)
        manager_with_events.load()
        manager_with_events.create("work-1")
        saves_before_duplicate = len(store.saved_snapshots)
        events.clear()

        result = manager_with_events.create("work-1")

        self.assertFalse(result.created)
        self.assertEqual(len(store.saved_snapshots), saves_before_duplicate)
        self.assertEqual(events, [])

    def test_create_save_failure_rolls_back_registry_and_events(self) -> None:
        store = FailingSessionStore()
        store.fail_save = True
        manager = SessionManager(self.event_bus, store)
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))

        with self.assertRaises(SessionError):
            manager.create("work-1")

        self.assertEqual(
            [session.session_id for session in manager.list()], ["default"]
        )
        self.assertEqual(events, [])

    def test_create_event_is_published_after_persistence(self) -> None:
        store = RecordingSessionStore()
        manager = SessionManager(self.event_bus, store)
        persisted_at_event: list[bool] = []
        self.event_bus.subscribe(
            "session.created",
            lambda event: persisted_at_event.append(store.save_completed),
        )

        manager.create("work-1")

        self.assertEqual(persisted_at_event, [True])

    def test_set_active_rejects_unknown_session(self) -> None:
        with self.assertRaisesRegex(SessionError, "Unknown session: work-1"):
            self.manager.set_active("work-1")

    def test_set_active_same_session_is_a_no_op(self) -> None:
        store = RecordingSessionStore()
        manager = SessionManager(self.event_bus, store)
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))

        result = manager.set_active("default")

        self.assertEqual(result.session_id, "default")
        self.assertEqual(store.saved_snapshots, [])
        self.assertEqual(events, [])

    def test_set_active_save_failure_preserves_active_session_and_events(self) -> None:
        store = FailingSessionStore()
        manager = SessionManager(self.event_bus, store)
        manager.create("work-1")
        store.fail_save = True
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))

        with self.assertRaises(SessionError):
            manager.set_active("work-1")

        self.assertEqual(manager.get_active().session_id, "default")
        self.assertEqual(events, [])

    def test_set_active_event_is_published_after_persistence(self) -> None:
        store = RecordingSessionStore()
        manager = SessionManager(self.event_bus, store)
        manager.create("work-1")
        store.save_completed = False
        persisted_at_event: list[bool] = []
        self.event_bus.subscribe(
            "session.activated",
            lambda event: persisted_at_event.append(store.save_completed),
        )

        manager.set_active("work-1")

        self.assertEqual(persisted_at_event, [True])

    def test_list_preserves_creation_order_and_get_active_returns_registered_record(
        self,
    ) -> None:
        self.manager.create("work-1")
        self.manager.create("work-2")
        active = self.manager.set_active("work-1")

        self.assertEqual(
            [session.session_id for session in self.manager.list()],
            ["default", "work-1", "work-2"],
        )
        self.assertEqual(self.manager.get_active(), active)

    def test_store_receives_a_distinct_snapshot_object(self) -> None:
        store = RecordingSessionStore()
        manager = SessionManager(store=store)

        result = manager.create("work-1")

        self.assertIsNot(store.snapshot.sessions[-1], result.session)
        self.assertEqual(store.snapshot.sessions[-1], result.session)

    def test_invalid_session_ids_raise_controlled_errors(self) -> None:
        for session_id, message in ((123, "string"), ("   ", "empty")):
            with self.subTest(session_id=session_id):
                with self.assertRaisesRegex(SessionError, message):
                    self.manager.create(session_id)

        self.assertEqual(
            [session.session_id for session in self.manager.list()], ["default"]
        )

    def test_snapshot_is_side_effect_free_and_preserves_registry_order(self) -> None:
        store = RecordingSessionStore()
        manager = SessionManager(self.event_bus, store)
        manager.create("work-1")
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))
        saved_before = len(store.saved_snapshots)

        snapshot = manager.snapshot()

        self.assertEqual(snapshot.active_session_id, "default")
        self.assertEqual(
            [session.session_id for session in snapshot.sessions], ["default", "work-1"]
        )
        self.assertEqual(len(store.saved_snapshots), saved_before)
        self.assertEqual(events, [])

    def test_persist_snapshot_writes_once_without_changing_ram_or_events(self) -> None:
        store = RecordingSessionStore()
        manager = SessionManager(self.event_bus, store)
        manager.create("work-1")
        candidate = self._snapshot(active_session_id="work-1")
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))

        self.assertIsNone(manager.persist_snapshot(candidate))

        self.assertEqual(store.saved_snapshots[-1], candidate)
        self.assertEqual(manager.snapshot().active_session_id, "default")
        self.assertEqual(events, [])

    def test_persist_snapshot_is_a_validated_no_op_without_a_store(self) -> None:
        candidate = self._snapshot(active_session_id="work-1")

        self.assertIsNone(self.manager.persist_snapshot(candidate))
        self.assertEqual(self.manager.get_active().session_id, "default")

    def test_persist_snapshot_propagates_store_failure_without_ram_or_event_changes(
        self,
    ) -> None:
        store = FailingSessionStore()
        store.fail_save = True
        manager = SessionManager(self.event_bus, store)
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))

        with self.assertRaisesRegex(SessionError, "^Session save failed\\.$"):
            manager.persist_snapshot(self._snapshot(active_session_id="work-1"))

        self.assertEqual(manager.get_active().session_id, "default")
        self.assertEqual(events, [])

    def test_commit_snapshot_replaces_ram_without_store_or_events(self) -> None:
        store = RecordingSessionStore()
        manager = SessionManager(self.event_bus, store)
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))
        candidate = self._snapshot(active_session_id="work-1")

        self.assertIsNone(manager.commit_snapshot(candidate))

        self.assertEqual(
            [session.session_id for session in manager.list()], ["default", "work-1"]
        )
        self.assertEqual(manager.get_active().session_id, "work-1")
        self.assertEqual(store.saved_snapshots, [])
        self.assertEqual(events, [])

    def test_snapshot_validation_failures_are_exact_and_side_effect_free(self) -> None:
        naive = datetime(2026, 8, 4, 15, 0)
        cases = (
            (object(), "Session snapshot must be a SessionRegistrySnapshot."),
            (
                SessionRegistrySnapshot("default", ()),
                "Session snapshot must contain at least one session.",
            ),
            (
                SessionRegistrySnapshot("default", ("bad",)),
                "Session snapshot contains an invalid session record.",
            ),
            (
                SessionRegistrySnapshot("default", (SessionRecord(" bad ", naive),)),
                "Session snapshot contains an invalid session ID.",
            ),
            (
                SessionRegistrySnapshot(
                    "default",
                    (SessionRecord("default", naive), SessionRecord("default", naive)),
                ),
                "Session snapshot contains duplicate session IDs.",
            ),
            (
                SessionRegistrySnapshot("work", (SessionRecord("work", naive),)),
                "Session snapshot must contain the default session.",
            ),
            (
                SessionRegistrySnapshot(" ", (SessionRecord("default", naive),)),
                "Session snapshot has an invalid active session ID.",
            ),
            (
                SessionRegistrySnapshot("work", (SessionRecord("default", naive),)),
                "Active session ID must exist in the session registry.",
            ),
            (
                SessionRegistrySnapshot("default", (SessionRecord("default", naive),)),
                "Session record created_at must include timezone information.",
            ),
        )
        before = self.manager.snapshot()
        for snapshot, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(SessionError, re.escape(message)):
                    self.manager.commit_snapshot(snapshot)  # type: ignore[arg-type]
        self.assertEqual(self.manager.snapshot(), before)

    @staticmethod
    def _snapshot(*, active_session_id: str) -> SessionRegistrySnapshot:
        created_at = datetime(2026, 8, 4, 15, 0, tzinfo=UTC)
        return SessionRegistrySnapshot(
            active_session_id=active_session_id,
            sessions=(
                SessionRecord(session_id="default", created_at=created_at),
                SessionRecord(session_id="work-1", created_at=created_at),
            ),
        )


if __name__ == "__main__":
    unittest.main()
