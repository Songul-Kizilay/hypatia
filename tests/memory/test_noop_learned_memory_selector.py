from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from memory.LearnedMemory import LearnedMemory
from memory.LearnedMemorySelector import LearnedMemorySelector
from memory.NoOpLearnedMemorySelector import NoOpLearnedMemorySelector


class NoOpLearnedMemorySelectorTests(unittest.TestCase):
    def test_returns_exact_nonempty_tuple_with_order_and_identities(self) -> None:
        first = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="Python",
        )
        second = LearnedMemory(
            kind="goal",
            key="current_learning_goal",
            value="Kali Linux",
        )
        memories = (first, second)
        original_memories = tuple(memories)
        selector: LearnedMemorySelector = NoOpLearnedMemorySelector()

        result = selector.select(
            source_text="  What do I prefer?  ",
            memories=memories,
        )

        self.assertIs(result, memories)
        self.assertEqual(memories, original_memories)
        self.assertIs(result[0], first)
        self.assertIs(result[1], second)

    def test_preserves_duplicate_and_empty_tuple_identity(self) -> None:
        duplicate = LearnedMemory(
            kind="self_fact",
            key="note",
            value="Exact duplicate",
        )
        duplicates = (duplicate, duplicate)
        empty: tuple[LearnedMemory, ...] = ()
        selector: LearnedMemorySelector = NoOpLearnedMemorySelector()

        duplicate_result = selector.select(
            source_text="first source",
            memories=duplicates,
        )
        empty_result = selector.select(
            source_text="second source",
            memories=empty,
        )

        self.assertIs(duplicate_result, duplicates)
        self.assertIs(duplicate_result[0], duplicate)
        self.assertIs(duplicate_result[1], duplicate)
        self.assertIs(empty_result, empty)

    def test_separate_calls_ignore_source_text_and_retain_no_state(self) -> None:
        first = LearnedMemory(kind="user_fact", key="name", value="Ada")
        second = LearnedMemory(kind="project_fact", key="project", value="Hypatia")
        first_memories = (first,)
        second_memories = (second,)
        selector: LearnedMemorySelector = NoOpLearnedMemorySelector()

        first_result = selector.select(
            source_text="  first source  ",
            memories=first_memories,
        )
        second_result = selector.select(
            source_text="\tcompletely different source\n",
            memories=second_memories,
        )

        self.assertIs(first_result, first_memories)
        self.assertIs(second_result, second_memories)
        self.assertIs(first_result[0], first)
        self.assertIs(second_result[0], second)


if __name__ == "__main__":
    unittest.main()
