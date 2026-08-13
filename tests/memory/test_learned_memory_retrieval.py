from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import call, patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from memory.LearnedMemory import LearnedMemory
from memory.LearnedMemoryRetrieval import collect_learned_memories
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
