"""Unit tests for the first CognitiveEngine implementation."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

import planner

source_planner_dir = str(SRC_DIR / "planner")
if source_planner_dir not in planner.__path__:
    planner.__path__.append(source_planner_dir)

from brain.BrainRequest import BrainRequest
from cognition.CognitiveEngine import CognitiveEngine
from core.Exceptions import KnowledgeError, MemoryError, PlannerError
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.MemoryManager import MemoryManager
from planner.Planner import Planner


class FailingKnowledgeEngine:
    """Minimal failure double for KnowledgeError handling coverage."""

    def search(self, query: str) -> list[object]:
        raise KnowledgeError("Knowledge is unavailable.")


class FailingMemoryManager:
    """Minimal failure double that preserves search response behavior."""

    def add(self, *args: object, **kwargs: object) -> None:
        raise MemoryError("Memory is unavailable.")


class FailingPlanner:
    """Minimal failure double for PlannerError handling coverage."""

    def create_plan(self, goal: str) -> None:
        raise PlannerError("Planner is unavailable.")


class CognitiveEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        path = Path(self.temporary_directory.name) / "knowledge.md"
        path.write_text("Hypatia\n\nKnowledge\n\nHypatia", encoding="utf-8")
        self.knowledge_engine = KnowledgeEngine()
        self.knowledge_engine.load(path)
        self.memory_manager = MemoryManager(EventBus())
        self.planner = Planner()
        self.engine = CognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_search_intent_returns_a_successful_response(self) -> None:
        response = self.engine.process(BrainRequest(message="search hypatia"))

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "search")

    def test_search_response_reports_matching_chunk_count(self) -> None:
        response = self.engine.process(BrainRequest(message="search hypatia"))

        self.assertEqual(response.message, "I found 2 matching knowledge chunks.")

    def test_search_response_contains_knowledge_results(self) -> None:
        response = self.engine.process(BrainRequest(message="search hypatia"))

        self.assertEqual(
            [chunk.content for chunk in response.knowledge_results],
            ["Hypatia", "Hypatia"],
        )

    def test_successful_search_is_saved_to_memory(self) -> None:
        self.engine.process(BrainRequest(message="search hypatia"))

        records = self.memory_manager.all()

        self.assertEqual(len(records), 1)

    def test_successful_search_memory_has_expected_content(self) -> None:
        self.engine.process(BrainRequest(message="search hypatia"))

        self.assertEqual(
            self.memory_manager.all()[0].content,
            "User: search hypatia\nHypatia: I found 2 matching knowledge chunks.",
        )

    def test_successful_search_memory_has_expected_tags(self) -> None:
        self.engine.process(BrainRequest(message="search hypatia"))

        self.assertEqual(
            self.memory_manager.all()[0].tags,
            frozenset({"cognition", "knowledge-search", "conversation"}),
        )

    def test_successful_search_memory_has_expected_metadata(self) -> None:
        response = self.engine.process(BrainRequest(message="search hypatia"))

        self.assertEqual(
            dict(self.memory_manager.all()[0].metadata),
            {
                "intent": "search",
                "query": "hypatia",
                "result_count": 2,
                "success": response.success,
            },
        )

    def test_declared_search_intent_uses_request_message_as_query(self) -> None:
        request = BrainRequest(message="hypatia", metadata={"intent": "search"})

        response = self.engine.process(request)

        self.assertEqual(len(response.knowledge_results), 2)

    def test_empty_search_query_returns_controlled_response(self) -> None:
        response = self.engine.process(BrainRequest(message="search "))

        self.assertFalse(response.success)
        self.assertEqual(response.intent, "search")
        self.assertEqual(response.message, "A search query is required.")

    def test_empty_search_query_is_saved_to_memory(self) -> None:
        self.engine.process(BrainRequest(message="search "))

        self.assertEqual(
            self.memory_manager.all()[0].content,
            "User: search \nHypatia: A search query is required.",
        )
        self.assertEqual(
            dict(self.memory_manager.all()[0].metadata),
            {
                "intent": "search",
                "query": "",
                "result_count": 0,
                "success": False,
            },
        )

    def test_search_with_no_results_returns_empty_result_list(self) -> None:
        response = self.engine.process(BrainRequest(message="search missing"))

        self.assertTrue(response.success)
        self.assertEqual(response.knowledge_results, [])
        self.assertEqual(response.message, "I found 0 matching knowledge chunks.")

    def test_unsupported_intent_returns_safe_response(self) -> None:
        response = self.engine.process(BrainRequest(message="hello"))

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "unsupported")
        self.assertEqual(response.message, "This intent is not supported yet.")

    def test_knowledge_error_returns_unsuccessful_response(self) -> None:
        memory_manager = MemoryManager()
        engine = CognitiveEngine(
            FailingKnowledgeEngine(),  # type: ignore[arg-type]
            memory_manager,
            Planner(),
        )

        response = engine.process(BrainRequest(message="search hypatia"))

        self.assertFalse(response.success)
        self.assertEqual(response.intent, "search")
        self.assertEqual(response.knowledge_results, [])

    def test_knowledge_error_response_is_saved_to_memory(self) -> None:
        memory_manager = MemoryManager()
        engine = CognitiveEngine(
            FailingKnowledgeEngine(),  # type: ignore[arg-type]
            memory_manager,
            Planner(),
        )

        engine.process(BrainRequest(message="search hypatia"))

        self.assertEqual(
            memory_manager.all()[0].content,
            "User: search hypatia"
            "\nHypatia: Knowledge search failed: Knowledge is unavailable.",
        )

    def test_memory_error_does_not_prevent_a_successful_search_response(self) -> None:
        engine = CognitiveEngine(
            self.knowledge_engine,
            FailingMemoryManager(),  # type: ignore[arg-type]
            self.planner,
        )

        response = engine.process(BrainRequest(message="search hypatia"))

        self.assertTrue(response.success)
        self.assertEqual(len(response.knowledge_results), 2)

    def test_plan_intent_returns_a_formatted_plan_response(self) -> None:
        response = self.engine.process(
            BrainRequest(message="plan Read a PDF and summarize it")
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "plan")
        self.assertEqual(
            response.message,
            "Plan created for: Read a PDF and summarize it\n\n"
            "1. Locate file\n"
            "2. Read document\n"
            "3. Extract text\n"
            "4. Summarize\n"
            "5. Return response",
        )

    def test_planner_error_returns_controlled_response(self) -> None:
        engine = CognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            FailingPlanner(),  # type: ignore[arg-type]
        )

        response = engine.process(BrainRequest(message="plan learn SQL injection"))

        self.assertFalse(response.success)
        self.assertEqual(response.intent, "plan")
        self.assertEqual(response.message, "Planning failed: Planner is unavailable.")
