"""Tests for in-process session rename transaction orchestration."""

from __future__ import annotations

import sys
import threading
import unittest
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import SessionError, SessionRenameRollbackError
from eventbus.Event import Event as EventBusEvent
from eventbus.EventBus import EventBus
from memory.MemoryManager import MemoryManager
from memory.MemoryRecord import MemoryRecord
from session.SessionManager import SessionManager
from session.SessionRecord import SessionRecord
from session.SessionRegistrySnapshot import SessionRegistrySnapshot
from session.SessionRenamePlanner import SessionRenamePlanner
from session.SessionRenamePreview import SessionRenamePreview
from session.SessionRenameResult import SessionRenameResult
from session.SessionRenameTransactionService import SessionRenameTransactionService


class RecordingSessionManager:
    def __init__(self, snapshot: SessionRegistrySnapshot, calls: list[str]) -> None:
        self.state = snapshot
        self.calls = calls
        self.persist_error: Exception | None = None

    def snapshot(self) -> SessionRegistrySnapshot:
        self.calls.append("session.snapshot")
        return self.state

    def persist_snapshot(self, snapshot: SessionRegistrySnapshot) -> None:
        self.calls.append("session.persist")
        if self.persist_error is not None:
            raise self.persist_error

    def commit_snapshot(self, snapshot: SessionRegistrySnapshot) -> None:
        self.calls.append("session.commit")
        self.state = snapshot


class RecordingMemoryManager:
    def __init__(self, records: tuple[MemoryRecord, ...], calls: list[str]) -> None:
        self.state = records
        self.calls = calls
        self.persist_errors: list[Exception | None] = []

    def snapshot(self) -> tuple[MemoryRecord, ...]:
        self.calls.append("memory.snapshot")
        return self.state

    def persist_snapshot(self, records: tuple[MemoryRecord, ...]) -> None:
        self.calls.append("memory.persist")
        if self.persist_errors:
            error = self.persist_errors.pop(0)
            if error is not None:
                raise error

    def commit_snapshot(self, records: tuple[MemoryRecord, ...]) -> None:
        self.calls.append("memory.commit")
        self.state = records


class SessionRenameTransactionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.calls: list[str] = []
        moment = datetime(2026, 8, 5, tzinfo=UTC)
        self.session = RecordingSessionManager(
            SessionRegistrySnapshot(
                "work",
                (
                    SessionRecord("default", moment),
                    SessionRecord("work", moment),
                    SessionRecord("research", moment),
                ),
            ),
            self.calls,
        )
        self.memory = RecordingMemoryManager(
            (
                MemoryRecord("other", "Other", {"session_id": "research"}),
                MemoryRecord("work-memory", "Work", {"session_id": "work"}),
            ),
            self.calls,
        )

    def test_result_is_frozen_and_has_exact_fields(self) -> None:
        result = SessionRenameResult("work", "renamed", 1, True)
        self.assertEqual(
            tuple(result.__dataclass_fields__),
            (
                "source_session_id",
                "target_session_id",
                "memory_record_count",
                "active_session_changed",
            ),
        )
        with self.assertRaises(FrozenInstanceError):
            result.source_session_id = "other"  # type: ignore[misc]

    def test_successful_rename_has_exact_order_result_and_aggregate_event(self) -> None:
        bus = EventBus()
        events: list[EventBusEvent] = []
        bus.subscribe("*", events.append)
        bus.subscribe("session.renamed", lambda _event: self.calls.append("event"))
        service = self._service(event_bus=bus)

        result = service.rename("work", "renamed")

        self.assertEqual(
            self.calls,
            [
                "session.snapshot",
                "memory.snapshot",
                "memory.persist",
                "session.persist",
                "session.commit",
                "memory.commit",
                "event",
            ],
        )
        self.assertEqual(result, SessionRenameResult("work", "renamed", 1, True))
        self.assertEqual(self.session.state.active_session_id, "renamed")
        self.assertEqual(self.memory.state[1].metadata["session_id"], "renamed")
        self.assertEqual([event.name for event in events], ["session.renamed"])
        self.assertEqual(events[0].source, "session_rename_transaction_service")
        self.assertEqual(
            events[0].payload,
            {
                "source_session_id": "work",
                "target_session_id": "renamed",
                "memory_record_count": 1,
                "active_session_changed": True,
            },
        )

    def test_inactive_and_zero_memory_rename_uses_normalized_result_without_event_bus(
        self,
    ) -> None:
        self.session.state = SessionRegistrySnapshot(
            "research", self.session.state.sessions
        )
        self.memory.state = ()

        result = self._service().rename("  work  ", "  Work Renamed  ")

        self.assertEqual(result, SessionRenameResult("work", "Work Renamed", 0, False))
        self.assertEqual(self.session.state.active_session_id, "research")

    def test_memory_persistence_failure_has_no_later_work_or_ram_changes(self) -> None:
        error = SessionError("memory candidate failed")
        self.memory.persist_errors = [error]

        with self.assertRaisesRegex(SessionError, "^memory candidate failed$"):
            self._service().rename("work", "renamed")

        self.assertEqual(
            self.calls, ["session.snapshot", "memory.snapshot", "memory.persist"]
        )
        self.assertEqual(self.session.state.active_session_id, "work")
        self.assertEqual(self.memory.state[1].metadata["session_id"], "work")

    def test_session_persistence_failure_restores_memory_backup_and_reraises_original(
        self,
    ) -> None:
        error = SessionError("session candidate failed")
        self.session.persist_error = error

        with self.assertRaises(SessionError) as raised:
            self._service().rename("work", "renamed")

        self.assertIs(raised.exception, error)
        self.assertEqual(
            self.calls,
            [
                "session.snapshot",
                "memory.snapshot",
                "memory.persist",
                "session.persist",
                "memory.persist",
            ],
        )
        self.assertEqual(self.session.state.active_session_id, "work")
        self.assertEqual(self.memory.state[1].metadata["session_id"], "work")

    def test_injected_planner_failure_prevents_builder_persistence_commits_and_events(
        self,
    ) -> None:
        error = SessionError("planner failed")
        planner = _FailingPlanner(error)
        builder = _FailingBuilder(SessionError("builder must not run"))
        bus = EventBus()
        events: list[EventBusEvent] = []
        bus.subscribe("*", events.append)

        with self.assertRaises(SessionError) as raised:
            self._service(planner=planner, builder=builder, event_bus=bus).rename(
                "work", "renamed"
            )

        self.assertIs(raised.exception, error)
        self.assertFalse(builder.called)
        self.assertEqual(self.calls, ["session.snapshot", "memory.snapshot"])
        self.assertEqual(events, [])

    def test_injected_builder_failure_prevents_persistence_commits_and_events(
        self,
    ) -> None:
        error = SessionError("builder failed")
        builder = _FailingBuilder(error)
        bus = EventBus()
        events: list[EventBusEvent] = []
        bus.subscribe("*", events.append)

        with self.assertRaises(SessionError) as raised:
            self._service(builder=builder, event_bus=bus).rename("work", "renamed")

        self.assertIs(raised.exception, error)
        self.assertTrue(builder.called)
        self.assertEqual(self.calls, ["session.snapshot", "memory.snapshot"])
        self.assertEqual(events, [])

    def test_real_managers_support_ram_only_rename_without_an_event_bus(self) -> None:
        sessions = SessionManager()
        sessions.create("work")
        sessions.set_active("work")
        memories = MemoryManager()
        record = memories.add("Work", metadata={"session_id": "work"})

        result = SessionRenameTransactionService(
            session_manager=sessions,
            memory_manager=memories,
        ).rename("work", "renamed")

        self.assertEqual(result, SessionRenameResult("work", "renamed", 1, True))
        self.assertEqual(sessions.get_active().session_id, "renamed")
        self.assertEqual(memories.snapshot()[0].memory_id, record.memory_id)
        self.assertEqual(memories.snapshot()[0].metadata["session_id"], "renamed")

    def test_real_managers_support_each_single_store_configuration(self) -> None:
        for session_store, memory_store in (
            (_RecordingSessionStore(), None),
            (None, _RecordingMemoryStore()),
        ):
            with self.subTest(
                session_store=session_store is not None,
                memory_store=memory_store is not None,
            ):
                sessions = SessionManager(store=session_store)
                sessions.create("work")
                sessions.set_active("work")
                memories = MemoryManager(store=memory_store)
                memories.add("Work", metadata={"session_id": "work"})

                result = SessionRenameTransactionService(
                    session_manager=sessions,
                    memory_manager=memories,
                ).rename("work", "renamed")

                self.assertEqual(
                    result,
                    SessionRenameResult("work", "renamed", 1, True),
                )
                self.assertEqual(sessions.get_active().session_id, "renamed")
                self.assertEqual(
                    memories.snapshot()[0].metadata["session_id"],
                    "renamed",
                )
                if session_store is not None:
                    self.assertEqual(
                        session_store.saved[-1].active_session_id,
                        "renamed",
                    )
                if memory_store is not None:
                    self.assertEqual(
                        memory_store.saved[-1][0].metadata["session_id"],
                        "renamed",
                    )

    def test_service_lock_serializes_concurrent_renames(self) -> None:
        entered = threading.Event()
        release = threading.Event()
        planner = _BlockingPlanner(entered, release)
        service = self._service(planner=planner)
        results: list[SessionRenameResult] = []

        first = threading.Thread(
            target=lambda: results.append(service.rename("work", "renamed"))
        )
        second = threading.Thread(
            target=lambda: results.append(service.rename("renamed", "renamed-again"))
        )
        first.start()
        self.assertTrue(entered.wait(timeout=1))
        second.start()
        self.assertEqual(self.calls, ["session.snapshot", "memory.snapshot"])
        release.set()
        first.join(timeout=1)
        second.join(timeout=1)

        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(
            [item.target_session_id for item in results], ["renamed", "renamed-again"]
        )

    def test_failed_memory_rollback_raises_structured_error_from_rollback_error(
        self,
    ) -> None:
        session_error = SessionError("session candidate failed")
        rollback_error = SessionError("memory rollback failed")
        self.session.persist_error = session_error
        self.memory.persist_errors = [None, rollback_error]

        with self.assertRaises(SessionRenameRollbackError) as raised:
            self._service().rename("work", "renamed")

        error = raised.exception
        self.assertEqual(
            str(error),
            "Session rename failed and memory rollback could not be completed.",
        )
        self.assertIs(error.original_error, session_error)
        self.assertIs(error.rollback_error, rollback_error)
        self.assertIs(error.__cause__, rollback_error)
        self.assertNotIn("session.commit", self.calls)

    def test_event_failure_is_propagated_after_both_candidate_commits_without_rollback(
        self,
    ) -> None:
        bus = EventBus()
        bus.subscribe(
            "session.renamed",
            lambda event: (_ for _ in ()).throw(SessionError("event failed")),
        )

        with self.assertRaisesRegex(SessionError, "^event failed$"):
            self._service(event_bus=bus).rename("work", "renamed")

        self.assertEqual(self.session.state.active_session_id, "renamed")
        self.assertEqual(self.memory.state[1].metadata["session_id"], "renamed")
        self.assertEqual(self.calls.count("memory.persist"), 1)

    def test_preview_is_read_only_and_reports_the_planned_effect(self) -> None:
        bus = EventBus()
        events: list[EventBusEvent] = []
        bus.subscribe("*", events.append)
        session_before = self.session.state
        memory_before = self.memory.state

        preview = self._service(event_bus=bus).preview("work", "renamed")

        self.assertEqual(
            preview,
            SessionRenamePreview("work", "renamed", 1, True, ("work-memory",)),
        )
        self.assertEqual(preview.memory_record_ids, ("work-memory",))
        self.assertEqual(self.calls, ["session.snapshot", "memory.snapshot"])
        self.assertEqual(self.session.state, session_before)
        self.assertEqual(self.memory.state, memory_before)
        self.assertEqual(events, [])

    def test_preview_memory_ids_are_immutable_unique_and_count_consistent(self) -> None:
        preview = SessionRenamePreview("work", "renamed", 2, False, ("one", "two"))

        self.assertEqual(preview.memory_record_ids, ("one", "two"))
        with self.assertRaises(FrozenInstanceError):
            preview.memory_record_ids = ()  # type: ignore[misc]
        with self.assertRaisesRegex(ValueError, "must match the record count"):
            SessionRenamePreview("work", "renamed", 1, False, ("one", "two"))
        with self.assertRaisesRegex(ValueError, "must be unique"):
            SessionRenamePreview("work", "renamed", 2, False, ("one", "one"))
        with self.assertRaisesRegex(TypeError, "must be a tuple"):
            SessionRenamePreview("work", "renamed", 1, False, ["one"])  # type: ignore[arg-type]

    def _service(
        self,
        *,
        event_bus: EventBus | None = None,
        planner: object | None = None,
        builder: object | None = None,
    ) -> SessionRenameTransactionService:
        return SessionRenameTransactionService(
            session_manager=self.session,  # type: ignore[arg-type]
            memory_manager=self.memory,  # type: ignore[arg-type]
            planner=planner,  # type: ignore[arg-type]
            candidate_builder=builder,  # type: ignore[arg-type]
            event_bus=event_bus,
        )


