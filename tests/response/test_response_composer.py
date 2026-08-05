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
from session.SessionRenameResult import SessionRenameResult


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

    def test_conversation_search_results_preserves_record_order_and_content(
        self,
    ) -> None:
        records = [
            MemoryRecord(
                memory_id="memory-1",
                content="First matching conversation\nwith preserved formatting.",
            ),
            MemoryRecord(
                memory_id="memory-2",
                content="SECOND matching conversation!",
            ),
        ]

        response = self.composer.conversation_search_results(
            self.request,
            records,
            self._session("work-1"),
        )

        self.assertEqual(
            response.message,
            "Conversation matches in work-1:\n"
            "1. First matching conversation\nwith preserved formatting.\n"
            "2. SECOND matching conversation!",
        )
        self.assertEqual(response.intent, "conversation_search")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 2)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_conversation_search_empty_composes_a_successful_response(self) -> None:
        response = self.composer.conversation_search_empty(
            self.request,
            self._session("work-1"),
        )

        self.assertEqual(
            response.message,
            "No matching conversations found in session: work-1",
        )
        self.assertEqual(response.intent, "conversation_search")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_conversation_search_failure_preserves_the_given_message(self) -> None:
        response = self.composer.conversation_search_failure(
            self.request,
            "Search query must not be empty.",
        )

        self.assertEqual(response.message, "Search query must not be empty.")
        self.assertEqual(response.intent, "conversation_search")
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

    def test_session_overview_preserves_registry_order_and_formats_counts(self) -> None:
        sessions = [
            self._session("default"),
            self._session("work-1"),
            self._session("research"),
        ]

        response = self.composer.session_overview(
            self.request,
            sessions,
            {"default": 0, "work-1": 1, "research": 8},
            "work-1",
        )

        self.assertEqual(
            response.message,
            "Sessions:\n"
            "1. default — 0 conversations\n"
            "2. work-1 — 1 conversation [active]\n"
            "3. research — 8 conversations",
        )
        self.assertEqual(response.intent, "session_overview")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 9)
        self.assertEqual(response.request_id, self.request.request_id)
        self.assertEqual(response.message.count("[active]"), 1)

    def test_session_overview_defaults_missing_counts_and_excludes_orphans(
        self,
    ) -> None:
        sessions = [self._session("default"), self._session("work-1")]

        response = self.composer.session_overview(
            self.request,
            sessions,
            {"default": 2, "orphan": 99},
            "default",
        )

        self.assertEqual(
            response.message,
            "Sessions:\n"
            "1. default — 2 conversations [active]\n"
            "2. work-1 — 0 conversations",
        )
        self.assertEqual(response.memory_count, 2)

    def test_session_overview_handles_an_empty_registry_deterministically(self) -> None:
        response = self.composer.session_overview(
            self.request,
            [],
            {"orphan": 99},
            "work-1",
        )

        self.assertEqual(response.message, "Sessions:\n")
        self.assertEqual(response.intent, "session_overview")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_session_details_composes_an_active_session_without_reformatting_time(
        self,
    ) -> None:
        session = SessionRecord(
            session_id="work-1",
            created_at=datetime(2026, 8, 5, 9, 10, tzinfo=UTC),
        )

        response = self.composer.session_details(
            self.request,
            session,
            conversation_count=1,
            is_active=True,
        )

        self.assertEqual(
            response.message,
            "Session: work-1\n"
            "Status: active\n"
            "Conversations: 1 conversation\n"
            "Created: 2026-08-05T09:10:00+00:00",
        )
        self.assertEqual(response.intent, "session_details")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 1)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_session_details_composes_an_inactive_session_with_plural_count(
        self,
    ) -> None:
        response = self.composer.session_details(
            self.request,
            self._session("research"),
            conversation_count=3,
            is_active=False,
        )

        self.assertEqual(
            response.message,
            "Session: research\n"
            "Status: inactive\n"
            "Conversations: 3 conversations\n"
            "Created: 2026-08-04T15:00:00+00:00",
        )
        self.assertEqual(response.memory_count, 3)

    def test_session_details_failure_preserves_the_given_message(self) -> None:
        response = self.composer.session_details_failure(
            self.request,
            "Session ID must not be empty.",
        )

        self.assertEqual(response.message, "Session ID must not be empty.")
        self.assertEqual(response.intent, "session_details")
        self.assertFalse(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_session_activity_composes_the_given_activity_values(self) -> None:
        first_activity = datetime(2026, 8, 5, 10, 0, tzinfo=UTC)
        last_activity = datetime(2026, 8, 4, 9, 0, tzinfo=UTC)

        response = self.composer.session_activity(
            self.request,
            self._session("Work Research"),
            conversation_count=24,
            first_activity=first_activity,
            last_activity=last_activity,
        )

        self.assertEqual(
            response.message,
            "Session: Work Research\n"
            "Conversations: 24\n"
            "First activity: 2026-08-05T10:00:00+00:00\n"
            "Last activity: 2026-08-04T09:00:00+00:00",
        )
        self.assertEqual(response.intent, "session_activity")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 24)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_session_activity_renders_empty_sessions_successfully(self) -> None:
        response = self.composer.session_activity(
            self.request,
            self._session("empty-session"),
            conversation_count=0,
            first_activity=None,
            last_activity=None,
        )

        self.assertEqual(
            response.message,
            "Session: empty-session\n"
            "Conversations: 0\n"
            "First activity: none\n"
            "Last activity: none",
        )
        self.assertEqual(response.intent, "session_activity")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_session_activity_failure_preserves_the_given_message(self) -> None:
        response = self.composer.session_activity_failure(
            self.request,
            "Session ID must not be empty.",
        )

        self.assertEqual(response.message, "Session ID must not be empty.")
        self.assertEqual(response.intent, "session_activity")
        self.assertFalse(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_session_recent_preserves_record_order_and_content(self) -> None:
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

        response = self.composer.session_recent(
            self.request,
            records,
            self._session("Work Research"),
        )

        self.assertEqual(
            response.message,
            "Recent conversations in Work Research:\n"
            "1. First conversation\nwith preserved formatting.\n"
            "2. SECOND conversation!",
        )
        self.assertEqual(response.intent, "session_recent")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 2)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_session_recent_empty_composes_a_successful_response(self) -> None:
        response = self.composer.session_recent_empty(
            self.request,
            self._session("work-1"),
        )

        self.assertEqual(response.message, "No conversations found in session: work-1")
        self.assertEqual(response.intent, "session_recent")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_session_recent_failure_preserves_the_given_message(self) -> None:
        response = self.composer.session_recent_failure(
            self.request,
            "Session ID must not be empty.",
        )

        self.assertEqual(response.message, "Session ID must not be empty.")
        self.assertEqual(response.intent, "session_recent")
        self.assertFalse(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_session_search_results_preserve_the_given_record_order(self) -> None:
        records = [
            MemoryRecord(
                memory_id="memory-1",
                content="Second timestamp, first relevance result.",
                created_at=datetime(2026, 8, 5, 10, 0, tzinfo=UTC),
            ),
            MemoryRecord(
                memory_id="memory-2",
                content="First timestamp, second relevance result.",
                created_at=datetime(2026, 8, 4, 10, 0, tzinfo=UTC),
            ),
        ]

        response = self.composer.session_search_results(
            self.request,
            self._session("Work Research"),
            "Persistence Contract",
            records,
        )

        self.assertEqual(
            response.message,
            'Conversation matches in Work Research for "Persistence Contract":\n'
            "1. Second timestamp, first relevance result.\n"
            "2. First timestamp, second relevance result.",
        )
        self.assertEqual(response.intent, "session_search")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 2)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_session_search_empty_composes_a_successful_response(self) -> None:
        response = self.composer.session_search_empty(
            self.request,
            self._session("work research"),
            "persistence contract",
        )

        self.assertEqual(
            response.message,
            "No matching conversations found in session work research for: "
            "persistence contract",
        )
        self.assertEqual(response.intent, "session_search")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_session_search_failure_preserves_the_given_message(self) -> None:
        response = self.composer.session_search_failure(
            self.request,
            "Search query separator is required: --",
        )

        self.assertEqual(response.message, "Search query separator is required: --")
        self.assertEqual(response.intent, "session_search")
        self.assertFalse(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_session_rename_responses_preserve_the_exact_contract(self) -> None:
        result = SessionRenameResult("work", "Research Archive", 2, True)

        response = self.composer.session_renamed(self.request, result)
        failure = self.composer.session_rename_failure(
            self.request,
            "Default session cannot be renamed.",
        )

        self.assertEqual(
            response.message,
            "Session renamed: work -> Research Archive\nMemory records updated: 2",
        )
        self.assertEqual(response.intent, "session_rename")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 2)
        self.assertEqual(response.request_id, self.request.request_id)
        self.assertEqual(failure.message, "Default session cannot be renamed.")
        self.assertEqual(failure.intent, "session_rename")
        self.assertFalse(failure.success)
        self.assertEqual(failure.memory_count, 0)

    @staticmethod
    def _session(session_id: str) -> SessionRecord:
        return SessionRecord(
            session_id=session_id,
            created_at=datetime(2026, 8, 4, 15, 0, tzinfo=UTC),
        )
