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
import response

source_planner_dir = str(SRC_DIR / "planner")
if source_planner_dir not in planner.__path__:
    planner.__path__.append(source_planner_dir)

source_response_dir = str(SRC_DIR / "response")
if source_response_dir not in response.__path__:
    response.__path__.append(source_response_dir)

from brain.BrainRequest import BrainRequest
from cognition.CognitiveEngine import CognitiveEngine
from core.Exceptions import KnowledgeError, MemoryError, PlannerError
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.MemoryManager import MemoryManager
from memory.MemoryRecord import MemoryRecord
from planner.Planner import Planner
from response.ResponseComposer import ResponseComposer
from session.SessionManager import SessionManager


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
        self.engine = CognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_search_intent_returns_a_successful_response(self) -> None:
        response = self.engine.process(BrainRequest(message="search hypatia"))

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "search")

    def test_session_manager_is_a_required_cognitive_engine_dependency(self) -> None:
        with self.assertRaises(TypeError):
            CognitiveEngine(
                self.knowledge_engine,
                self.memory_manager,
                self.planner,
                self.event_bus,
                self.response_composer,
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
