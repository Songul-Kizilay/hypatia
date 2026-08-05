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
