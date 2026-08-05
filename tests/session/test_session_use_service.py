"""Unit tests for command-level active-session delegation."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import SessionError
from eventbus.EventBus import EventBus
from session.SessionManager import SessionManager
from session.SessionUseService import SessionUseService


class SessionUseServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.event_bus = EventBus()
        self.manager = SessionManager(self.event_bus)
        self.manager.create("work")
        self.service = SessionUseService(self.manager)

    def test_use_delegates_to_the_manager_transaction(self) -> None:
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))

        result = self.service.use("work")

        self.assertEqual(result.session_id, "work")
        self.assertEqual(self.manager.get_active().session_id, "work")
        self.assertEqual(events, ["session.activated"])

    def test_use_active_session_is_a_no_op_without_an_event(self) -> None:
        before = self.manager.snapshot()
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))

        result = self.service.use("default")

        self.assertEqual(result.session_id, "default")
        self.assertEqual(self.manager.snapshot(), before)
        self.assertEqual(events, [])

    def test_use_unknown_session_preserves_state_without_an_event(self) -> None:
        before = self.manager.snapshot()
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))

        with self.assertRaisesRegex(SessionError, "Unknown session: unknown"):
            self.service.use("unknown")

        self.assertEqual(self.manager.snapshot(), before)
        self.assertEqual(events, [])


if __name__ == "__main__":
    unittest.main()
