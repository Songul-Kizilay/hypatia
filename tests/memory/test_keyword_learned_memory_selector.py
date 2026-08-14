from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from memory.KeywordLearnedMemorySelector import KeywordLearnedMemorySelector
from memory.LearnedMemory import LearnedMemory
from memory.LearnedMemorySelector import LearnedMemorySelector


class KeywordLearnedMemorySelectorTests(unittest.TestCase):
    def test_selects_exact_language_memory_by_key_token(self) -> None:
        language = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="Rust",
        )
        goal = LearnedMemory(
            kind="goal",
            key="current_learning_goal",
            value="Kali Linux",
        )
        selector: LearnedMemorySelector = KeywordLearnedMemorySelector()

        result = selector.select(
            source_text="What language do I prefer?",
            memories=(language, goal),
        )

        self.assertEqual(result, (language,))
        self.assertIs(result[0], language)

    def test_selects_learning_goal_by_second_relevance_case(self) -> None:
        language = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="Rust",
        )
        goal = LearnedMemory(
            kind="goal",
            key="current_learning_goal",
            value="Kali Linux",
        )
        selector = KeywordLearnedMemorySelector()

        result = selector.select(
            source_text="What am I learning now?",
            memories=(language, goal),
        )

        self.assertEqual(result, (goal,))
        self.assertIs(result[0], goal)

    def test_matching_is_case_insensitive_and_splits_boundaries(self) -> None:
        language = LearnedMemory(
            kind="preference",
            key="Preferred_LANGUAGE",
            value="Rust",
        )
        original = LearnedMemory(
            kind=language.kind,
            key=language.key,
            value=language.value,
        )
        selector = KeywordLearnedMemorySelector()

        result = selector.select(
            source_text="Which...LANGUAGE?!",
            memories=(language,),
        )

        self.assertEqual(result, (language,))
        self.assertIs(result[0], language)
        self.assertEqual(language, original)
        self.assertEqual(language.key, "Preferred_LANGUAGE")

    def test_requires_exact_key_token_overlap_only(self) -> None:
        language = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="Rust",
        )
        selector = KeywordLearnedMemorySelector()

        self.assertEqual(
            selector.select(source_text="lang", memories=(language,)),
            (),
        )
        self.assertEqual(
            selector.select(source_text="Rust", memories=(language,)),
            (),
        )
        self.assertEqual(
            selector.select(source_text="preference", memories=(language,)),
            (),
        )
        self.assertEqual(
            selector.select(source_text="unrelated question", memories=(language,)),
            (),
        )

    def test_preserves_matching_order_identities_and_duplicates(self) -> None:
        first = LearnedMemory(
            kind="project_fact",
            key="active_project",
            value="Hypatia",
        )
        second = LearnedMemory(
            kind="goal",
            key="project_goal",
            value="Ship safely",
        )
        memories = (second, first, second)
        original_memories = tuple(memories)
        selector = KeywordLearnedMemorySelector()

        result = selector.select(
            source_text="Tell me about the project.",
            memories=memories,
        )

        self.assertEqual(result, memories)
        self.assertEqual(memories, original_memories)
        self.assertIs(result[0], second)
        self.assertIs(result[1], first)
        self.assertIs(result[2], second)

    def test_repeated_calls_are_deterministic_and_stateless(self) -> None:
        language = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="Rust",
        )
        goal = LearnedMemory(
            kind="goal",
            key="current_learning_goal",
            value="Kali Linux",
        )
        memories = (language, goal)
        selector = KeywordLearnedMemorySelector()

        first = selector.select(source_text="language", memories=memories)
        unrelated = selector.select(source_text="nothing relevant", memories=memories)
        second = selector.select(source_text="language", memories=memories)

        self.assertEqual(first, (language,))
        self.assertEqual(unrelated, ())
        self.assertEqual(second, first)
        self.assertIs(first[0], language)
        self.assertIs(second[0], language)


if __name__ == "__main__":
    unittest.main()
