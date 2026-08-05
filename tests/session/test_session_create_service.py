"""Unit tests for command-level session creation validation."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import SessionError
from eventbus.EventBus import EventBus
from session.SessionCreateService import SessionCreateService
from session.SessionManager import SessionManager


class SessionCreateServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.event_bus = EventBus()
        self.manager = SessionManager(self.event_bus)
        self.service = SessionCreateService(self.manager)

    def test_create_delegates_to_the_manager_transaction(self) -> None:
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))

        result = self.service.create("project-alpha")

        self.assertTrue(result.created)
        self.assertEqual(result.session.session_id, "project-alpha")
        self.assertTrue(self.manager.exists("project-alpha"))
        self.assertEqual(events, ["session.created"])

    def test_create_preserves_existing_normalized_id_compatibility(self) -> None:
        result = self.service.create("work research")

        self.assertTrue(result.created)
        self.assertEqual(result.session.session_id, "work research")

    def test_create_rejects_empty_ids_without_state_or_event_changes(self) -> None:
        self._assert_failure_preserves_state("", "session_id must not be empty.")

    def test_create_rejects_reserved_default_without_state_or_event_changes(
        self,
    ) -> None:
        self._assert_failure_preserves_state(
            "default",
            "reserved default session id.",
        )

    def test_create_returns_existing_session_without_state_or_event_changes(
        self,
    ) -> None:
        self.manager.create("work")
        before = self.manager.snapshot()
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))

        result = self.service.create("work")

        self.assertFalse(result.created)
        self.assertEqual(result.session.session_id, "work")
        self.assertEqual(self.manager.snapshot(), before)
        self.assertEqual(events, [])

    def test_create_preserves_manager_invalid_type_validation(self) -> None:
        with self.assertRaisesRegex(SessionError, "session_id must be a string"):
            self.service.create(None)  # type: ignore[arg-type]

    def _assert_failure_preserves_state(self, session_id: str, message: str) -> None:
        before = self.manager.snapshot()
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))

        with self.assertRaisesRegex(SessionError, message):
            self.service.create(session_id)

        self.assertEqual(self.manager.snapshot(), before)
        self.assertEqual(events, [])


if __name__ == "__main__":
    unittest.main()
