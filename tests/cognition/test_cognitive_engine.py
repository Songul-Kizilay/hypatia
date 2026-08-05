"""Unit tests for the first CognitiveEngine implementation."""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

import planner
import response

source_planner_dir = str(SRC_DIR / "planner")
if source_planner_dir not in planner.__path__:
    planner.__path__.append(source_planner_dir)

source_response_dir = str(SRC_DIR / "response")
if source_response_dir not in response.__path__:
    response.__path__.append(source_response_dir)

from brain.BrainRequest import BrainRequest
from cognition.CognitiveEngine import CognitiveEngine as ProductionCognitiveEngine
from core.Exceptions import KnowledgeError, MemoryError, PlannerError
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.MemoryManager import MemoryManager
from memory.MemoryRecord import MemoryRecord
from memory.SessionMemoryPolicy import SessionMemoryPolicy
from planner.Planner import Planner
from response.ResponseComposer import ResponseComposer
from session.SessionManager import SessionManager
from session.SessionRenameTransactionService import SessionRenameTransactionService


class StubSessionRenameService:
    """Fails tests that accidentally route an unrelated request to rename."""

    def rename(self, source_session_id: str, target_session_id: str) -> object:
        raise AssertionError("Session rename service must not be called in this test.")


class CognitiveEngine(ProductionCognitiveEngine):
    """Test harness that supplies the required rename dependency when omitted."""

    def __init__(self, *args: object) -> None:
        if len(args) == 6:
            super().__init__(*args, StubSessionRenameService())  # type: ignore[arg-type]
            return
        super().__init__(*args)  # type: ignore[arg-type]


class FailingKnowledgeEngine:
    """Minimal failure double for KnowledgeError handling coverage."""

    def search(self, query: str) -> list[object]:
        raise KnowledgeError("Knowledge is unavailable.")


class FailingMemoryManager:
    """Minimal failure double that preserves search response behavior."""

    def add(self, *args: object, **kwargs: object) -> None:
        raise MemoryError("Memory is unavailable.")


class RecallSearchMustNotRunMemoryManager:
    """Minimal double that fails if invalid recall attempts a memory search."""

    def search(self, *args: object, **kwargs: object) -> list[MemoryRecord]:
        raise AssertionError("Recall search must not run.")


class RecentConversationsMustNotReadMemoryManager:
    """Minimal double that fails when an invalid request reads memory."""

    def all(self) -> list[MemoryRecord]:
        raise AssertionError("Recent conversations must not read memory.")


class KnowledgeSearchMustNotRun:
    """Minimal double that fails when conversation search reaches knowledge."""

    def search(self, query: str) -> list[object]:
        raise AssertionError("Knowledge search must not run.")


class RecordingConversationSearchMemoryManager:
    """Minimal double that preserves a caller-provided relevance order."""

    def __init__(self, records: list[MemoryRecord]) -> None:
        self.records = records
        self.calls: list[tuple[str, int | None]] = []

    def search(self, query: str, *, limit: int | None) -> list[MemoryRecord]:
        self.calls.append((query, limit))
        return list(self.records)


class SessionSearchMustNotReadMemoryManager:
    """Minimal double that fails if invalid session search reads memory."""

    def all(self) -> list[MemoryRecord]:
        raise AssertionError("Session search must not read all memory records.")

    def search(self, *args: object, **kwargs: object) -> list[MemoryRecord]:
        raise AssertionError("Invalid session search must not run.")


class SessionActivityMustNotReadMemoryManager:
    """Minimal double that fails if invalid session activity reads memory."""

    def all(self) -> list[MemoryRecord]:
        raise AssertionError(
            "Invalid session activity must not read all memory records."
        )

    def search(self, *args: object, **kwargs: object) -> list[MemoryRecord]:
        raise AssertionError("Invalid session activity must not run a memory search.")


class RecordingSessionOverviewMemoryManager:
    """Minimal double that records read-only session overview access."""

    def __init__(self, records: list[MemoryRecord]) -> None:
        self.records = records
        self.all_calls = 0

    def all(self) -> list[MemoryRecord]:
        self.all_calls += 1
        return list(self.records)


class SessionOverviewMustNotResolveEngine(CognitiveEngine):
    """Fails the test if session overview attempts request-level resolution."""

    def _resolve_session_id(self, request: BrainRequest) -> str:
        raise AssertionError("Session overview must not resolve a session ID.")


class SessionDetailsMustNotResolveEngine(CognitiveEngine):
    """Fails the test if session details attempts request-level resolution."""

    def _resolve_session_id(self, request: BrainRequest) -> str:
        raise AssertionError("Session details must not resolve a session ID.")


class SessionRecentMustNotResolveEngine(CognitiveEngine):
    """Fails the test if session recent attempts request-level resolution."""

    def _resolve_session_id(self, request: BrainRequest) -> str:
        raise AssertionError("Session recent must not resolve a session ID.")


class SessionSearchMustNotResolveEngine(CognitiveEngine):
    """Fails the test if session search attempts request-level resolution."""

    def _resolve_session_id(self, request: BrainRequest) -> str:
        raise AssertionError("Session search must not resolve a session ID.")


