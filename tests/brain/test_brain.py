"""Unit tests for the deterministic first Brain flow."""

from __future__ import annotations

import sys
from pathlib import Path
import unittest


SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# unittest imports this file as ``brain.test_brain`` because the test
# directory is a package. Remove that temporary package so imports below
# resolve the real implementation package at ``src/brain``.
loaded_brain = sys.modules.get("brain")
if loaded_brain is not None:
    loaded_path = Path(getattr(loaded_brain, "__file__", "")).resolve()
    if loaded_path.parent == Path(__file__).resolve().parent:
        del sys.modules["brain"]

from brain.Brain import Brain
from core.DependencyContainer import DependencyContainer
from eventbus.EventBus import EventBus
from memory.MemoryManager import MemoryManager


class BrainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.event_bus = EventBus()
        self.memory_manager = MemoryManager(self.event_bus)
        self.container = DependencyContainer()
        self.container.register(self.event_bus)
        self.container.register(self.memory_manager)
        self.brain = Brain(self.container)

    def test_process_returns_greeting_and_saves_conversation(self) -> None:
        response = self.brain.process("hello")

        self.assertEqual(response.intent, "greeting")
        self.assertEqual(response.message, "Hello! I am Hypatia.")
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(self.memory_manager.count(), 1)

    def test_process_checks_existing_memory(self) -> None:
        self.memory_manager.add("hello from a saved memory")

        response = self.brain.process("hello")

        self.assertEqual(response.memory_count, 1)
        self.assertEqual(self.memory_manager.count(), 2)

    def test_process_emits_brain_lifecycle_events(self) -> None:
        observed_events: list[str] = []
        self.event_bus.subscribe("*", lambda event: observed_events.append(event.name))

        self.brain.process("hello")

        self.assertEqual(
            observed_events,
            [
                "brain.request.received",
                "brain.intent.detected",
                "memory.record.added",
                "brain.response.ready",
            ],
        )


if __name__ == "__main__":
    unittest.main()
