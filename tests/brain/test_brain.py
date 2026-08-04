"""Unit tests for the deterministic first Brain flow."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

import planner

# unittest imports this file as ``brain.test_brain`` because the test
# directory is a package. Extend that package's search path so imports below
# resolve implementation modules at ``src/brain`` as well.
loaded_brain = sys.modules.get("brain")
if loaded_brain is not None:
    source_brain_dir = str(SRC_DIR / "brain")
    if source_brain_dir not in loaded_brain.__path__:
        loaded_brain.__path__.append(source_brain_dir)

source_planner_dir = str(SRC_DIR / "planner")
if source_planner_dir not in planner.__path__:
    planner.__path__.append(source_planner_dir)

from brain.Brain import Brain
from cognition.CognitiveEngine import CognitiveEngine
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.MemoryManager import MemoryManager
from planner.Planner import Planner


class BrainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.event_bus = EventBus()
        self.memory_manager = MemoryManager(self.event_bus)
        self.knowledge_engine = KnowledgeEngine()
        self.planner = Planner()
        self.cognitive_engine = CognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
        )
        self.brain = Brain(
            self.cognitive_engine,
            self.memory_manager,
            self.event_bus,
        )

    def test_process_returns_greeting_and_saves_conversation(self) -> None:
        response = self.brain.process("hello")

        self.assertEqual(response.intent, "greeting")
        self.assertEqual(response.message, "Hello! I am Hypatia.")
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(self.memory_manager.count(), 1)
        self.assertEqual(
            self.memory_manager.all()[0].content,
            "User: hello\nHypatia: Hello! I am Hypatia.",
        )
        self.assertEqual(
            self.memory_manager.all()[0].tags,
            frozenset({"brain", "conversation"}),
        )

    def test_process_does_not_treat_existing_memory_as_recall(self) -> None:
        self.memory_manager.add("hello from a saved memory")

        response = self.brain.process("hello")

        self.assertEqual(response.memory_count, 0)
        self.assertEqual(self.memory_manager.count(), 2)

    def test_process_returns_message_response_and_saves_one_conversation(self) -> None:
        response = self.brain.process("how are you")

        self.assertEqual(response.intent, "message")
        self.assertEqual(response.message, "I received your message: how are you")
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(self.memory_manager.count(), 1)
        self.assertEqual(
            self.memory_manager.all()[0].content,
            "User: how are you\nHypatia: I received your message: how are you",
        )

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

    def test_process_searches_knowledge_and_returns_matching_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            document_path = Path(temporary_directory) / "knowledge.md"
            document_path.write_text("Hypatia\n\nKnowledge", encoding="utf-8")
            self.knowledge_engine.load(document_path)

            response = self.brain.process("search hypatia")

        self.assertEqual(response.message, "I found 1 matching knowledge chunks.")
        self.assertEqual(
            [chunk.content for chunk in response.knowledge_results], ["Hypatia"]
        )
        self.assertEqual(self.memory_manager.count(), 1)
        self.assertEqual(
            self.memory_manager.all()[0].tags,
            frozenset({"cognition", "knowledge-search", "conversation"}),
        )

    def test_empty_search_is_delegated_to_cognitive_engine(self) -> None:
        response = self.brain.process("search ")

        self.assertFalse(response.success)
        self.assertEqual(response.message, "A search query is required.")
        self.assertEqual(response.knowledge_results, [])

    def test_plan_request_is_delegated_to_cognitive_engine(self) -> None:
        response = self.brain.process("plan learn SQL injection")

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "plan")
        self.assertIn("Plan created for: learn SQL injection", response.message)
        self.assertIn("1. Clarify goal", response.message)
        self.assertEqual(self.memory_manager.count(), 0)

    def test_empty_plan_is_delegated_to_cognitive_engine(self) -> None:
        response = self.brain.process("plan ")

        self.assertFalse(response.success)
        self.assertEqual(response.message, "A planning goal is required.")


if __name__ == "__main__":
    unittest.main()
