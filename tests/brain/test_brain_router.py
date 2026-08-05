"""Unit tests for deterministic BrainRouter intent detection."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

loaded_brain = sys.modules.get("brain")
if loaded_brain is not None:
    source_brain_dir = str(SRC_DIR / "brain")
    if source_brain_dir not in loaded_brain.__path__:
        loaded_brain.__path__.append(source_brain_dir)

from brain.BrainRequest import BrainRequest
from brain.BrainRouter import BrainRouter


class BrainRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.router = BrainRouter()

    def test_recall_command_is_detected(self) -> None:
        intent = self.router.detect_intent(BrainRequest(message="recall cats"))

        self.assertEqual(intent, "recall")

    def test_recall_command_is_case_insensitive(self) -> None:
        intent = self.router.detect_intent(BrainRequest(message="RECALL cats"))

        self.assertEqual(intent, "recall")

    def test_declared_recall_intent_is_detected(self) -> None:
        intent = self.router.detect_intent(
            BrainRequest(message="cats", metadata={"intent": "recall"})
        )

        self.assertEqual(intent, "recall")

    def test_recall_word_inside_a_sentence_remains_a_message(self) -> None:
        intent = self.router.detect_intent(BrainRequest(message="please recall cats"))

        self.assertEqual(intent, "message")

    def test_conversation_search_command_is_detected(self) -> None:
        intent = self.router.detect_intent(
            BrainRequest(message="search conversations bootstrap")
        )

        self.assertEqual(intent, "conversation_search")

    def test_empty_conversation_search_command_is_detected(self) -> None:
        intent = self.router.detect_intent(BrainRequest(message="search conversations"))

        self.assertEqual(intent, "conversation_search")

    def test_conversation_search_command_is_case_insensitive(self) -> None:
        intent = self.router.detect_intent(
            BrainRequest(message="SEARCH CONVERSATIONS Session Manager")
        )

        self.assertEqual(intent, "conversation_search")

    def test_natural_language_conversation_search_phrases_remain_messages(self) -> None:
        for message in (
            "can you search our conversations",
            "what did we discuss about bootstrap",
            "find something from earlier",
        ):
            with self.subTest(message=message):
                self.assertEqual(
                    self.router.detect_intent(BrainRequest(message=message)),
                    "message",
                )

    def test_recent_conversations_command_is_detected(self) -> None:
        intent = self.router.detect_intent(BrainRequest(message="recent conversations"))

        self.assertEqual(intent, "recent_conversations")

    def test_recent_conversations_count_command_is_detected_case_insensitively(
        self,
    ) -> None:
        intent = self.router.detect_intent(
            BrainRequest(message="RECENT CONVERSATIONS 10")
        )

        self.assertEqual(intent, "recent_conversations")

    def test_recent_conversations_word_inside_a_sentence_remains_a_message(
        self,
    ) -> None:
        for message in (
            "can you show my recent conversations",
            "what did we recently talk about",
            "show recent things",
        ):
            with self.subTest(message=message):
                self.assertEqual(
                    self.router.detect_intent(BrainRequest(message=message)),
                    "message",
                )

    def test_declared_recent_conversations_metadata_does_not_trigger_the_command(
        self,
    ) -> None:
        intent = self.router.detect_intent(
            BrainRequest(
                message="hello",
                metadata={"intent": "recent_conversations"},
            )
        )

        self.assertEqual(intent, "greeting")

    def test_session_overview_command_is_detected_case_insensitively(self) -> None:
        self.assertEqual(
            self.router.detect_intent(BrainRequest(message="SESSION OVERVIEW")),
            "session_overview",
        )

    def test_natural_language_session_overview_phrases_remain_messages(self) -> None:
        for message in (
            "give me an overview of my sessions",
            "how many conversations are there",
            "show session information",
        ):
            with self.subTest(message=message):
                self.assertEqual(
                    self.router.detect_intent(BrainRequest(message=message)),
                    "message",
                )

    def test_declared_session_overview_metadata_does_not_trigger_the_command(
        self,
    ) -> None:
        intent = self.router.detect_intent(
            BrainRequest(message="hello", metadata={"intent": "session_overview"})
        )

        self.assertEqual(intent, "greeting")

    def test_session_details_commands_are_detected_case_insensitively(self) -> None:
        self.assertEqual(
            self.router.detect_intent(BrainRequest(message="SESSION DETAILS")),
            "session_details",
        )
        self.assertEqual(
            self.router.detect_intent(BrainRequest(message="SESSION DETAILS Work-1")),
            "session_details",
        )

    def test_natural_language_session_details_phrases_remain_messages(self) -> None:
        for message in (
            "show me session details",
            "can you give details about work-1",
            "I need session details for work-1",
            "session detail work-1",
        ):
            with self.subTest(message=message):
                self.assertEqual(
                    self.router.detect_intent(BrainRequest(message=message)),
                    "message",
                )

    def test_declared_session_details_metadata_does_not_trigger_the_command(
        self,
    ) -> None:
        intent = self.router.detect_intent(
            BrainRequest(message="hello", metadata={"intent": "session_details"})
        )

        self.assertEqual(intent, "greeting")

    def test_session_recent_commands_are_detected_case_insensitively(self) -> None:
        self.assertEqual(
            self.router.detect_intent(BrainRequest(message="SESSION RECENT")),
            "session_recent",
        )
        self.assertEqual(
            self.router.detect_intent(
                BrainRequest(message="SESSION RECENT Work Research")
            ),
            "session_recent",
        )

    def test_natural_language_session_recent_phrases_remain_messages(self) -> None:
        for message in (
            "show recent messages from work",
            "what did we discuss in research",
            "give me recent session messages",
        ):
            with self.subTest(message=message):
                self.assertEqual(
                    self.router.detect_intent(BrainRequest(message=message)),
                    "message",
                )

    def test_declared_session_recent_metadata_does_not_trigger_the_command(
        self,
    ) -> None:
        intent = self.router.detect_intent(
            BrainRequest(message="hello", metadata={"intent": "session_recent"})
        )

        self.assertEqual(intent, "greeting")

    def test_session_search_commands_are_detected_case_insensitively(self) -> None:
        for message in (
            "session search",
            "session search work-1",
            "session search work-1 --",
            "SESSION SEARCH Work Research -- Memory",
        ):
            with self.subTest(message=message):
                self.assertEqual(
                    self.router.detect_intent(BrainRequest(message=message)),
                    "session_search",
                )

    def test_natural_language_session_search_phrases_remain_messages(self) -> None:
        for message in (
            "search the work session for persistence",
            "find our memory discussion",
            "what did we say about routing",
        ):
            with self.subTest(message=message):
                self.assertEqual(
                    self.router.detect_intent(BrainRequest(message=message)),
                    "message",
                )

    def test_declared_session_search_metadata_does_not_trigger_the_command(
        self,
    ) -> None:
        intent = self.router.detect_intent(
            BrainRequest(message="hello", metadata={"intent": "session_search"})
        )

        self.assertEqual(intent, "greeting")

    def test_session_activity_commands_are_detected_case_insensitively(self) -> None:
        for message in (
            "session activity",
            "session activity work-1",
            "SESSION ACTIVITY Work Research",
        ):
            with self.subTest(message=message):
                self.assertEqual(
                    self.router.detect_intent(BrainRequest(message=message)),
                    "session_activity",
                )

    def test_natural_language_session_activity_phrases_remain_messages(self) -> None:
        for message in (
            "show activity for work",
            "what happened in my session",
            "session activitylight",
        ):
            with self.subTest(message=message):
                self.assertEqual(
                    self.router.detect_intent(BrainRequest(message=message)),
                    "message",
                )

    def test_declared_session_activity_metadata_does_not_trigger_the_command(
        self,
    ) -> None:
        intent = self.router.detect_intent(
            BrainRequest(message="hello", metadata={"intent": "session_activity"})
        )

        self.assertEqual(intent, "greeting")

    def test_session_rename_is_an_explicit_case_insensitive_command(self) -> None:
        for message in (
            "rename session",
            "rename session work -- archive",
            "RENAME SESSION Work -- Research Archive",
        ):
            with self.subTest(message=message):
                self.assertEqual(
                    self.router.detect_intent(BrainRequest(message=message)),
                    "session_rename",
                )

    def test_natural_language_rename_variants_remain_messages(self) -> None:
        for message in ("rename work", "session rename work -- archive"):
            with self.subTest(message=message):
                self.assertEqual(
                    self.router.detect_intent(BrainRequest(message=message)),
                    "message",
                )

    def test_existing_greeting_and_message_detection_is_preserved(self) -> None:
        self.assertEqual(
            self.router.detect_intent(BrainRequest(message="hello there")),
            "greeting",
        )
        self.assertEqual(
            self.router.detect_intent(BrainRequest(message="tell me more")),
            "message",
        )

    def test_create_session_command_is_detected_and_preserves_its_id_case(self) -> None:
        request = BrainRequest(message="CREATE SESSION Work-1")

        self.assertEqual(self.router.detect_intent(request), "session_create")
        self.assertEqual(request.message.removeprefix("CREATE SESSION "), "Work-1")

    def test_list_sessions_command_is_detected(self) -> None:
        self.assertEqual(
            self.router.detect_intent(BrainRequest(message="list sessions")),
            "session_list",
        )

    def test_use_session_command_is_detected(self) -> None:
        self.assertEqual(
            self.router.detect_intent(BrainRequest(message="use session work-1")),
            "session_use",
        )

    def test_non_command_session_phrases_remain_messages(self) -> None:
        for message in (
            "please create session work-1",
            "can you list sessions",
            "I want to use session work-1",
            "create sessions work-1",
            "use sessions work-1",
        ):
            with self.subTest(message=message):
                self.assertEqual(
                    self.router.detect_intent(BrainRequest(message=message)),
                    "message",
                )

    def test_declared_session_metadata_does_not_trigger_a_session_command(self) -> None:
        intent = self.router.detect_intent(
            BrainRequest(message="hello", metadata={"intent": "session_create"})
        )

        self.assertEqual(intent, "greeting")

    def test_session_rename_preview_command_is_explicit_and_case_insensitive(
        self,
    ) -> None:
        self.assertEqual(
            self.router.detect_intent(
                BrainRequest(message="PREVIEW RENAME SESSION Work -- Archive")
            ),
            "session_rename_preview",
        )
        self.assertEqual(
            self.router.detect_intent(
                BrainRequest(message="preview session rename work")
            ),
            "message",
        )
        self.assertEqual(
            self.router.detect_intent(BrainRequest(message="preview rename session")),
            "session_rename_preview",
        )
        self.assertEqual(
            self.router.detect_intent(
                BrainRequest(message="rename session work -- archive")
            ),
            "session_rename",
        )

    def test_session_rename_help_command_is_exact_and_case_insensitive(self) -> None:
        for message in (
            "help rename session",
            "  HELP RENAME SESSION  ",
        ):
            with self.subTest(message=message):
                self.assertEqual(
                    self.router.detect_intent(BrainRequest(message=message)),
                    "session_rename_help",
                )

        self.assertEqual(
            self.router.detect_intent(BrainRequest(message="help session rename")),
            "message",
        )
        self.assertEqual(
            self.router.detect_intent(BrainRequest(message="rename session help")),
            "session_rename",
        )

    def test_session_rename_candidates_command_is_exact_and_case_insensitive(
        self,
    ) -> None:
        for message in (
            "list renameable sessions",
            "  LIST RENAMEABLE SESSIONS  ",
        ):
            with self.subTest(message=message):
                self.assertEqual(
                    self.router.detect_intent(BrainRequest(message=message)),
                    "session_rename_candidates",
                )

        for message in (
            "list renamable sessions",
            "renameable sessions",
            "list sessions renameable",
        ):
            with self.subTest(message=message):
                self.assertEqual(
                    self.router.detect_intent(BrainRequest(message=message)),
                    "message",
                )

        self.assertEqual(
            self.router.detect_intent(BrainRequest(message="list sessions")),
            "session_list",
        )

    def test_active_session_command_is_exact_and_case_insensitive(self) -> None:
        for message in (
            "active session",
            "  ACTIVE SESSION  ",
        ):
            with self.subTest(message=message):
                self.assertEqual(
                    self.router.detect_intent(BrainRequest(message=message)),
                    "session_active",
                )

        for message in (
            "session active",
            "show active session",
            "active session work",
        ):
            with self.subTest(message=message):
                self.assertEqual(
                    self.router.detect_intent(BrainRequest(message=message)),
                    "message",
                )

        self.assertEqual(
            self.router.detect_intent(BrainRequest(message="session activity work")),
            "session_activity",
        )
