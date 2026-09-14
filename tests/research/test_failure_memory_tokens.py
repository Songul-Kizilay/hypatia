"""Subject-free vocabulary cannot manufacture Failure Memory relevance."""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from research.FailureLessonKind import FailureLessonKind
from research.FailureMemoryAdvisor import FailureMemoryAdvisor
from research.FailureMemoryTokens import failure_memory_tokens
from research.ResearchFailureLesson import ResearchFailureLesson
from research.ResearchQueryTerms import COMMON_ACRONYMS, STOP_WORDS


class FailureMemoryTokensTests(unittest.TestCase):
    def test_closed_lists_are_filtered_at_every_length_and_case(self) -> None:
        for word in sorted(STOP_WORDS | COMMON_ACRONYMS):
            with self.subTest(word=word):
                self.assertEqual(
                    failure_memory_tokens(f"({word.upper()}),"), frozenset()
                )

    def test_subject_words_and_exact_technical_identifiers_survive(self) -> None:
        self.assertEqual(
            failure_memory_tokens(
                "Which XSS SQL C++ C# HTTP/2 Next.js CVE-2026-12345 does Saturn rings?"
            ),
            frozenset(
                {
                    "xss",
                    "sql",
                    "c++",
                    "c#",
                    "http/2",
                    "next.js",
                    "cve-2026-12345",
                    "saturn",
                    "rings",
                }
            ),
        )

    def test_function_words_or_medium_names_alone_do_not_recall_a_lesson(self) -> None:
        for context, question in (
            ("Which observation does help?", "Which compiler does optimize Rust?"),
            ("HTTP HTML redirects", "HTTP HTML rendering"),
        ):
            with self.subTest(context=context):
                lesson = ResearchFailureLesson(
                    lesson_id="lesson-1",
                    kind=FailureLessonKind.FAILED_HYPOTHESIS,
                    run_id="run-old",
                    subject_id="hypothesis-1",
                    statement="Saturn rings failed.",
                    provenance=("hypothesis-1",),
                    context=context,
                    recorded_at=datetime(2026, 9, 3, tzinfo=UTC),
                )
                advisor = FailureMemoryAdvisor()
                self.assertEqual(advisor.matches(question, (lesson,)), ())
                self.assertEqual(advisor.relevant(question, (lesson,)), ())


if __name__ == "__main__":
    unittest.main()
