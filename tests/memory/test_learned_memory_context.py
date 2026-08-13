from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from memory.LearnedMemory import LearnedMemory
from memory.LearnedMemoryContext import (
    build_learned_memory_context,
    load_learned_memory_context,
)
from memory.MemoryManager import MemoryManager


class LearnedMemoryContextTests(unittest.TestCase):
    def test_load_context_delegates_exact_authoritative_tuple_once(self) -> None:
        memory_manager = Mock(spec=MemoryManager)
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
        sentinel_context = "".join(("sentinel", "-context"))

        with (
            patch(
                "memory.LearnedMemoryContext.load_learned_memories",
                return_value=memories,
            ) as load_learned_memories,
            patch(
                "memory.LearnedMemoryContext.build_learned_memory_context",
                return_value=sentinel_context,
            ) as build_learned_memory_context,
        ):
            result = load_learned_memory_context(memory_manager)

        load_learned_memories.assert_called_once_with(memory_manager)
        build_learned_memory_context.assert_called_once_with(memories)
        self.assertIs(result, sentinel_context)

    def test_load_context_from_real_empty_manager_returns_exact_empty_string(
        self,
    ) -> None:
        self.assertEqual(load_learned_memory_context(MemoryManager()), "")

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
