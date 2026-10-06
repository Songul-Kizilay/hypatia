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
    recall_query_terms,
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


class RecallQueryTermsTests(unittest.TestCase):
    """Live bug: a real SQL injection record was never found because the
    recall sentence's own instructional wording ("bul", "ve", "söyle", ...)
    survived extraction alongside the real topic and had to match too.
    """

    def test_turkish_recall_boilerplate_is_stripped_leaving_only_the_topic(
        self,
    ) -> None:
        message = (
            "Önceki oturumda SQL Injection konusunda nerede kalmıştık? Eski "
            "oturum kayıtlarından bul ve hangi session_id'den getirdiğini "
            "söyle."
        )
        self.assertEqual(recall_query_terms(message), ("sql", "injection"))

    def test_english_recall_boilerplate_is_stripped_leaving_only_the_topic(
        self,
    ) -> None:
        message = (
            "Can you find and tell me which session_id you brought the SQL "
            "injection records from the old session?"
        )
        self.assertEqual(recall_query_terms(message), ("sql", "injection"))

    def test_extraction_is_deterministic(self) -> None:
        message = (
            "Önceki oturumda SQL Injection konusunda nerede kalmıştık? Eski "
            "oturum kayıtlarından bul ve hangi session_id'den getirdiğini "
            "söyle."
        )
        self.assertEqual(recall_query_terms(message), recall_query_terms(message))

    def test_a_real_topic_word_sharing_no_boilerplate_still_survives(self) -> None:
        message = "Let's continue the buffer overflow and SQL injection lesson."
        self.assertEqual(
            recall_query_terms(message), ("buffer", "overflow", "sql", "injection")
        )

    def test_a_topic_made_entirely_of_stopwords_is_a_disclosed_blind_spot(
        self,
    ) -> None:
        """Independent QA review (v0.3.448): a real, narrower regression risk.

        Stopword growth only ever removes candidate terms, so it can never
        make an unrelated record match -- but if someone's actual recall
        topic is composed entirely of words this list now treats as
        boilerplate (e.g. "old records" with nothing else to anchor it),
        extraction returns nothing, and
        `CognitiveEngine._cross_session_recall_records` skips semantic
        search too, not only the lexical path (see the comment at its
        `if not recall_query_terms(query): return []` gate). This fails
        safe to a deterministic NOT_FOUND -- never a wrong-session leak or
        a fabricated answer -- but it is a real, disclosed blind spot, not
        a hidden one: recorded here, not silently accepted.
        """
        self.assertEqual(recall_query_terms("Eski kayıtlar konusunda."), ())
        self.assertEqual(recall_query_terms("Old records, please."), ())


if __name__ == "__main__":
    unittest.main()
