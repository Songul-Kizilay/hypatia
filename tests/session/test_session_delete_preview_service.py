"""Unit tests for read-only session deletion previews."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import SessionError
from eventbus.EventBus import EventBus
from memory.MemoryManager import MemoryManager
from session.SessionDeletePolicy import SessionDeleteStatus
from session.SessionDeletePreviewService import SessionDeletePreviewService
from session.SessionManager import SessionManager


class SessionDeletePreviewServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.event_bus = EventBus()
        self.sessions = SessionManager(self.event_bus)
        self.memory = MemoryManager(event_bus=self.event_bus)
        self.sessions.create("work")
        self.sessions.create("empty")
        self.sessions.create("vacant")
        self.memory.add(
            "Work",
            metadata={"session_id": "work"},
            tags={"brain", "conversation"},
        )
        self.memory.add(
            "Other",
            metadata={"session_id": "empty"},
            tags={"brain", "conversation"},
        )
        self.service = SessionDeletePreviewService(self.sessions, self.memory)

    def test_preview_reports_matching_memory_ids_without_side_effects(self) -> None:
        sessions_before = self.sessions.snapshot()
        memory_before = self.memory.snapshot()
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))

        session_id, memory_ids, status, reason = self.service.preview("work")

        self.assertEqual(session_id, "work")
        self.assertEqual(memory_ids, (memory_before[0].memory_id,))
        self.assertEqual(status, SessionDeleteStatus.PENDING_MEMORY_POLICY)
        self.assertEqual(reason, "session has attached memories")
        self.assertEqual(self.sessions.snapshot(), sessions_before)
        self.assertEqual(self.memory.snapshot(), memory_before)
        self.assertEqual(events, [])

    def test_preview_reports_policy_denials_without_side_effects(self) -> None:
        for session_id, expected_reason in (
            ("default", "default session cannot be deleted"),
            ("work", "active session cannot be deleted"),
        ):
            with self.subTest(session_id=session_id):
                if session_id == "work":
                    self.sessions.set_active("work")
                before = self.sessions.snapshot()

                _, _, status, reason = self.service.preview(session_id)

                self.assertEqual(status, SessionDeleteStatus.DENY)
                self.assertEqual(reason, expected_reason)
                self.assertEqual(self.sessions.snapshot(), before)

    def test_preview_reports_allow_for_an_inactive_session_without_memories(
        self,
    ) -> None:
        session_id, memory_ids, status, reason = self.service.preview("vacant")

        self.assertEqual(session_id, "vacant")
        self.assertEqual(memory_ids, ())
        self.assertEqual(status, SessionDeleteStatus.ALLOW)
        self.assertEqual(reason, "")

    def test_preview_rejects_unknown_targets(self) -> None:
        with self.assertRaisesRegex(SessionError, "Unknown session: unknown"):
            self.service.preview("unknown")


if __name__ == "__main__":
    unittest.main()
