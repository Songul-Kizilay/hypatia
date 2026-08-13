from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from memory.LearnedMemory import LearnedMemory
from memory.LearnedMemoryContext import build_learned_memory_context


class LearnedMemoryContextTests(unittest.TestCase):
    def test_empty_memories_return_exact_empty_string(self) -> None:
        self.assertEqual(build_learned_memory_context(()), "")

    def test_single_memory_returns_exact_context(self) -> None:
        memories = (
            LearnedMemory(
                kind="preference",
                key="preferred_language",
                value="Rust",
            ),
        )

        self.assertEqual(
            build_learned_memory_context(memories),
            "Known learned memories:\n" "- preference | preferred_language | Rust",
        )

    def test_multiple_memories_preserve_exact_supplied_order(self) -> None:
        memories = (
            LearnedMemory(
                kind="preference",
                key="preferred_language",
                value="Rust",
            ),
            LearnedMemory(
                kind="goal",
                key="current_learning_goal",
                value="Kali Linux",
            ),
        )

        self.assertEqual(
            build_learned_memory_context(memories),
            "Known learned memories:\n"
            "- preference | preferred_language | Rust\n"
            "- goal | current_learning_goal | Kali Linux",
        )

    def test_duplicates_and_exact_whitespace_are_preserved_deterministically(
        self,
    ) -> None:
        duplicate = LearnedMemory(
            kind="preference",
            key="Preferred_Language",
            value="  Rust  ",
        )
        memories = (duplicate, duplicate)
        original_memories = tuple(memories)
        expected = (
            "Known learned memories:\n"
            "- preference | Preferred_Language |   Rust  \n"
            "- preference | Preferred_Language |   Rust  "
        )

        self.assertEqual(build_learned_memory_context(memories), expected)
        self.assertEqual(build_learned_memory_context(memories), expected)
        self.assertEqual(memories, original_memories)
        self.assertIs(memories[0], duplicate)
        self.assertIs(memories[1], duplicate)


if __name__ == "__main__":
    unittest.main()