class SessionActivityMustNotResolveEngine(CognitiveEngine):
    """Fails the test if session activity attempts request-level resolution."""

    def _resolve_session_id(self, request: BrainRequest) -> str:
        raise AssertionError("Session activity must not resolve a session ID.")


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
        self.event_bus = EventBus()
        self.memory_manager = MemoryManager(self.event_bus)
        self.planner = Planner()
        self.response_composer = ResponseComposer()
        self.session_manager = SessionManager(self.event_bus)
        self.session_manager.create("work-1")
        self.session_manager.create("personal")
        self.session_rename_service = SessionRenameTransactionService(
            session_manager=self.session_manager,
            memory_manager=self.memory_manager,
            event_bus=self.event_bus,
        )
        self.engine = CognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_search_intent_returns_a_successful_response(self) -> None:
        response = self.engine.process(BrainRequest(message="search hypatia"))

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "search")

    def test_session_manager_is_a_required_cognitive_engine_dependency(self) -> None:
        with self.assertRaises(TypeError):
            ProductionCognitiveEngine(
                self.knowledge_engine,
                self.memory_manager,
                self.planner,
                self.event_bus,
                self.response_composer,
            )

    def test_session_rename_service_is_a_required_cognitive_engine_dependency(
        self,
    ) -> None:
        with self.assertRaises(TypeError):
            ProductionCognitiveEngine(
                self.knowledge_engine,
                self.memory_manager,
                self.planner,
                self.event_bus,
                self.response_composer,
                self.session_manager,
            )

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

    def test_session_rename_executes_without_conversation_side_effects(self) -> None:
        self.memory_manager.add("Work", metadata={"session_id": "work-1"})
        events = []
        self.event_bus.subscribe("*", events.append)

        response = self.engine.process(
            BrainRequest(message="  RENAME SESSION work-1 -- Work Archive  ")
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "session_rename")
        self.assertEqual(
            response.message,
            "Session renamed: work-1 -> Work Archive\nMemory records updated: 1",
        )
        self.assertTrue(self.session_manager.exists("Work Archive"))
        self.assertFalse(self.session_manager.exists("work-1"))
        self.assertEqual(
            self.memory_manager.snapshot()[0].metadata["session_id"],
            "Work Archive",
        )
        self.assertEqual([event.name for event in events], ["session.renamed"])

    def test_session_rename_parser_and_domain_failures_are_controlled(self) -> None:
        for message, expected in (
            ("rename session work", "Session rename separator is required: --"),
            ("rename session -- work", "Session source ID must not be empty."),
            ("rename session work --", "Session target ID must not be empty."),
            ("rename session default -- other", "Default session cannot be renamed."),
        ):
            with self.subTest(message=message):
                response = self.engine.process(BrainRequest(message=message))
                self.assertFalse(response.success)
                self.assertEqual(response.intent, "session_rename")
                self.assertEqual(response.memory_count, 0)
                self.assertEqual(response.message, expected)

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

    def test_greeting_is_processed_as_a_conversation(self) -> None:
        response = self.engine.process(BrainRequest(message="hello"))

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "greeting")
        self.assertEqual(response.message, "Hello! I am Hypatia.")

    def test_message_is_processed_as_a_conversation(self) -> None:
        response = self.engine.process(BrainRequest(message="how are you"))

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "message")
        self.assertEqual(response.message, "I received your message: how are you")
        self.assertEqual(len(self.memory_manager.all()), 1)

    def test_conversation_without_a_session_id_uses_the_default_session(self) -> None:
        self.engine.process(BrainRequest(message="hello"))

        self.assertEqual(
            self.memory_manager.all()[0].metadata["session_id"],
            "default",
        )

    def test_none_empty_and_whitespace_session_ids_use_the_default_session(
        self,
    ) -> None:
        for session_id in (None, "", "   "):
            with self.subTest(session_id=session_id):
                self.memory_manager.clear()
                self.engine.process(
                    BrainRequest(message="hello", metadata={"session_id": session_id})
                )

                self.assertEqual(
                    self.memory_manager.all()[0].metadata["session_id"],
                    "default",
                )

    def test_conversation_normalizes_a_string_session_id_without_mutating_request(
        self,
    ) -> None:
        metadata = {"session_id": "  work-1  "}
        request = BrainRequest(message="hello", metadata=metadata)

        self.engine.process(request)

        self.assertEqual(self.memory_manager.all()[0].metadata["session_id"], "work-1")
        self.assertEqual(metadata, {"session_id": "  work-1  "})

    def test_non_string_session_id_returns_a_controlled_failure_without_side_effects(
        self,
    ) -> None:
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))

        response = self.engine.process(
            BrainRequest(message="hello", metadata={"session_id": 123})
        )

        self.assertFalse(response.success)
        self.assertEqual(response.message, "session_id must be a string.")
        self.assertEqual(self.memory_manager.count(), 0)
        self.assertEqual(events, [])

    def test_create_session_uses_the_registry_without_conversation_side_effects(
        self,
    ) -> None:
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))

        response = self.engine.process(BrainRequest(message="create session Work-2"))

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "session_create")
        self.assertEqual(response.message, "Session created: Work-2")
        self.assertTrue(self.session_manager.exists("Work-2"))
        self.assertEqual(self.memory_manager.count(), 0)
        self.assertEqual(events, ["session.created"])

    def test_duplicate_session_create_returns_an_exists_response_without_side_effects(
        self,
    ) -> None:
        self.session_manager.create("work-2")
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))

        response = self.engine.process(BrainRequest(message="create session work-2"))

        self.assertTrue(response.success)
        self.assertEqual(response.message, "Session already exists: work-2")
        self.assertEqual(self.memory_manager.count(), 0)
        self.assertEqual(events, [])

    def test_list_sessions_preserves_order_and_marks_the_active_session(self) -> None:
        response = self.engine.process(BrainRequest(message="list sessions"))

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "session_list")
        self.assertEqual(
            response.message,
            "Sessions:\n1. default (active)\n2. work-1\n3. personal",
        )
        self.assertEqual(self.memory_manager.count(), 0)

    def test_use_session_activates_an_existing_session_without_memory_writes(
        self,
    ) -> None:
        response = self.engine.process(BrainRequest(message="use session work-1"))

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "session_use")
        self.assertEqual(response.message, "Active session: work-1")
        self.assertEqual(self.session_manager.get_active().session_id, "work-1")
        self.assertEqual(self.memory_manager.count(), 0)

    def test_use_unknown_session_returns_a_controlled_failure(self) -> None:
        response = self.engine.process(BrainRequest(message="use session unknown"))

        self.assertFalse(response.success)
        self.assertEqual(response.message, "Unknown session: unknown")
        self.assertEqual(self.session_manager.get_active().session_id, "default")
        self.assertEqual(self.memory_manager.count(), 0)

    def test_session_overview_counts_only_registered_normal_conversations(
        self,
    ) -> None:
        records = (
            ("Legacy default", {}, {"brain", "conversation"}),
            (
                "Default with extra tag",
                {"session_id": "default"},
                {"brain", "conversation", "extra"},
            ),
            ("Work conversation", {"session_id": "work-1"}, {"brain", "conversation"}),
            (
                "Personal conversation",
                {"session_id": "personal"},
                {"brain", "conversation"},
            ),
            ("None session", {"session_id": None}, {"brain", "conversation"}),
            ("Numeric session", {"session_id": 123}, {"brain", "conversation"}),
            ("Orphan session", {"session_id": "orphan"}, {"brain", "conversation"}),
            ("Brain only", {"session_id": "default"}, {"brain"}),
            ("Conversation only", {"session_id": "default"}, {"conversation"}),
            ("Plan record", {"session_id": "default"}, {"brain", "plan"}),
            (
                "Knowledge search record",
                {"session_id": "default"},
                {"conversation", "knowledge-search"},
            ),
        )
        for content, metadata, tags in records:
            self.memory_manager.add(content, metadata=metadata, tags=tags)
        self.session_manager.set_active("work-1")
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))
        memory_count = self.memory_manager.count()

        for metadata in (
            {},
            {"session_id": "personal"},
            {"session_id": 123},
            {"session_id": None},
            {"session_id": ""},
        ):
            with self.subTest(metadata=metadata):
                response = self.engine.process(
                    BrainRequest(message="session overview", metadata=metadata)
                )

                self.assertTrue(response.success)
                self.assertEqual(response.intent, "session_overview")
                self.assertEqual(
                    response.message,
                    "Sessions:\n"
                    "1. default — 2 conversations\n"
                    "2. work-1 — 1 conversation [active]\n"
                    "3. personal — 1 conversation",
                )
                self.assertEqual(response.memory_count, 4)
                self.assertEqual(self.memory_manager.count(), memory_count)
                self.assertEqual(self.session_manager.get_active().session_id, "work-1")

        self.assertEqual(events, [])

    def test_session_overview_reads_memory_once_without_resolving_request_session(
        self,
    ) -> None:
        memory_manager = RecordingSessionOverviewMemoryManager(
            [
                MemoryRecord(
                    memory_id="default-record",
                    content="Legacy default",
                    tags=frozenset({"brain", "conversation"}),
                )
            ]
        )
        engine = SessionOverviewMustNotResolveEngine(
            self.knowledge_engine,
            memory_manager,  # type: ignore[arg-type]
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        response = engine.process(
            BrainRequest(message="session overview", metadata={"session_id": 123})
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "session_overview")
        self.assertEqual(memory_manager.all_calls, 1)
        self.assertIn("1. default — 1 conversation [active]", response.message)

    def test_session_overview_delegates_record_matching_to_the_shared_policy(
        self,
    ) -> None:
        record = MemoryRecord(
            memory_id="default-record",
            content="Legacy default",
            tags=frozenset({"brain", "conversation"}),
        )
        memory_manager = RecordingSessionOverviewMemoryManager([record])
        engine = CognitiveEngine(
            self.knowledge_engine,
            memory_manager,  # type: ignore[arg-type]
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        with patch.object(
            SessionMemoryPolicy,
            "matches",
            wraps=SessionMemoryPolicy.matches,
        ) as matches:
            response = engine.process(BrainRequest(message="session overview"))

        self.assertTrue(response.success)
        self.assertEqual(memory_manager.all_calls, 1)
        matches.assert_called_once_with(record, "default")

    def test_session_details_counts_only_target_normal_conversations(self) -> None:
        records = (
            (
                "Target conversation",
                {"session_id": "work-1"},
                {"brain", "conversation"},
            ),
            (
                "Target with extra tag",
                {"session_id": "work-1"},
                {"brain", "conversation", "extra"},
            ),
            ("Other session", {"session_id": "personal"}, {"brain", "conversation"}),
            ("None session", {"session_id": None}, {"brain", "conversation"}),
            ("Orphan session", {"session_id": "orphan"}, {"brain", "conversation"}),
            (
                "Search record",
                {"session_id": "work-1"},
                {"cognition", "knowledge-search", "conversation"},
            ),
            ("Plan record", {"session_id": "work-1"}, {"brain", "plan"}),
        )
        for content, metadata, tags in records:
            self.memory_manager.add(content, metadata=metadata, tags=tags)
        self.session_manager.set_active("personal")
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))
        memory_count = self.memory_manager.count()

        response = self.engine.process(
            BrainRequest(
                message="session details work-1",
                metadata={"session_id": 123},
            )
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "session_details")
        self.assertIn("Session: work-1", response.message)
        self.assertIn("Status: inactive", response.message)
        self.assertIn("Conversations: 2 conversations", response.message)
        self.assertEqual(response.memory_count, 2)
        self.assertEqual(self.memory_manager.count(), memory_count)
        self.assertEqual(self.session_manager.get_active().session_id, "personal")
        self.assertEqual(events, [])

    def test_session_details_treats_only_missing_session_metadata_as_default(
        self,
    ) -> None:
        self.memory_manager.add(
            "Legacy default",
            tags={"brain", "conversation"},
        )
        self.memory_manager.add(
            "Null default",
            metadata={"session_id": None},
            tags={"brain", "conversation"},
        )

        response = self.engine.process(BrainRequest(message="session details default"))

        self.assertEqual(response.memory_count, 1)
        self.assertIn("Conversations: 1 conversation", response.message)

    def test_session_details_reads_memory_once_without_resolving_request_session(
        self,
    ) -> None:
        memory_manager = RecordingSessionOverviewMemoryManager(
            [
                MemoryRecord(
                    memory_id="work-record",
                    content="Work conversation",
                    metadata={"session_id": "work-1"},
                    tags=frozenset({"brain", "conversation"}),
                )
            ]
        )
        engine = SessionDetailsMustNotResolveEngine(
            self.knowledge_engine,
            memory_manager,  # type: ignore[arg-type]
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        response = engine.process(
            BrainRequest(
                message="SESSION DETAILS work-1",
                metadata={"session_id": 123},
            )
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "session_details")
        self.assertEqual(memory_manager.all_calls, 1)
        self.assertIn("Session: work-1", response.message)

    def test_session_details_empty_and_unknown_ids_do_not_read_memory(self) -> None:
        engine = CognitiveEngine(
            self.knowledge_engine,
            RecentConversationsMustNotReadMemoryManager(),  # type: ignore[arg-type]
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        for message, expected in (
            ("session details", "Session ID must not be empty."),
            ("session details unknown", "Unknown session: unknown"),
        ):
            with self.subTest(message=message):
                response = engine.process(BrainRequest(message=message))

                self.assertFalse(response.success)
                self.assertEqual(response.intent, "session_details")
                self.assertEqual(response.message, expected)

    def test_session_details_delegates_record_matching_to_the_shared_policy(
        self,
    ) -> None:
        record = MemoryRecord(
            memory_id="work-record",
            content="Work conversation",
            metadata={"session_id": "work-1"},
            tags=frozenset({"brain", "conversation"}),
        )
        memory_manager = RecordingSessionOverviewMemoryManager([record])
        engine = CognitiveEngine(
            self.knowledge_engine,
            memory_manager,  # type: ignore[arg-type]
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        with patch.object(
            SessionMemoryPolicy,
            "matches",
            wraps=SessionMemoryPolicy.matches,
        ) as matches:
            response = engine.process(BrainRequest(message="session details work-1"))

        self.assertTrue(response.success)
        self.assertEqual(memory_manager.all_calls, 1)
        matches.assert_called_once_with(record, "work-1")

    def test_session_activity_aggregates_only_target_conversations(self) -> None:
        self.session_manager.create("Work Research")
        self.session_manager.set_active("personal")
        records = [
            MemoryRecord(
                memory_id="middle",
                content="Middle activity",
                metadata={"session_id": "Work Research"},
                tags=frozenset({"brain", "conversation"}),
                created_at=datetime(2026, 8, 5, 10, 0, tzinfo=UTC),
            ),
            MemoryRecord(
                memory_id="newest",
                content="Newest activity",
                metadata={"session_id": "Work Research"},
                tags=frozenset({"brain", "conversation", "extra"}),
                created_at=datetime(2026, 8, 6, 10, 0, tzinfo=UTC),
            ),
            MemoryRecord(
                memory_id="oldest",
                content="Oldest activity",
                metadata={"session_id": "Work Research"},
                tags=frozenset({"brain", "conversation"}),
                created_at=datetime(2026, 8, 4, 10, 0, tzinfo=UTC),
            ),
            MemoryRecord(
                memory_id="other",
                content="Other session",
                metadata={"session_id": "personal"},
                tags=frozenset({"brain", "conversation"}),
            ),
            MemoryRecord(
                memory_id="none",
                content="None session",
                metadata={"session_id": None},
                tags=frozenset({"brain", "conversation"}),
            ),
            MemoryRecord(
                memory_id="orphan",
                content="Orphan session",
                metadata={"session_id": "orphan"},
                tags=frozenset({"brain", "conversation"}),
            ),
            MemoryRecord(
                memory_id="search",
                content="Knowledge record",
                metadata={"session_id": "Work Research"},
                tags=frozenset({"cognition", "knowledge-search", "conversation"}),
            ),
        ]
        memory_manager = RecordingSessionOverviewMemoryManager(records)
        engine = SessionActivityMustNotResolveEngine(
            self.knowledge_engine,
            memory_manager,  # type: ignore[arg-type]
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        response = engine.process(
            BrainRequest(
                message="SESSION ACTIVITY Work Research",
                metadata={"session_id": 123, "intent": "search"},
            )
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "session_activity")
        self.assertEqual(memory_manager.all_calls, 1)
        self.assertEqual(response.memory_count, 3)
        self.assertIn("Session: Work Research", response.message)
        self.assertIn("First activity: 2026-08-04T10:00:00+00:00", response.message)
        self.assertIn("Last activity: 2026-08-06T10:00:00+00:00", response.message)
        self.assertEqual(self.session_manager.get_active().session_id, "personal")

    def test_session_activity_treats_only_missing_metadata_as_default(self) -> None:
        self.memory_manager.add("Legacy default", tags={"brain", "conversation"})
        self.memory_manager.add(
            "Explicit default",
            metadata={"session_id": "default"},
            tags={"brain", "conversation"},
        )
        self.memory_manager.add(
            "Null default",
            metadata={"session_id": None},
            tags={"brain", "conversation"},
        )
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))
        memory_count = self.memory_manager.count()

        response = self.engine.process(BrainRequest(message="session activity default"))

        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 2)
        self.assertEqual(self.memory_manager.count(), memory_count)
        self.assertEqual(events, [])

    def test_session_activity_empty_and_unknown_ids_do_not_read_memory(self) -> None:
        engine = CognitiveEngine(
            self.knowledge_engine,
            SessionActivityMustNotReadMemoryManager(),  # type: ignore[arg-type]
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        for message, expected in (
            ("session activity", "Session ID must not be empty."),
            ("session activity unknown", "Unknown session: unknown"),
        ):
            with self.subTest(message=message):
                response = engine.process(BrainRequest(message=message))

                self.assertFalse(response.success)
                self.assertEqual(response.intent, "session_activity")
                self.assertEqual(response.message, expected)

    def test_session_activity_empty_registered_session_is_successful(self) -> None:
        self.session_manager.create("empty-session")
        memory_manager = RecordingSessionOverviewMemoryManager([])
        engine = CognitiveEngine(
            self.knowledge_engine,
            memory_manager,  # type: ignore[arg-type]
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        response = engine.process(
            BrainRequest(message="session activity empty-session")
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "session_activity")
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(memory_manager.all_calls, 1)
        self.assertIn("First activity: none", response.message)
        self.assertIn("Last activity: none", response.message)

    def test_session_activity_delegates_record_matching_to_the_shared_policy(
        self,
    ) -> None:
        record = MemoryRecord(
            memory_id="work-record",
            content="Work conversation",
            metadata={"session_id": "work"},
            tags=frozenset({"brain", "conversation"}),
            created_at=datetime.now(UTC),
        )
        self.session_manager.create("work")
        memory_manager = RecordingSessionOverviewMemoryManager([record])
        engine = CognitiveEngine(
            self.knowledge_engine,
            memory_manager,  # type: ignore[arg-type]
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        with patch.object(
            SessionMemoryPolicy,
            "matches",
            wraps=SessionMemoryPolicy.matches,
        ) as matches:
            response = engine.process(BrainRequest(message="session activity work"))

        self.assertTrue(response.success)
        self.assertEqual(memory_manager.all_calls, 1)
        matches.assert_called_once_with(record, "work")

    def test_session_recent_uses_the_complete_suffix_and_filters_before_limiting(
        self,
    ) -> None:
        self.session_manager.create("work research")
        now = datetime.now(UTC)
        records = [
            MemoryRecord(
                memory_id=f"target-{index}",
                content=f"Target conversation {index}",
                metadata={"session_id": "work research"},
                tags=frozenset({"brain", "conversation"}),
                created_at=now + timedelta(seconds=index),
            )
            for index in range(6)
        ]
        records.extend(
            [
                MemoryRecord(
                    memory_id="other-session",
                    content="Other session",
                    metadata={"session_id": "work-1"},
                    tags=frozenset({"brain", "conversation"}),
                    created_at=now + timedelta(minutes=1),
                ),
                MemoryRecord(
                    memory_id="search-record",
                    content="Search record",
                    metadata={"session_id": "work research"},
                    tags=frozenset({"cognition", "knowledge-search", "conversation"}),
                    created_at=now + timedelta(minutes=2),
                ),
                MemoryRecord(
                    memory_id="null-record",
                    content="Null record",
                    metadata={"session_id": None},
                    tags=frozenset({"brain", "conversation"}),
                    created_at=now + timedelta(minutes=3),
                ),
            ]
        )
        memory_manager = RecordingSessionOverviewMemoryManager(records)
        engine = SessionRecentMustNotResolveEngine(
            self.knowledge_engine,
            memory_manager,  # type: ignore[arg-type]
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        response = engine.process(
            BrainRequest(
                message="SESSION RECENT work research",
                metadata={"session_id": 123},
            )
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "session_recent")
        self.assertEqual(memory_manager.all_calls, 1)
        self.assertEqual(response.memory_count, 5)
        self.assertIn("1. Target conversation 5", response.message)
        self.assertIn("5. Target conversation 1", response.message)
        self.assertNotIn("Target conversation 0", response.message)
        self.assertNotIn("Other session", response.message)
        self.assertNotIn("Search record", response.message)
        self.assertNotIn("Null record", response.message)

    def test_session_recent_treats_only_missing_session_metadata_as_default(
        self,
    ) -> None:
        self.memory_manager.add(
            "Legacy default",
            tags={"brain", "conversation"},
        )
        self.memory_manager.add(
            "Null default",
            metadata={"session_id": None},
            tags={"brain", "conversation"},
        )

        response = self.engine.process(BrainRequest(message="session recent default"))

        self.assertEqual(response.memory_count, 1)
        self.assertIn("Legacy default", response.message)
        self.assertNotIn("Null default", response.message)

    def test_session_recent_delegates_record_matching_to_the_shared_policy(
        self,
    ) -> None:
        record = MemoryRecord(
            memory_id="work-record",
            content="Work conversation",
            metadata={"session_id": "work"},
            tags=frozenset({"brain", "conversation"}),
            created_at=datetime.now(UTC),
        )
        self.session_manager.create("work")
        memory_manager = RecordingSessionOverviewMemoryManager([record])
        engine = CognitiveEngine(
            self.knowledge_engine,
            memory_manager,  # type: ignore[arg-type]
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        with patch.object(
            SessionMemoryPolicy,
            "matches",
            wraps=SessionMemoryPolicy.matches,
        ) as matches:
            response = engine.process(BrainRequest(message="session recent work"))

        self.assertTrue(response.success)
        self.assertEqual(memory_manager.all_calls, 1)
        matches.assert_called_once_with(record, "work")

    def test_session_recent_empty_and_unknown_ids_do_not_read_memory(self) -> None:
        engine = CognitiveEngine(
            self.knowledge_engine,
            RecentConversationsMustNotReadMemoryManager(),  # type: ignore[arg-type]
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        for message, expected in (
            ("session recent", "Session ID must not be empty."),
            ("session recent unknown", "Unknown session: unknown"),
        ):
            with self.subTest(message=message):
                response = engine.process(BrainRequest(message=message))

                self.assertFalse(response.success)
                self.assertEqual(response.intent, "session_recent")
                self.assertEqual(response.message, expected)

    def test_session_search_filters_after_relevance_order_without_resolving_request(
        self,
    ) -> None:
        self.session_manager.create("work research")
        records = [
            MemoryRecord(
                memory_id=f"target-{index}",
                content=f"Target relevance {index}",
                metadata={"session_id": "work research"},
                tags=frozenset({"brain", "conversation"}),
                created_at=datetime(2026, 8, 5, 10 - index, tzinfo=UTC),
            )
            for index in range(6)
        ]
        records.extend(
            [
                MemoryRecord(
                    memory_id="other-session",
                    content="Other relevance",
                    metadata={"session_id": "work-1"},
                    tags=frozenset({"brain", "conversation"}),
                ),
                MemoryRecord(
                    memory_id="knowledge-record",
                    content="Knowledge relevance",
                    metadata={"session_id": "work research"},
                    tags=frozenset({"cognition", "knowledge-search", "conversation"}),
                ),
                MemoryRecord(
                    memory_id="null-record",
                    content="Null relevance",
                    metadata={"session_id": None},
                    tags=frozenset({"brain", "conversation"}),
                ),
            ]
        )
        memory_manager = RecordingConversationSearchMemoryManager(records)
        engine = SessionSearchMustNotResolveEngine(
            KnowledgeSearchMustNotRun(),  # type: ignore[arg-type]
            memory_manager,  # type: ignore[arg-type]
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        response = engine.process(
            BrainRequest(
                message="SESSION SEARCH work research -- Persistence Contract",
                metadata={"session_id": 123, "intent": "search"},
            )
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "session_search")
        self.assertEqual(memory_manager.calls, [("Persistence Contract", None)])
        self.assertEqual(response.memory_count, 5)
        self.assertIn("1. Target relevance 0", response.message)
        self.assertIn("5. Target relevance 4", response.message)
        self.assertNotIn("Target relevance 5", response.message)
        self.assertNotIn("Other relevance", response.message)
        self.assertNotIn("Knowledge relevance", response.message)
        self.assertNotIn("Null relevance", response.message)

    def test_session_search_default_target_treats_only_missing_metadata_as_legacy(
        self,
    ) -> None:
        self.memory_manager.add("Legacy match", tags={"brain", "conversation"})
        self.memory_manager.add(
            "Explicit default match",
            metadata={"session_id": "default"},
            tags={"brain", "conversation"},
        )
        self.memory_manager.add(
            "Null match",
            metadata={"session_id": None},
            tags={"brain", "conversation"},
        )

        response = self.engine.process(
            BrainRequest(message="session search default -- match")
        )

        self.assertEqual(response.memory_count, 2)
        self.assertIn("Legacy match", response.message)
        self.assertIn("Explicit default match", response.message)
        self.assertNotIn("Null match", response.message)

    def test_session_search_delegates_record_matching_to_the_shared_policy(
        self,
    ) -> None:
        record = MemoryRecord(
            memory_id="work-record",
            content="Work conversation",
            metadata={"session_id": "work"},
            tags=frozenset({"brain", "conversation"}),
            created_at=datetime.now(UTC),
        )
        self.session_manager.create("work")
        memory_manager = RecordingConversationSearchMemoryManager([record])
        engine = CognitiveEngine(
            self.knowledge_engine,
            memory_manager,  # type: ignore[arg-type]
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        with patch.object(
            SessionMemoryPolicy,
            "matches",
            wraps=SessionMemoryPolicy.matches,
        ) as matches:
            response = engine.process(
                BrainRequest(message="session search work -- conversation")
            )

        self.assertTrue(response.success)
        self.assertEqual(memory_manager.calls, [("conversation", None)])
        matches.assert_called_once_with(record, "work")

    def test_session_search_failures_do_not_read_memory(self) -> None:
        engine = CognitiveEngine(
            KnowledgeSearchMustNotRun(),  # type: ignore[arg-type]
            SessionSearchMustNotReadMemoryManager(),  # type: ignore[arg-type]
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        for message, expected in (
            ("session search work-1", "Search query separator is required: --"),
            ("session search -- persistence", "Session ID must not be empty."),
            ("session search work-1 --", "Search query must not be empty."),
            ("session search unknown -- persistence", "Unknown session: unknown"),
        ):
            with self.subTest(message=message):
                response = engine.process(BrainRequest(message=message))

                self.assertFalse(response.success)
                self.assertEqual(response.intent, "session_search")
                self.assertEqual(response.message, expected)

    def test_active_session_is_used_when_conversation_has_no_session_override(
        self,
    ) -> None:
        self.session_manager.set_active("work-1")

        self.engine.process(BrainRequest(message="hello"))

        self.assertEqual(
            self.memory_manager.all()[0].metadata["session_id"],
            "work-1",
        )

    def test_blank_session_override_uses_the_active_session(self) -> None:
        self.session_manager.set_active("work-1")

        self.engine.process(BrainRequest(message="hello", metadata={"session_id": ""}))

        self.assertEqual(
            self.memory_manager.all()[0].metadata["session_id"],
            "work-1",
        )

    def test_request_session_override_does_not_change_the_active_session(self) -> None:
        self.session_manager.set_active("work-1")

        self.engine.process(
            BrainRequest(message="hello", metadata={"session_id": "default"})
        )

        self.assertEqual(
            self.memory_manager.all()[0].metadata["session_id"],
            "default",
        )
        self.assertEqual(self.session_manager.get_active().session_id, "work-1")

    def test_unknown_session_override_prevents_conversation_side_effects(self) -> None:
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))

        response = self.engine.process(
            BrainRequest(message="hello", metadata={"session_id": "unknown"})
        )

        self.assertFalse(response.success)
        self.assertEqual(response.message, "Unknown session: unknown")
        self.assertEqual(self.memory_manager.count(), 0)
        self.assertEqual(events, [])

    def test_knowledge_error_returns_unsuccessful_response(self) -> None:
        memory_manager = MemoryManager()
        engine = CognitiveEngine(
            FailingKnowledgeEngine(),  # type: ignore[arg-type]
            memory_manager,
            Planner(),
            EventBus(),
            ResponseComposer(),
            SessionManager(),
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
            EventBus(),
            ResponseComposer(),
            SessionManager(),
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
            self.event_bus,
            self.response_composer,
            self.session_manager,
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
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        response = engine.process(BrainRequest(message="plan learn SQL injection"))

        self.assertFalse(response.success)
        self.assertEqual(response.intent, "plan")
        self.assertEqual(response.message, "Planning failed: Planner is unavailable.")

    def test_recall_returns_matching_conversation_records(self) -> None:
        self.memory_manager.add(
            "User: cats\nHypatia: Cats are animals.",
            tags={"brain", "conversation"},
        )

        response = self.engine.process(BrainRequest(message="recall cats"))

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "recall")
        self.assertEqual(response.memory_count, 1)
        self.assertIn("1. User: cats\nHypatia: Cats are animals.", response.message)

    def test_recall_matching_is_case_insensitive(self) -> None:
        self.memory_manager.add(
            "User: Cats\nHypatia: Cats are animals.",
            tags={"brain", "conversation"},
        )

        response = self.engine.process(BrainRequest(message="recall CATS"))

        self.assertEqual(response.memory_count, 1)

    def test_recall_excludes_knowledge_search_records(self) -> None:
        self.memory_manager.add(
            "User: search cats\nHypatia: I found 1 matching knowledge chunks.",
            tags={"cognition", "knowledge-search", "conversation"},
        )
        self.memory_manager.add(
            "User: cats\nHypatia: Cats are animals.",
            tags={"brain", "conversation"},
        )

        response = self.engine.process(BrainRequest(message="recall cats"))

        self.assertEqual(response.memory_count, 1)
        self.assertNotIn("search cats", response.message)
        self.assertIn("Cats are animals.", response.message)

    def test_recall_returns_at_most_the_first_five_matching_records(self) -> None:
        for index in range(6):
            self.memory_manager.add(
                f"User: cats {index}\nHypatia: response {index}",
                tags={"brain", "conversation"},
            )

        response = self.engine.process(BrainRequest(message="recall cats"))

        self.assertEqual(response.memory_count, 5)
        self.assertIn("1. User: cats 0", response.message)
        self.assertIn("5. User: cats 4", response.message)
        self.assertNotIn("cats 5", response.message)

    def test_recall_with_no_matches_returns_a_successful_empty_response(self) -> None:
        response = self.engine.process(BrainRequest(message="recall cats"))

        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.message, "No matching conversation records found.")

    def test_empty_recall_returns_a_controlled_failure(self) -> None:
        response = self.engine.process(BrainRequest(message="recall"))

        self.assertFalse(response.success)
        self.assertEqual(response.intent, "recall")
        self.assertEqual(response.message, "A recall query is required.")

    def test_recall_does_not_create_a_new_memory_record(self) -> None:
        self.memory_manager.add(
            "User: cats\nHypatia: Cats are animals.",
            tags={"brain", "conversation"},
        )

        self.engine.process(BrainRequest(message="recall cats"))

        self.assertEqual(self.memory_manager.count(), 1)

    def test_declared_recall_intent_uses_request_message_as_query(self) -> None:
        self.memory_manager.add(
            "User: cats\nHypatia: Cats are animals.",
            tags={"brain", "conversation"},
        )

        response = self.engine.process(
            BrainRequest(message="cats", metadata={"intent": "recall"})
        )

        self.assertEqual(response.intent, "recall")
        self.assertEqual(response.memory_count, 1)

    def test_recall_word_inside_a_sentence_remains_a_message(self) -> None:
        response = self.engine.process(BrainRequest(message="please recall cats"))

        self.assertEqual(response.intent, "message")
        self.assertEqual(
            response.message,
            "I received your message: please recall cats",
        )

    def test_default_session_recall_includes_legacy_records(self) -> None:
        self.memory_manager.add(
            "User: cats\nHypatia: Legacy conversation.",
            tags={"brain", "conversation"},
        )
        self.memory_manager.add(
            "User: cats\nHypatia: Default conversation.",
            metadata={"session_id": "default"},
            tags={"brain", "conversation"},
        )

        response = self.engine.process(BrainRequest(message="recall cats"))

        self.assertEqual(response.memory_count, 2)
        self.assertIn("Legacy conversation.", response.message)
        self.assertIn("Default conversation.", response.message)

    def test_active_session_is_used_when_recall_has_no_session_override(self) -> None:
        self.memory_manager.add(
            "User: cats\nHypatia: Default conversation.",
            metadata={"session_id": "default"},
            tags={"brain", "conversation"},
        )
        self.memory_manager.add(
            "User: cats\nHypatia: Work conversation.",
            metadata={"session_id": "work-1"},
            tags={"brain", "conversation"},
        )
        self.session_manager.set_active("work-1")

        response = self.engine.process(BrainRequest(message="recall cats"))

        self.assertEqual(response.memory_count, 1)
        self.assertIn("Work conversation.", response.message)
        self.assertNotIn("Default conversation.", response.message)

    def test_recall_session_override_does_not_change_the_active_session(self) -> None:
        self.memory_manager.add(
            "User: cats\nHypatia: Default conversation.",
            metadata={"session_id": "default"},
            tags={"brain", "conversation"},
        )
        self.session_manager.set_active("work-1")

        response = self.engine.process(
            BrainRequest(message="recall cats", metadata={"session_id": "default"})
        )

        self.assertEqual(response.memory_count, 1)
        self.assertIn("Default conversation.", response.message)
        self.assertEqual(self.session_manager.get_active().session_id, "work-1")

    def test_custom_session_recall_returns_only_its_records(self) -> None:
        self.memory_manager.add(
            "User: cats\nHypatia: Default conversation.",
            metadata={"session_id": "default"},
            tags={"brain", "conversation"},
        )
        self.memory_manager.add(
            "User: cats\nHypatia: Work conversation.",
            metadata={"session_id": "work-1"},
            tags={"brain", "conversation"},
        )
        self.memory_manager.add(
            "User: cats\nHypatia: Personal conversation.",
            metadata={"session_id": "personal"},
            tags={"brain", "conversation"},
        )

        response = self.engine.process(
            BrainRequest(message="recall cats", metadata={"session_id": "work-1"})
        )

        self.assertEqual(response.memory_count, 1)
        self.assertIn("Work conversation.", response.message)
        self.assertNotIn("Default conversation.", response.message)
        self.assertNotIn("Personal conversation.", response.message)

    def test_recall_applies_the_limit_after_session_filtering(self) -> None:
        for index in range(5):
            self.memory_manager.add(
                f"User: cats other {index}\nHypatia: other {index}",
                metadata={"session_id": "other"},
                tags={"brain", "conversation"},
            )
        for index in range(6):
            self.memory_manager.add(
                f"User: cats work {index}\nHypatia: work {index}",
                metadata={"session_id": "work-1"},
                tags={"brain", "conversation"},
            )

        response = self.engine.process(
            BrainRequest(message="recall cats", metadata={"session_id": "work-1"})
        )

        self.assertEqual(response.memory_count, 5)
        self.assertIn("User: cats work 0", response.message)
        self.assertIn("User: cats work 4", response.message)
        self.assertNotIn("User: cats work 5", response.message)
        self.assertNotIn("User: cats other 0", response.message)

    def test_same_query_returns_different_results_for_different_sessions(self) -> None:
        self.memory_manager.add(
            "User: cats\nHypatia: Work answer.",
            metadata={"session_id": "work-1"},
            tags={"brain", "conversation"},
        )
        self.memory_manager.add(
            "User: cats\nHypatia: Personal answer.",
            metadata={"session_id": "personal"},
            tags={"brain", "conversation"},
        )

        work_response = self.engine.process(
            BrainRequest(message="recall cats", metadata={"session_id": "work-1"})
        )
        personal_response = self.engine.process(
            BrainRequest(message="recall cats", metadata={"session_id": "personal"})
        )

        self.assertIn("Work answer.", work_response.message)
        self.assertNotIn("Personal answer.", work_response.message)
        self.assertIn("Personal answer.", personal_response.message)
        self.assertNotIn("Work answer.", personal_response.message)

    def test_custom_session_recall_excludes_default_and_none_session_records(
        self,
    ) -> None:
        self.memory_manager.add(
            "User: cats\nHypatia: Legacy conversation.",
            tags={"brain", "conversation"},
        )
        self.memory_manager.add(
            "User: cats\nHypatia: Null session conversation.",
            metadata={"session_id": None},
            tags={"brain", "conversation"},
        )

        response = self.engine.process(
            BrainRequest(message="recall cats", metadata={"session_id": "work-1"})
        )

        self.assertEqual(response.memory_count, 0)
        self.assertNotIn("Legacy conversation.", response.message)
        self.assertNotIn("Null session conversation.", response.message)

    def test_invalid_session_id_prevents_recall_search(self) -> None:
        engine = CognitiveEngine(
            self.knowledge_engine,
            RecallSearchMustNotRunMemoryManager(),  # type: ignore[arg-type]
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        response = engine.process(
            BrainRequest(message="recall cats", metadata={"session_id": 123})
        )

        self.assertFalse(response.success)
        self.assertEqual(response.message, "session_id must be a string.")

    def test_unknown_session_override_prevents_recall_search(self) -> None:
        engine = CognitiveEngine(
            self.knowledge_engine,
            RecallSearchMustNotRunMemoryManager(),  # type: ignore[arg-type]
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        response = engine.process(
            BrainRequest(message="recall cats", metadata={"session_id": "unknown"})
        )

        self.assertFalse(response.success)
        self.assertEqual(response.message, "Unknown session: unknown")

    def test_conversation_search_precedes_generic_knowledge_search(self) -> None:
        self.memory_manager.add(
            "Bootstrap loading order",
            metadata={"session_id": "default"},
            tags={"brain", "conversation"},
        )
        engine = CognitiveEngine(
            KnowledgeSearchMustNotRun(),  # type: ignore[arg-type]
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        response = engine.process(
            BrainRequest(message="search conversations bootstrap")
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "conversation_search")
        self.assertIn("Bootstrap loading order", response.message)

    def test_conversation_search_preserves_query_case_and_uses_no_memory_limit(
        self,
    ) -> None:
        memory_manager = RecordingConversationSearchMemoryManager(
            [
                MemoryRecord(
                    memory_id="match-1",
                    content="Session Manager transaction contract",
                    metadata={"session_id": "default"},
                    tags=frozenset({"brain", "conversation"}),
                )
            ]
        )
        engine = CognitiveEngine(
            KnowledgeSearchMustNotRun(),  # type: ignore[arg-type]
            memory_manager,  # type: ignore[arg-type]
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        response = engine.process(
            BrainRequest(message="SEARCH CONVERSATIONS Session Manager")
        )

        self.assertTrue(response.success)
        self.assertEqual(memory_manager.calls, [("Session Manager", None)])

    def test_empty_conversation_search_fails_without_memory_or_knowledge_access(
        self,
    ) -> None:
        engine = CognitiveEngine(
            KnowledgeSearchMustNotRun(),  # type: ignore[arg-type]
            RecentConversationsMustNotReadMemoryManager(),  # type: ignore[arg-type]
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        response = engine.process(BrainRequest(message="search conversations"))

        self.assertFalse(response.success)
        self.assertEqual(response.intent, "conversation_search")
        self.assertEqual(response.message, "Search query must not be empty.")

    def test_conversation_search_filters_sessions_and_tags_before_limiting(
        self,
    ) -> None:
        now = datetime.now(UTC)
        records = [
            MemoryRecord(
                memory_id=f"other-{index}",
                content=f"Other relevance {index}",
                metadata={"session_id": "personal"},
                tags=frozenset({"brain", "conversation"}),
                created_at=now + timedelta(hours=index),
            )
            for index in range(5)
        ]
        records.extend(
            MemoryRecord(
                memory_id=f"work-{index}",
                content=f"Work relevance {index}",
                metadata={"session_id": "work-1"},
                tags=frozenset({"brain", "conversation"}),
                created_at=now + timedelta(hours=10 - index),
            )
            for index in range(6)
        )
        records.extend(
            [
                MemoryRecord(
                    memory_id="search-record",
                    content="Knowledge search relevance",
                    metadata={"session_id": "work-1"},
                    tags=frozenset({"cognition", "knowledge-search", "conversation"}),
                ),
                MemoryRecord(
                    memory_id="plan-record",
                    content="Plan relevance",
                    metadata={"session_id": "work-1"},
                    tags=frozenset({"brain", "plan"}),
                ),
            ]
        )
        memory_manager = RecordingConversationSearchMemoryManager(records)
        engine = CognitiveEngine(
            KnowledgeSearchMustNotRun(),  # type: ignore[arg-type]
            memory_manager,  # type: ignore[arg-type]
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        response = engine.process(
            BrainRequest(
                message="search conversations relevance",
                metadata={"session_id": "work-1"},
            )
        )

        self.assertEqual(response.memory_count, 5)
        self.assertIn("1. Work relevance 0", response.message)
        self.assertIn("5. Work relevance 4", response.message)
        self.assertNotIn("Work relevance 5", response.message)
        self.assertNotIn("Other relevance", response.message)
        self.assertNotIn("Knowledge search relevance", response.message)
        self.assertNotIn("Plan relevance", response.message)

    def test_conversation_search_treats_only_missing_session_metadata_as_legacy(
        self,
    ) -> None:
        self.memory_manager.add(
            "Legacy conversation match",
            tags={"brain", "conversation"},
        )
        self.memory_manager.add(
            "Null session conversation match",
            metadata={"session_id": None},
            tags={"brain", "conversation"},
        )

        response = self.engine.process(
            BrainRequest(message="search conversations conversation")
        )

        self.assertEqual(response.memory_count, 1)
        self.assertIn("Legacy conversation match", response.message)
        self.assertNotIn("Null session conversation match", response.message)

    def test_conversation_search_uses_active_session_and_request_override(
        self,
    ) -> None:
        self.memory_manager.add(
            "Default conversation match",
            metadata={"session_id": "default"},
            tags={"brain", "conversation"},
        )
        self.memory_manager.add(
            "Work conversation match",
            metadata={"session_id": "work-1"},
            tags={"brain", "conversation"},
        )
        self.session_manager.set_active("work-1")

        active_response = self.engine.process(
            BrainRequest(message="search conversations match")
        )
        override_response = self.engine.process(
            BrainRequest(
                message="search conversations match",
                metadata={"session_id": "default"},
            )
        )

        self.assertIn("Work conversation match", active_response.message)
        self.assertNotIn("Default conversation match", active_response.message)
        self.assertIn("Default conversation match", override_response.message)
        self.assertNotIn("Work conversation match", override_response.message)
        self.assertEqual(self.session_manager.get_active().session_id, "work-1")

    def test_invalid_conversation_search_session_override_has_no_side_effects(
        self,
    ) -> None:
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))
        engine = CognitiveEngine(
            KnowledgeSearchMustNotRun(),  # type: ignore[arg-type]
            RecentConversationsMustNotReadMemoryManager(),  # type: ignore[arg-type]
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        for session_id, expected in (
            (123, "session_id must be a string."),
            ("unknown", "Unknown session: unknown"),
        ):
            with self.subTest(session_id=session_id):
                response = engine.process(
                    BrainRequest(
                        message="search conversations bootstrap",
                        metadata={"session_id": session_id},
                    )
                )

                self.assertFalse(response.success)
                self.assertEqual(response.message, expected)

        self.assertEqual(events, [])
        self.assertEqual(self.session_manager.get_active().session_id, "default")

    def test_conversation_search_does_not_create_new_events_or_memory_records(
        self,
    ) -> None:
        self.memory_manager.add(
            "Stored conversation match",
            metadata={"session_id": "default"},
            tags={"brain", "conversation"},
        )
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))
        memory_count = self.memory_manager.count()

        response = self.engine.process(
            BrainRequest(message="search conversations match")
        )

        self.assertTrue(response.success)
        self.assertEqual(self.memory_manager.count(), memory_count)
        self.assertEqual(events, [])

    def test_recent_conversations_uses_a_default_limit_of_five_newest_records(
        self,
    ) -> None:
        for index in range(6):
            self.memory_manager.add(
                f"Conversation {index}",
                metadata={"session_id": "default"},
                tags={"brain", "conversation"},
            )

        response = self.engine.process(BrainRequest(message="recent conversations"))

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "recent_conversations")
        self.assertEqual(response.memory_count, 5)
        self.assertIn("1. Conversation 5", response.message)
        self.assertIn("5. Conversation 1", response.message)
        self.assertNotIn("Conversation 0", response.message)

    def test_recent_conversations_honours_explicit_one_and_twenty_limits(self) -> None:
        for index in range(6):
            self.memory_manager.add(
                f"Conversation {index}",
                metadata={"session_id": "default"},
                tags={"brain", "conversation"},
            )

        one_response = self.engine.process(
            BrainRequest(message="recent conversations 1")
        )
        twenty_response = self.engine.process(
            BrainRequest(message="recent conversations 20")
        )

        self.assertEqual(one_response.memory_count, 1)
        self.assertIn("1. Conversation 5", one_response.message)
        self.assertEqual(twenty_response.memory_count, 6)
        self.assertIn("6. Conversation 0", twenty_response.message)

    def test_recent_conversations_rejects_invalid_counts(self) -> None:
        expected_messages = {
            "recent conversations abc": "Count must be an integer.",
            "recent conversations 0": "Count must be between 1 and 20.",
            "recent conversations 21": "Count must be between 1 and 20.",
        }

        for message, expected in expected_messages.items():
            with self.subTest(message=message):
                response = self.engine.process(BrainRequest(message=message))

                self.assertFalse(response.success)
                self.assertEqual(response.intent, "recent_conversations")
                self.assertEqual(response.message, expected)
                self.assertEqual(response.memory_count, 0)

    def test_recent_conversations_filters_tags_and_other_sessions_before_limiting(
        self,
    ) -> None:
        for index in range(5):
            self.memory_manager.add(
                f"Other session {index}",
                metadata={"session_id": "personal"},
                tags={"brain", "conversation"},
            )
        for index in range(6):
            self.memory_manager.add(
                f"Work conversation {index}",
                metadata={"session_id": "work-1"},
                tags={"brain", "conversation"},
            )
        self.memory_manager.add(
            "Search record",
            metadata={"session_id": "work-1"},
            tags={"cognition", "knowledge-search", "conversation"},
        )
        self.memory_manager.add(
            "Plan record",
            metadata={"session_id": "work-1"},
            tags={"brain", "plan"},
        )

        response = self.engine.process(
            BrainRequest(
                message="recent conversations",
                metadata={"session_id": "work-1"},
            )
        )

        self.assertEqual(response.memory_count, 5)
        self.assertIn("1. Work conversation 5", response.message)
        self.assertIn("5. Work conversation 1", response.message)
        self.assertNotIn("Work conversation 0", response.message)
        self.assertNotIn("Other session", response.message)
        self.assertNotIn("Search record", response.message)
        self.assertNotIn("Plan record", response.message)

    def test_recent_conversations_treats_only_missing_session_metadata_as_legacy(
        self,
    ) -> None:
        self.memory_manager.add(
            "Legacy conversation",
            tags={"brain", "conversation"},
        )
        self.memory_manager.add(
            "Null session conversation",
            metadata={"session_id": None},
            tags={"brain", "conversation"},
        )

        response = self.engine.process(BrainRequest(message="recent conversations"))

        self.assertEqual(response.memory_count, 1)
        self.assertIn("Legacy conversation", response.message)
        self.assertNotIn("Null session conversation", response.message)

    def test_recent_conversations_uses_active_session_and_request_override(
        self,
    ) -> None:
        self.memory_manager.add(
            "Default conversation",
            metadata={"session_id": "default"},
            tags={"brain", "conversation"},
        )
        self.memory_manager.add(
            "Work conversation",
            metadata={"session_id": "work-1"},
            tags={"brain", "conversation"},
        )
        self.session_manager.set_active("work-1")

        active_response = self.engine.process(
            BrainRequest(message="recent conversations")
        )
        override_response = self.engine.process(
            BrainRequest(
                message="recent conversations",
                metadata={"session_id": "default"},
            )
        )

        self.assertIn("Work conversation", active_response.message)
        self.assertNotIn("Default conversation", active_response.message)
        self.assertIn("Default conversation", override_response.message)
        self.assertNotIn("Work conversation", override_response.message)
        self.assertEqual(self.session_manager.get_active().session_id, "work-1")

    def test_invalid_recent_conversations_session_overrides_have_no_side_effects(
        self,
    ) -> None:
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))
        engine = CognitiveEngine(
            self.knowledge_engine,
            RecentConversationsMustNotReadMemoryManager(),  # type: ignore[arg-type]
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        for session_id, expected in (
            (123, "session_id must be a string."),
            ("unknown", "Unknown session: unknown"),
        ):
            with self.subTest(session_id=session_id):
                response = engine.process(
                    BrainRequest(
                        message="recent conversations",
                        metadata={"session_id": session_id},
                    )
                )

                self.assertFalse(response.success)
                self.assertEqual(response.message, expected)

        self.assertEqual(events, [])
        self.assertEqual(self.session_manager.get_active().session_id, "default")

    def test_recent_conversations_does_not_create_conversation_or_session_events(
        self,
    ) -> None:
        self.memory_manager.add(
            "Stored conversation",
            metadata={"session_id": "default"},
            tags={"brain", "conversation"},
        )
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))
        memory_count = self.memory_manager.count()

        response = self.engine.process(BrainRequest(message="recent conversations"))

        self.assertTrue(response.success)
        self.assertEqual(self.memory_manager.count(), memory_count)
        self.assertEqual(events, [])
