"""Unit tests for the first CognitiveEngine implementation."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from brain.BrainRequest import BrainRequest
from cognition.CognitiveEngine import CognitiveEngine
from core.Exceptions import KnowledgeError
from knowledge.KnowledgeEngine import KnowledgeEngine


class FailingKnowledgeEngine:
    """Minimal failure double for KnowledgeError handling coverage."""

    def search(self, query: str) -> list[object]:
        raise KnowledgeError("Knowledge is unavailable.")


class CognitiveEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        path = Path(self.temporary_directory.name) / "knowledge.md"
        path.write_text("Hypatia\n\nKnowledge\n\nHypatia", encoding="utf-8")
        self.knowledge_engine = KnowledgeEngine()
        self.knowledge_engine.load(path)
        self.engine = CognitiveEngine(self.knowledge_engine)

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

    def test_declared_search_intent_uses_request_message_as_query(self) -> None:
        request = BrainRequest(message="hypatia", metadata={"intent": "search"})

        response = self.engine.process(request)

        self.assertEqual(len(response.knowledge_results), 2)

    def test_empty_search_query_returns_controlled_response(self) -> None:
        response = self.engine.process(BrainRequest(message="search "))

        self.assertFalse(response.success)
        self.assertEqual(response.intent, "search")
        self.assertEqual(response.message, "A search query is required.")

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
        engine = CognitiveEngine(FailingKnowledgeEngine())  # type: ignore[arg-type]

        response = engine.process(BrainRequest(message="search hypatia"))

        self.assertFalse(response.success)
        self.assertEqual(response.intent, "search")
        self.assertEqual(response.knowledge_results, [])
