"""Unit tests for guarded session-delete orchestration."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from threading import Event, Thread

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import MemoryError, SessionDeleteEventError, SessionError
from eventbus.EventBus import EventBus
from memory.MemoryManager import MemoryManager
from session.SessionDeleteService import SessionDeleteService
from session.SessionDeleteTransactionService import SessionDeleteTransactionService
from session.SessionManager import SessionManager


class SnapshotMutatingMemoryManager(MemoryManager):
    """Make the guard observe one independently changed memory snapshot."""

    def run_if_snapshot_current(self, expected_snapshot, operation):  # type: ignore[no-untyped-def]
        self.add("Intervening", metadata={"session_id": "work"})
        return super().run_if_snapshot_current(expected_snapshot, operation)


class GuardTrackingMemoryManager(MemoryManager):
    """Expose whether a guarded callback is currently running."""

    def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        super().__init__(*args, **kwargs)
        self.inside_guard = False

    def run_if_snapshot_current(self, expected_snapshot, operation):  # type: ignore[no-untyped-def]
        self.inside_guard = True
        try:
            return super().run_if_snapshot_current(expected_snapshot, operation)
        finally:
            self.inside_guard = False


class BlockingTransactionService(SessionDeleteTransactionService):
    """Pause the guarded commit so another memory write attempts to race it."""

    def __init__(self) -> None:
        self.commit_entered = Event()
        self.release_commit = Event()

    def commit(self, context, sessions):  # type: ignore[no-untyped-def]
        self.commit_entered.set()
        self.release_commit.wait(timeout=2)
        return super().commit(context, sessions)


class ApplyMutatingSessionManager(SessionManager):
    """Write to the registry immediately before one atomic delete apply."""

    def __init__(self, event_bus: EventBus) -> None:
        super().__init__(event_bus)
        self.mutate_before_apply = False

    def apply_snapshot_if_current(self, expected, candidate):  # type: ignore[no-untyped-def]
        if self.mutate_before_apply:
            self.mutate_before_apply = False
            self.create("research")
        super().apply_snapshot_if_current(expected, candidate)


class SessionDeleteServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.event_bus = EventBus()
        self.sessions = SessionManager(self.event_bus)
        self.memory = MemoryManager(event_bus=self.event_bus)
        self.sessions.create("work")
        self.sessions.create("archive")
        self.service = SessionDeleteService(self.sessions, self.memory)

    def test_delete_commits_an_inactive_zero_memory_session_and_emits_once(
        self,
    ) -> None:
        events: list[object] = []
        self.event_bus.subscribe("*", events.append)

        result = self.service.delete("work")

        self.assertTrue(result.committed)
        self.assertEqual(result.session_id, "work")
        self.assertEqual(result.memory_records_removed, 0)
        self.assertEqual(
            tuple(session.session_id for session in self.sessions.list()),
            ("default", "archive"),
        )
        self.assertEqual(self.memory.snapshot(), ())
        self.assertEqual([event.name for event in events], ["session.deleted"])

    def test_delete_rejects_default_active_and_unknown_targets_without_mutation(
        self,
    ) -> None:
        self.sessions.set_active("work")
        sessions_before = self.sessions.snapshot()
        memory_before = self.memory.snapshot()
        events: list[object] = []
        self.event_bus.subscribe("*", events.append)

        for session_id, reason in (
            ("default", "default session cannot be deleted"),
            ("work", "active session cannot be deleted"),
            ("missing", "Unknown session: missing"),
        ):
            with self.subTest(session_id=session_id):
                with self.assertRaisesRegex(SessionError, f"^{reason}$"):
                    self.service.delete(session_id)

                self.assertEqual(self.sessions.snapshot(), sessions_before)
                self.assertEqual(self.memory.snapshot(), memory_before)
                self.assertEqual(events, [])

    def test_delete_rejects_attached_memory_without_deleting_or_emitting(self) -> None:
        record = self.memory.add(
            "Work",
            metadata={"session_id": "work"},
            tags={"brain", "conversation"},
        )
        sessions_before = self.sessions.snapshot()
        memory_before = self.memory.snapshot()
        events: list[object] = []
        self.event_bus.subscribe("*", events.append)

        with self.assertRaisesRegex(SessionError, "^session has attached memories$"):
            self.service.delete("work")

        self.assertEqual(self.sessions.snapshot(), sessions_before)
        self.assertEqual(self.memory.snapshot(), memory_before)
        self.assertEqual(self.memory.get(record.memory_id), record)
        self.assertEqual(events, [])

    def test_delete_rejects_an_intervening_memory_change_before_session_commit(
        self,
    ) -> None:
        memory = SnapshotMutatingMemoryManager(event_bus=self.event_bus)
        service = SessionDeleteService(self.sessions, memory)
        sessions_before = self.sessions.snapshot()
        events: list[object] = []
        self.event_bus.subscribe("*", events.append)

        with self.assertRaisesRegex(MemoryError, "^Memory snapshot changed\\.$"):
            service.delete("work")

        self.assertEqual(self.sessions.snapshot(), sessions_before)
        self.assertEqual([event.name for event in events], ["memory.record.added"])

    def test_delete_emits_after_releasing_the_memory_guard(self) -> None:
        memory = GuardTrackingMemoryManager(event_bus=self.event_bus)
        service = SessionDeleteService(self.sessions, memory)
        guard_states: list[bool] = []
        self.event_bus.subscribe(
            "session.deleted",
            lambda event: guard_states.append(memory.inside_guard),
        )

        service.delete("work")

        self.assertEqual(guard_states, [False])

    def test_delete_reports_a_post_commit_event_failure_without_rollback(self) -> None:
        memory_before = self.memory.snapshot()
        event_error = RuntimeError("subscriber failed")

        def fail_subscriber(event: object) -> None:
            raise event_error

        self.event_bus.subscribe("session.deleted", fail_subscriber)

        with self.assertRaisesRegex(
            SessionDeleteEventError,
            "^Session delete committed but lifecycle event publication failed\\.$",
        ) as raised:
            self.service.delete("work")

        error = raised.exception
        self.assertEqual(error.result.session_id, "work")
        self.assertEqual(error.result.memory_records_removed, 0)
        self.assertTrue(error.result.committed)
        self.assertIs(error.event_error, event_error)
        self.assertIs(error.__cause__, event_error)
        self.assertFalse(self.sessions.exists("work"))
        self.assertEqual(self.memory.snapshot(), memory_before)

    def test_delete_blocks_a_concurrent_memory_write_while_committing(self) -> None:
        transaction = BlockingTransactionService()
        service = SessionDeleteService(self.sessions, self.memory, transaction)
        delete_error: list[Exception] = []
        add_finished = Event()

        def delete() -> None:
            try:
                service.delete("work")
            except Exception as error:  # pragma: no cover - assertion below
                delete_error.append(error)

        def add_memory() -> None:
            self.memory.add("Later")
            add_finished.set()

        delete_thread = Thread(target=delete)
        delete_thread.start()
        self.assertTrue(transaction.commit_entered.wait(timeout=1))
        add_thread = Thread(target=add_memory)
        add_thread.start()
        self.assertFalse(add_finished.wait(timeout=0.05))

        transaction.release_commit.set()
        delete_thread.join(timeout=1)
        add_thread.join(timeout=1)

        self.assertEqual(delete_error, [])
        self.assertFalse(delete_thread.is_alive())
        self.assertFalse(add_thread.is_alive())
        self.assertTrue(add_finished.is_set())

    def test_delete_propagates_a_stale_session_snapshot_without_delete_event(
        self,
    ) -> None:
        event_bus = EventBus()
        sessions = ApplyMutatingSessionManager(event_bus)
        sessions.create("work")
        sessions.mutate_before_apply = True
        service = SessionDeleteService(sessions, MemoryManager(event_bus=event_bus))
        deleted_events: list[object] = []
        event_bus.subscribe("session.deleted", deleted_events.append)

        with self.assertRaisesRegex(SessionError, "^Session snapshot changed\\.$"):
            service.delete("work")

        self.assertEqual(
            tuple(session.session_id for session in sessions.list()),
            ("default", "work", "research"),
        )
        self.assertEqual(deleted_events, [])

    def test_delete_propagates_session_snapshot_and_persistence_failures_without_event(
        self,
    ) -> None:
        class FailingSessionStore:
            def load(self):  # type: ignore[no-untyped-def]
                return None

            def save(self, snapshot):  # type: ignore[no-untyped-def]
                raise RuntimeError("session store unavailable")

        event_bus = EventBus()
        sessions = SessionManager(event_bus, FailingSessionStore())
        with self.assertRaises(RuntimeError):
            sessions.create("work")

        # Set up in memory, then fail only on the delete persistence path.
        sessions = SessionManager(event_bus)
        sessions.create("work")
        original = sessions.snapshot()
        sessions._store = FailingSessionStore()  # type: ignore[attr-defined]
        service = SessionDeleteService(sessions, MemoryManager(event_bus=event_bus))
        events: list[object] = []
        event_bus.subscribe("*", events.append)

        with self.assertRaisesRegex(RuntimeError, "^session store unavailable$"):
            service.delete("work")

        self.assertEqual(sessions.snapshot(), original)
        self.assertEqual(events, [])


if __name__ == "__main__":
    unittest.main()
