"""Unit tests for the synchronous EventBus."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import EventBusError
from eventbus.Event import Event
from eventbus.EventBus import EventBus


class EventBusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bus = EventBus()

    def test_subscribe_and_publish_invokes_handler(self) -> None:
        received: list[Event] = []
        self.bus.subscribe("test.event", received.append)

        invoked = self.bus.publish(Event(name="test.event"))

        self.assertEqual(invoked, 1)
        self.assertEqual(len(received), 1)

    def test_duplicate_subscription_is_ignored(self) -> None:
        received: list[Event] = []
        self.bus.subscribe("test.event", received.append)
        self.bus.subscribe("test.event", received.append)

        self.bus.emit("test.event")

        self.assertEqual(len(received), 1)
        self.assertEqual(self.bus.subscriber_count("test.event"), 1)

    def test_wildcard_handler_receives_every_event(self) -> None:
        received: list[str] = []
        self.bus.subscribe("*", lambda event: received.append(event.name))

        self.bus.emit("one")
        self.bus.emit("two")

        self.assertEqual(received, ["one", "two"])

    def test_unsubscribe_removes_registered_handler(self) -> None:
        def handler(event: Event) -> None:
            return None

        self.bus.subscribe("test.event", handler)

        self.assertTrue(self.bus.unsubscribe("test.event", handler))
        self.assertEqual(self.bus.subscriber_count("test.event"), 0)

    def test_unsubscribe_returns_false_for_unknown_handler(self) -> None:
        self.assertFalse(self.bus.unsubscribe("test.event", lambda event: None))

    def test_subscribe_rejects_blank_event_name(self) -> None:
        with self.assertRaises(EventBusError):
            self.bus.subscribe("   ", lambda event: None)

    def test_emit_preserves_payload_and_source(self) -> None:
        event = self.bus.emit("test.event", {"answer": 42}, source="test")

        self.assertEqual(event.name, "test.event")
        self.assertEqual(event.payload, {"answer": 42})
        self.assertEqual(event.source, "test")

    def test_clear_removes_all_subscriptions(self) -> None:
        self.bus.subscribe("one", lambda event: None)
        self.bus.subscribe("two", lambda event: None)

        self.bus.clear()

        self.assertEqual(self.bus.subscriber_count(), 0)
