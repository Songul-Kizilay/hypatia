"""Integration tests for Bootstrap dependency wiring."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.Brain import Brain
from core.Bootstrap import Bootstrap
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.MemoryManager import MemoryManager


class BootstrapTests(unittest.TestCase):
    def test_bootstrap_wires_cognitive_search_to_shared_memory_manager(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            document_path = Path(temporary_directory) / "knowledge.md"
            document_path.write_text("Hypatia", encoding="utf-8")

            bootstrap = Bootstrap()
            bootstrap.initialize()
            container = bootstrap.container
            knowledge_engine = container.resolve(KnowledgeEngine)
            memory_manager = container.resolve(MemoryManager)
            brain = container.resolve(Brain)
            knowledge_engine.load(document_path)

            response = brain.process("search hypatia")

        self.assertTrue(response.success)
        self.assertEqual(len(memory_manager.all()), 1)
        self.assertEqual(
            memory_manager.all()[0].content,
            "User: search hypatia\nHypatia: I found 1 matching knowledge chunks.",
        )

    def test_bootstrap_wires_brain_to_the_planner(self) -> None:
        bootstrap = Bootstrap()
        bootstrap.initialize()
        brain = bootstrap.container.resolve(Brain)

        response = brain.process("plan learn SQL injection")

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "plan")
        self.assertIn("Plan created for: learn SQL injection", response.message)
        self.assertIn("1. Clarify goal", response.message)

    def test_bootstrap_processes_greeting_through_cognition(self) -> None:
        bootstrap = Bootstrap()
        bootstrap.initialize()
        brain = bootstrap.container.resolve(Brain)

        response = brain.process("hello")

        self.assertEqual(response.intent, "greeting")
        self.assertEqual(response.message, "Hello! I am Hypatia.")

    def test_bootstrap_processes_message_through_cognition(self) -> None:
        bootstrap = Bootstrap()
        bootstrap.initialize()
        brain = bootstrap.container.resolve(Brain)

        response = brain.process("how are you")

        self.assertEqual(response.intent, "message")
        self.assertEqual(response.message, "I received your message: how are you")


if __name__ == "__main__":
    unittest.main()
