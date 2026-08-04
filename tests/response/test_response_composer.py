"""Unit tests for ResponseComposer."""

from __future__ import annotations

import sys
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
from knowledge.Chunk import Chunk, ChunkType
from planner.Planner import Planner
from response.ResponseComposer import ResponseComposer


class ResponseComposerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.composer = ResponseComposer()
        self.request = BrainRequest(message="hello")

    def test_greeting_composes_the_expected_response(self) -> None:
        response = self.composer.greeting(self.request)

        self.assertEqual(response.message, "Hello! I am Hypatia.")
        self.assertEqual(response.intent, "greeting")
        self.assertTrue(response.success)
        self.assertEqual(response.request_id, self.request.request_id)
        self.assertEqual(response.memory_count, 0)

    def test_message_composes_the_expected_response(self) -> None:
        request = BrainRequest(message="how are you")

        response = self.composer.message(request)

        self.assertEqual(response.message, "I received your message: how are you")
        self.assertEqual(response.intent, "message")
        self.assertTrue(response.success)
        self.assertEqual(response.request_id, request.request_id)
        self.assertEqual(response.memory_count, 0)

    def test_search_success_preserves_results_and_formats_the_count(self) -> None:
        results = [
            Chunk("document", 0, "Hypatia", ChunkType.PARAGRAPH),
            Chunk("document", 1, "Knowledge", ChunkType.PARAGRAPH),
        ]

        response = self.composer.search_success(self.request, results)

        self.assertEqual(response.message, "I found 2 matching knowledge chunks.")
        self.assertEqual(response.intent, "search")
        self.assertTrue(response.success)
        self.assertIs(response.knowledge_results, results)
        self.assertEqual(response.request_id, self.request.request_id)
        self.assertEqual(response.memory_count, 0)

    def test_search_failure_preserves_the_given_message(self) -> None:
        response = self.composer.search_failure(
            self.request,
            "A search query is required.",
        )

        self.assertEqual(response.message, "A search query is required.")
        self.assertEqual(response.intent, "search")
        self.assertFalse(response.success)
        self.assertEqual(response.knowledge_results, [])
        self.assertEqual(response.request_id, self.request.request_id)
        self.assertEqual(response.memory_count, 0)

    def test_plan_success_preserves_goal_and_task_order(self) -> None:
        plan = Planner().create_plan("Read a PDF and summarize it")

        response = self.composer.plan_success(self.request, plan)

        self.assertEqual(response.intent, "plan")
        self.assertTrue(response.success)
        self.assertEqual(
            response.message,
            "Plan created for: Read a PDF and summarize it\n\n"
            "1. Locate file\n"
            "2. Read document\n"
            "3. Extract text\n"
            "4. Summarize\n"
            "5. Return response",
        )
        self.assertEqual(response.request_id, self.request.request_id)
        self.assertEqual(response.memory_count, 0)

    def test_plan_failure_preserves_the_given_message(self) -> None:
        response = self.composer.plan_failure(
            self.request,
            "A planning goal is required.",
        )

        self.assertEqual(response.message, "A planning goal is required.")
        self.assertEqual(response.intent, "plan")
        self.assertFalse(response.success)
        self.assertEqual(response.request_id, self.request.request_id)
        self.assertEqual(response.memory_count, 0)
