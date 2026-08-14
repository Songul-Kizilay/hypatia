from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from memory.KeywordLearnedMemoryRelevance import (
    score_keyword_learned_memory_relevance,
)
from memory.LearnedMemory import LearnedMemory


class KeywordLearnedMemoryRelevanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.language = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="Rust",
        )

    def test_scores_zero_for_no_overlap(self) -> None:
        self.assertEqual(
            score_keyword_learned_memory_relevance(
                source_text="What is the weather?",
                memory=self.language,
            ),
            0,
        )

    def test_scores_single_key_overlap(self) -> None:
        self.assertEqual(
            score_keyword_learned_memory_relevance(
                source_text="What language do I prefer?",
                memory=self.language,
            ),
            1,
        )

    def test_scores_distinct_key_and_value_overlaps(self) -> None:
        self.assertEqual(
            score_keyword_learned_memory_relevance(
                source_text="Is Rust my preferred language?",
                memory=self.language,
            ),
            3,
        )

    def test_duplicate_source_tokens_count_once(self) -> None:
        self.assertEqual(
            score_keyword_learned_memory_relevance(
                source_text="Rust Rust Rust",
                memory=self.language,
            ),
            1,
        )

    def test_duplicate_token_across_key_and_value_counts_once(self) -> None:
        memory = LearnedMemory(
            kind="project_fact",
            key="rust_project",
            value="Rust tooling",
        )

        self.assertEqual(
            score_keyword_learned_memory_relevance(
                source_text="rust",
                memory=memory,
            ),
            1,
        )

    def test_matching_is_case_insensitive_and_splits_boundaries(self) -> None:
        memory = LearnedMemory(
            kind="goal",
            key="Current_LANGUAGE",
            value="Kali-Linux",
        )

        self.assertEqual(
            score_keyword_learned_memory_relevance(
                source_text="LANGUAGE, kali!",
                memory=memory,
            ),
            2,
        )

    def test_unicode_alphanumeric_tokens_match(self) -> None:
        memory = LearnedMemory(
            kind="self_fact",
            key="öğrenme_hedefi",
            value="München",
        )

        self.assertEqual(
            score_keyword_learned_memory_relevance(
                source_text="ÖĞRENME MÜNCHEN",
                memory=memory,
            ),
            2,
        )

    def test_partial_substring_and_kind_only_matches_score_zero(self) -> None:
        self.assertEqual(
            score_keyword_learned_memory_relevance(
                source_text="Rus preference",
                memory=self.language,
            ),
            0,
        )

    def test_repeated_calls_are_deterministic_and_leave_memory_unchanged(self) -> None:
        original = LearnedMemory(
            kind=self.language.kind,
            key=self.language.key,
            value=self.language.value,
        )

        first = score_keyword_learned_memory_relevance(
            source_text="Rust language",
            memory=self.language,
        )
        second = score_keyword_learned_memory_relevance(
            source_text="Rust language",
            memory=self.language,
        )

        self.assertEqual(first, 2)
        self.assertEqual(second, first)
        self.assertIs(type(first), int)
        self.assertGreaterEqual(first, 0)
        self.assertEqual(self.language, original)


if __name__ == "__main__":
    unittest.main()
