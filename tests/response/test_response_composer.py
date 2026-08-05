"""Unit tests for ResponseComposer."""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
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
from memory.MemoryRecord import MemoryRecord
from planner.Planner import Planner
from response.ResponseComposer import ResponseComposer
from session.SessionRecord import SessionRecord


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

    def test_recall_success_with_no_records_returns_a_successful_empty_response(
        self,
    ) -> None:
        response = self.composer.recall_success(self.request, [])

        self.assertEqual(response.message, "No matching conversation records found.")
        self.assertEqual(response.intent, "recall")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_recall_success_numbers_a_single_record_without_changing_content(
        self,
    ) -> None:
        record = MemoryRecord(
            memory_id="memory-1",
            content="User: cats\nHypatia: Cats are animals.",
        )

        response = self.composer.recall_success(self.request, [record])

        self.assertEqual(
            response.message,
            "Matching conversation records:\n\n"
            "1. User: cats\nHypatia: Cats are animals.",
        )
        self.assertEqual(response.memory_count, 1)

    def test_recall_success_preserves_multiple_record_order(self) -> None:
        records = [
            MemoryRecord(memory_id="memory-1", content="User: first"),
            MemoryRecord(memory_id="memory-2", content="User: second"),
        ]

        response = self.composer.recall_success(self.request, records)

        self.assertEqual(
            response.message,
            "Matching conversation records:\n\n1. User: first\n\n2. User: second",
        )
        self.assertEqual(response.memory_count, 2)

    def test_recall_failure_preserves_the_given_message(self) -> None:
        response = self.composer.recall_failure(
            self.request,
            "A recall query is required.",
        )

        self.assertEqual(response.message, "A recall query is required.")
        self.assertEqual(response.intent, "recall")
        self.assertFalse(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_recent_conversations_preserves_record_order_and_content(self) -> None:
        records = [
            MemoryRecord(
                memory_id="memory-1",
                content="First conversation\nwith preserved formatting.",
            ),
            MemoryRecord(
                memory_id="memory-2",
                content="SECOND conversation!",
            ),
        ]

        response = self.composer.recent_conversations(
            self.request,
            records,
            self._session("work-1"),
        )

        self.assertEqual(
            response.message,
            "Recent conversations in work-1:\n"
            "1. First conversation\nwith preserved formatting.\n"
            "2. SECOND conversation!",
        )
        self.assertEqual(response.intent, "recent_conversations")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 2)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_recent_conversations_empty_composes_a_successful_response(self) -> None:
        response = self.composer.recent_conversations_empty(
            self.request,
            self._session("work-1"),
        )

        self.assertEqual(response.message, "No conversations found in session: work-1")
        self.assertEqual(response.intent, "recent_conversations")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_recent_conversations_failure_preserves_the_given_message(self) -> None:
        response = self.composer.recent_conversations_failure(
            self.request,
            "Count must be an integer.",
        )

        self.assertEqual(response.message, "Count must be an integer.")
        self.assertEqual(response.intent, "recent_conversations")
        self.assertFalse(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_session_created_composes_the_expected_response(self) -> None:
        response = self.composer.session_created(self.request, self._session("work-1"))

        self.assertEqual(response.message, "Session created: work-1")
        self.assertEqual(response.intent, "session_create")
        self.assertTrue(response.success)
        self.assertEqual(response.request_id, self.request.request_id)
        self.assertEqual(response.memory_count, 0)

    def test_session_exists_composes_the_expected_response(self) -> None:
        response = self.composer.session_exists(self.request, self._session("work-1"))

        self.assertEqual(response.message, "Session already exists: work-1")
        self.assertEqual(response.intent, "session_create")
        self.assertTrue(response.success)

    def test_session_activated_composes_the_expected_response(self) -> None:
        response = self.composer.session_activated(
            self.request, self._session("work-1")
        )

        self.assertEqual(response.message, "Active session: work-1")
        self.assertEqual(response.intent, "session_use")
        self.assertTrue(response.success)

    def test_session_failure_preserves_the_given_message(self) -> None:
        response = self.composer.session_failure(
            self.request,
            "Unknown session: work-1",
        )

        self.assertEqual(response.message, "Unknown session: work-1")
        self.assertEqual(response.intent, "session")
        self.assertFalse(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_sessions_list_preserves_order_and_marks_only_the_active_session(
        self,
    ) -> None:
        sessions = [
            self._session("default"),
            self._session("work-1"),
            self._session("personal"),
        ]

        response = self.composer.sessions_list(
            self.request,
            sessions,
            sessions[1],
        )

        self.assertEqual(
            response.message,
            "Sessions:\n1. default\n2. work-1 (active)\n3. personal",
        )
        self.assertEqual(response.intent, "session_list")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.message.count("(active)"), 1)

    @staticmethod
    def _session(session_id: str) -> SessionRecord:
        return SessionRecord(
            session_id=session_id,
            created_at=datetime(2026, 8, 4, 15, 0, tzinfo=UTC),
        )
