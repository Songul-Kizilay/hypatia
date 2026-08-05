"""Tests for in-process session rename transaction orchestration."""

from __future__ import annotations

import sys
import unittest
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import SessionError, SessionRenameRollbackError
from eventbus.EventBus import EventBus
from memory.MemoryRecord import MemoryRecord
from session.SessionRecord import SessionRecord
from session.SessionRegistrySnapshot import SessionRegistrySnapshot
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
        events = []
        bus.subscribe("*", events.append)
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

        with self.assertRaisesRegex(SessionError, "^session candidate failed$"):
            self._service().rename("work", "renamed")

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

    def _service(
        self, *, event_bus: EventBus | None = None
    ) -> SessionRenameTransactionService:
        return SessionRenameTransactionService(
            session_manager=self.session,  # type: ignore[arg-type]
            memory_manager=self.memory,  # type: ignore[arg-type]
            event_bus=event_bus,
        )


if __name__ == "__main__":
    unittest.main()
