from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import call, patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from memory.LearnedMemory import LearnedMemory
from memory.LearnedMemoryRetrieval import (
    collect_learned_memories,
    find_learned_memories,
)
from memory.MemoryRecord import MemoryRecord


class LearnedMemoryRetrievalTests(unittest.TestCase):
    @patch("memory.LearnedMemoryRetrieval.decode_learned_memory")
    def test_collects_decoded_memories_in_order_with_identity_preserved(
        self,
        decode_learned_memory,
    ) -> None:
        records = tuple(
            MemoryRecord(memory_id=f"record-{index}", content=f"content-{index}")
            for index in range(4)
        )
        original_records = records
        memory_a = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="Python",
        )
        memory_b = LearnedMemory(
            kind="user_fact",
            key="name",
            value="Songül",
        )
        decode_learned_memory.side_effect = [memory_a, None, None, memory_b]

        result = collect_learned_memories(records)

        self.assertEqual(result, (memory_a, memory_b))
        self.assertIs(result[0], memory_a)
        self.assertIs(result[1], memory_b)
        self.assertIs(records, original_records)
        self.assertEqual(
            decode_learned_memory.call_args_list,
            [call(record) for record in records],
        )

    @patch("memory.LearnedMemoryRetrieval.decode_learned_memory")
    def test_empty_input_returns_empty_tuple_without_decoding(
        self,
        decode_learned_memory,
    ) -> None:
        result = collect_learned_memories(())

        self.assertEqual(result, ())
        self.assertIsInstance(result, tuple)
        decode_learned_memory.assert_not_called()

    def test_finds_all_exact_kind_and_key_matches_in_supplied_order(self) -> None:
        first_match = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="Python",
        )
        same_key_different_kind = LearnedMemory(
            kind="user_fact",
            key="preferred_language",
            value="Turkish",
        )
        same_kind_different_key = LearnedMemory(
            kind="preference",
            key="preferred_editor",
            value="VS Code",
        )
        case_different_key = LearnedMemory(
            kind="preference",
            key="Preferred_Language",
            value="Rust",
        )
        second_match = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="Go",
        )
        memories = (
            first_match,
            same_key_different_kind,
            same_kind_different_key,
            case_different_key,
            second_match,
        )

        result = find_learned_memories(
            memories,
            kind="preference",
            key="preferred_language",
        )

        self.assertEqual(result, (first_match, second_match))
        self.assertIs(result[0], first_match)
        self.assertIs(result[1], second_match)
        self.assertIsInstance(result, tuple)

    def test_find_with_empty_input_returns_exact_empty_tuple(self) -> None:
        result = find_learned_memories(
            (),
            kind="preference",
            key="preferred_language",
        )

        self.assertEqual(result, ())
        self.assertIsInstance(result, tuple)
