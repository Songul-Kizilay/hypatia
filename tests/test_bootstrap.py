"""Integration tests for Bootstrap dependency wiring."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.Brain import Brain
from brain.BrainRequest import BrainRequest
from core.Bootstrap import Bootstrap
from core.Exceptions import MemoryError
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.JsonFileMemoryStore import JsonFileMemoryStore
from memory.MemoryManager import MemoryManager
from memory.MemoryRecord import MemoryRecord
from response.ResponseComposer import ResponseComposer


class BootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.memory_path = Path(self.temporary_directory.name) / "memory.json"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _bootstrap(self) -> Bootstrap:
        return Bootstrap(memory_path=self.memory_path)

    def test_bootstrap_registers_response_composer(self) -> None:
        bootstrap = self._bootstrap()
        bootstrap.initialize()

        response_composer = bootstrap.container.resolve(ResponseComposer)

        self.assertIsInstance(response_composer, ResponseComposer)

    def test_bootstrap_wires_cognitive_search_to_shared_memory_manager(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            document_path = Path(temporary_directory) / "knowledge.md"
            document_path.write_text("Hypatia", encoding="utf-8")

            bootstrap = self._bootstrap()
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
        bootstrap = self._bootstrap()
        bootstrap.initialize()
        brain = bootstrap.container.resolve(Brain)

        response = brain.process("plan learn SQL injection")

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "plan")
        self.assertIn("Plan created for: learn SQL injection", response.message)
        self.assertIn("1. Clarify goal", response.message)

    def test_bootstrap_processes_greeting_through_cognition(self) -> None:
        bootstrap = self._bootstrap()
        bootstrap.initialize()
        brain = bootstrap.container.resolve(Brain)

        response = brain.process("hello")

        self.assertEqual(response.intent, "greeting")
        self.assertEqual(response.message, "Hello! I am Hypatia.")

    def test_bootstrap_processes_message_through_cognition(self) -> None:
        bootstrap = self._bootstrap()
        bootstrap.initialize()
        brain = bootstrap.container.resolve(Brain)

        response = brain.process("how are you")

        self.assertEqual(response.intent, "message")
        self.assertEqual(response.message, "I received your message: how are you")

    def test_bootstrap_registers_json_file_memory_store_with_default_path(self) -> None:
        bootstrap = Bootstrap()
        bootstrap.initialize()

        store = bootstrap.container.resolve(JsonFileMemoryStore)
        project_root = Path(__file__).resolve().parents[1]

        self.assertEqual(store._path, project_root / "data" / "memory" / "memory.json")

    def test_bootstrap_loads_existing_memory_for_explicit_recall(self) -> None:
        record = MemoryRecord(
            memory_id="conversation-1",
            content="User: I like cats\nHypatia: Noted.",
            tags=frozenset({"brain", "conversation"}),
        )
        JsonFileMemoryStore(self.memory_path).save([record])
        bootstrap = self._bootstrap()

        bootstrap.initialize()
        memory_manager = bootstrap.container.resolve(MemoryManager)
        brain = bootstrap.container.resolve(Brain)
        response = brain.process("recall cats")

        self.assertEqual(memory_manager.all(), [record])
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 1)
        self.assertIn(record.content, response.message)

    def test_missing_memory_file_starts_with_empty_memory(self) -> None:
        bootstrap = self._bootstrap()

        bootstrap.initialize()

        memory_manager = bootstrap.container.resolve(MemoryManager)
        self.assertEqual(memory_manager.all(), [])

    def test_corrupt_memory_file_stops_bootstrap_without_a_container(self) -> None:
        self.memory_path.write_text("{invalid", encoding="utf-8")
        bootstrap = self._bootstrap()

        with self.assertRaises(MemoryError):
            bootstrap.initialize()

        self.assertFalse(hasattr(bootstrap, "container"))

    def test_persisted_conversation_is_recalled_after_bootstrap_restart(self) -> None:
        first_bootstrap = self._bootstrap()
        first_bootstrap.initialize()
        first_brain = first_bootstrap.container.resolve(Brain)
        first_brain.process("I like cats")

        restarted_bootstrap = self._bootstrap()
        restarted_bootstrap.initialize()
        restarted_brain = restarted_bootstrap.container.resolve(Brain)
        response = restarted_brain.process("recall cats")

        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 1)
        self.assertIn("User: I like cats", response.message)

    def test_persisted_search_records_are_excluded_from_recall(self) -> None:
        document_path = Path(self.temporary_directory.name) / "knowledge.md"
        document_path.write_text("Hypatia", encoding="utf-8")
        first_bootstrap = self._bootstrap()
        first_bootstrap.initialize()
        knowledge_engine = first_bootstrap.container.resolve(KnowledgeEngine)
        first_brain = first_bootstrap.container.resolve(Brain)
        knowledge_engine.load(document_path)
        first_brain.process("search hypatia")

        restarted_bootstrap = self._bootstrap()
        restarted_bootstrap.initialize()
        restarted_brain = restarted_bootstrap.container.resolve(Brain)
        response = restarted_brain.process("recall hypatia")

        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.message, "No matching conversation records found.")

    def test_custom_session_conversation_persists_and_is_recalled_after_restart(
        self,
    ) -> None:
        first_bootstrap = self._bootstrap()
        first_bootstrap.initialize()
        first_brain = first_bootstrap.container.resolve(Brain)
        first_brain.process(
            BrainRequest(
                message="I like cats",
                metadata={"session_id": "work-1"},
            )
        )

        document = json.loads(self.memory_path.read_text(encoding="utf-8"))
        self.assertEqual(document["schema_version"], 1)
        self.assertEqual(document["records"][0]["metadata"]["session_id"], "work-1")
        self.assertEqual(set(document), {"schema_version", "records"})

        restarted_bootstrap = self._bootstrap()
        restarted_bootstrap.initialize()
        restarted_brain = restarted_bootstrap.container.resolve(Brain)
        response = restarted_brain.process(
            BrainRequest(
                message="recall cats",
                metadata={"session_id": "work-1"},
            )
        )

        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 1)
        self.assertIn("User: I like cats", response.message)

    def test_custom_session_record_is_excluded_from_default_recall_after_restart(
        self,
    ) -> None:
        first_bootstrap = self._bootstrap()
        first_bootstrap.initialize()
        first_brain = first_bootstrap.container.resolve(Brain)
        first_brain.process(
            BrainRequest(
                message="I like cats",
                metadata={"session_id": "work-1"},
            )
        )

        restarted_bootstrap = self._bootstrap()
        restarted_bootstrap.initialize()
        restarted_brain = restarted_bootstrap.container.resolve(Brain)
        response = restarted_brain.process("recall cats")

        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 0)

    def test_same_query_stays_isolated_between_sessions_after_restart(self) -> None:
        first_bootstrap = self._bootstrap()
        first_bootstrap.initialize()
        first_brain = first_bootstrap.container.resolve(Brain)
        first_brain.process(
            BrainRequest(
                message="Cats are my work topic",
                metadata={"session_id": "work-1"},
            )
        )
        first_brain.process(
            BrainRequest(
                message="Cats are my personal topic",
                metadata={"session_id": "personal"},
            )
        )

        restarted_bootstrap = self._bootstrap()
        restarted_bootstrap.initialize()
        restarted_brain = restarted_bootstrap.container.resolve(Brain)
        work_response = restarted_brain.process(
            BrainRequest(
                message="recall cats",
                metadata={"session_id": "work-1"},
            )
        )
        personal_response = restarted_brain.process(
            BrainRequest(
                message="recall cats",
                metadata={"session_id": "personal"},
            )
        )

        self.assertIn("work topic", work_response.message)
        self.assertNotIn("personal topic", work_response.message)
        self.assertIn("personal topic", personal_response.message)
        self.assertNotIn("work topic", personal_response.message)

    def test_persisted_search_records_are_excluded_from_custom_session_recall(
        self,
    ) -> None:
        document_path = Path(self.temporary_directory.name) / "knowledge.md"
        document_path.write_text("Hypatia", encoding="utf-8")
        first_bootstrap = self._bootstrap()
        first_bootstrap.initialize()
        knowledge_engine = first_bootstrap.container.resolve(KnowledgeEngine)
        first_brain = first_bootstrap.container.resolve(Brain)
        knowledge_engine.load(document_path)
        first_brain.process("search hypatia")

        restarted_bootstrap = self._bootstrap()
        restarted_bootstrap.initialize()
        restarted_brain = restarted_bootstrap.container.resolve(Brain)
        response = restarted_brain.process(
            BrainRequest(
                message="recall hypatia",
                metadata={"session_id": "work-1"},
            )
        )

        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 0)


if __name__ == "__main__":
    unittest.main()
