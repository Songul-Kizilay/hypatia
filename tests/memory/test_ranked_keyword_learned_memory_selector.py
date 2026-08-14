from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import call, patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from memory.LearnedMemory import LearnedMemory
from memory.LearnedMemorySelector import LearnedMemorySelector
from memory.RankedKeywordLearnedMemorySelector import (
    RankedKeywordLearnedMemorySelector,
)

SCORE_PATH = (
    "memory.RankedKeywordLearnedMemorySelector."
    "score_keyword_learned_memory_relevance"
)


def _memory(*, key: str, value: str) -> LearnedMemory:
    return LearnedMemory(kind="preference", key=key, value=value)


class RankedKeywordLearnedMemorySelectorTests(unittest.TestCase):
    def test_orders_relevant_memories_by_descending_score(self) -> None:
        memory_a = _memory(key="memory_a", value="A")
        memory_b = _memory(key="memory_b", value="B")
        memory_c = _memory(key="memory_c", value="C")
        selector: LearnedMemorySelector = RankedKeywordLearnedMemorySelector()

        with patch(SCORE_PATH, side_effect=(1, 3, 2)) as score:
            result = selector.select(
                source_text="  Exact Source  ",
                memories=(memory_a, memory_b, memory_c),
            )

        self.assertEqual(result, (memory_b, memory_c, memory_a))
        self.assertIs(result[0], memory_b)
        self.assertIs(result[1], memory_c)
        self.assertIs(result[2], memory_a)
        self.assertEqual(
            score.call_args_list,
            [
                call(source_text="  Exact Source  ", memory=memory_a),
                call(source_text="  Exact Source  ", memory=memory_b),
                call(source_text="  Exact Source  ", memory=memory_c),
            ],
        )

    def test_equal_scores_preserve_original_relative_order(self) -> None:
        memory_a = _memory(key="memory_a", value="A")
        memory_b = _memory(key="memory_b", value="B")
        memory_c = _memory(key="memory_c", value="C")
        selector = RankedKeywordLearnedMemorySelector()

        with patch(SCORE_PATH, side_effect=(2, 2, 1)):
            result = selector.select(
                source_text="source",
                memories=(memory_a, memory_b, memory_c),
            )

        self.assertEqual(result, (memory_a, memory_b, memory_c))
        self.assertIs(result[0], memory_a)
        self.assertIs(result[1], memory_b)
        self.assertIs(result[2], memory_c)

    def test_all_zero_scores_return_exact_empty_tuple(self) -> None:
        memories = (
            _memory(key="memory_a", value="A"),
            _memory(key="memory_b", value="B"),
        )
        selector = RankedKeywordLearnedMemorySelector()

        with patch(SCORE_PATH, side_effect=(0, 0)) as score:
            result = selector.select(source_text="source", memories=memories)

        self.assertEqual(result, ())
        self.assertEqual(score.call_count, len(memories))

    def test_one_relevant_memory_returns_exact_singleton_identity(self) -> None:
        irrelevant = _memory(key="irrelevant", value="none")
        relevant = _memory(key="language", value="Rust")
        selector = RankedKeywordLearnedMemorySelector()

        with patch(SCORE_PATH, side_effect=(0, 1)):
            result = selector.select(
                source_text="Rust",
                memories=(irrelevant, relevant),
            )

        self.assertEqual(result, (relevant,))
        self.assertIs(result[0], relevant)

    def test_duplicate_relevant_entries_remain_distinct_positions(self) -> None:
        repeated = _memory(key="language", value="Rust")
        memories = (repeated, repeated)
        selector = RankedKeywordLearnedMemorySelector()

        with patch(SCORE_PATH, side_effect=(1, 1)) as score:
            result = selector.select(source_text="Rust", memories=memories)

        self.assertEqual(result, memories)
        self.assertIs(result[0], repeated)
        self.assertIs(result[1], repeated)
        self.assertEqual(score.call_count, 2)

    def test_real_scoring_preserves_input_and_is_deterministic(self) -> None:
        weak = _memory(key="preferred_language", value="Python")
        strong = _memory(key="preferred_language", value="Rust")
        zero = _memory(key="active_project", value="Hypatia")
        memories = (weak, zero, strong)
        original_memories = tuple(memories)
        original_values = tuple(
            LearnedMemory(kind=memory.kind, key=memory.key, value=memory.value)
            for memory in memories
        )
        selector = RankedKeywordLearnedMemorySelector()

        first = selector.select(
            source_text="Rust language",
            memories=memories,
        )
        second = selector.select(
            source_text="Rust language",
            memories=memories,
        )

        self.assertEqual(first, (strong, weak))
        self.assertEqual(second, first)
        self.assertIs(first[0], strong)
        self.assertIs(first[1], weak)
        self.assertEqual(memories, original_memories)
        self.assertEqual(memories, original_values)


if __name__ == "__main__":
    unittest.main()
