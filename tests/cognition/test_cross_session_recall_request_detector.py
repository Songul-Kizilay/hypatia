"""Fixed-phrase detector for natural-language cross-session recall requests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from cognition.CrossSessionRecallRequestDetector import (
    CrossSessionRecallRequestDetector,
)


class CrossSessionRecallRequestDetectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.detector = CrossSessionRecallRequestDetector()

    def test_detects_english_continuation_and_recall_phrases(self) -> None:
        for message in (
            "Let's continue the SQL injection lesson.",
            "Lets continue where we left off.",
            "Can we continue our lesson from before?",
            "Where did we leave off last time?",
            "What was my last question about?",
            "What did we discuss last time?",
            "Last time we talked about buffer overflows, right?",
            "In our previous session you explained XSS.",
            "That was covered in an earlier session.",
        ):
            with self.subTest(message=message):
                self.assertTrue(self.detector.detect(message))

    def test_detects_turkish_continuation_and_recall_phrases(self) -> None:
        for message in (
            "Derse devam edelim mi?",
            "Önceki oturumda ne öğrendik?",
            "Geçen oturumda SQL injection konuşmuştuk.",
            "Nerede kalmıştık?",
            "Son sorum neydi?",
            "Ne kalmıştı dersten?",
            "Hangi soruda kalmıştık?",
        ):
            with self.subTest(message=message):
                self.assertTrue(self.detector.detect(message))

    def test_close_paraphrases_still_match(self) -> None:
        for message in (
            "Hey, let's continue the lesson from yesterday.",
            "So, where did we leave off exactly?",
            "DERSE DEVAM edelim.",
        ):
            with self.subTest(message=message):
                self.assertTrue(self.detector.detect(message))

    def test_does_not_detect_ordinary_unrelated_chat(self) -> None:
        for message in (
            "hello",
            "Hello there, how are you?",
            "what's 2+2",
            "tell me about SQL injection",
            "Can you explain XSS?",
            "What did we discuss?",
        ):
            with self.subTest(message=message):
                self.assertFalse(self.detector.detect(message))

    def test_empty_and_non_string_input_is_never_detected(self) -> None:
        self.assertFalse(self.detector.detect(""))
        self.assertFalse(self.detector.detect("   "))
        self.assertFalse(self.detector.detect(None))  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
