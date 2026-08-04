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

    def test_existing_greeting_and_message_detection_is_preserved(self) -> None:
        self.assertEqual(
            self.router.detect_intent(BrainRequest(message="hello there")),
            "greeting",
        )
        self.assertEqual(
            self.router.detect_intent(BrainRequest(message="tell me more")),
            "message",
        )