class _FailingPlanner:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def create_plan(self, **kwargs: object) -> object:
        raise self.error


class _FailingBuilder:
    def __init__(self, error: Exception) -> None:
        self.error = error
        self.called = False

    def build(self, **kwargs: object) -> object:
        self.called = True
        raise self.error


class _BlockingPlanner:
    def __init__(self, entered: threading.Event, release: threading.Event) -> None:
        self.entered = entered
        self.release = release
        self._planner = SessionRenamePlanner()
        self._calls = 0

    def create_plan(self, **kwargs: object):
        self._calls += 1
        if self._calls == 1:
            self.entered.set()
            self.release.wait(timeout=1)
        return self._planner.create_plan(**kwargs)  # type: ignore[arg-type]


class _RecordingSessionStore:
    def __init__(self) -> None:
        self.saved: list[SessionRegistrySnapshot] = []

    def load(self) -> SessionRegistrySnapshot | None:
        return None

    def save(self, snapshot: SessionRegistrySnapshot) -> None:
        self.saved.append(snapshot)


class _RecordingMemoryStore:
    def __init__(self) -> None:
        self.saved: list[list[MemoryRecord]] = []

    def load(self) -> list[MemoryRecord]:
        return []

    def save(self, records: list[MemoryRecord]) -> None:
        self.saved.append(records)


if __name__ == "__main__":
    unittest.main()
