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
    resolve_latest_learned_memory,
    select_latest_learned_memories,
)
from memory.MemoryRecord import MemoryRecord


class LearnedMemoryRetrievalTests(unittest.TestCase):
    def test_latest_view_empty_input_returns_exact_empty_tuple(self) -> None:
        self.assertEqual(select_latest_learned_memories(()), ())

    def test_latest_view_preserves_distinct_objects_and_order(self) -> None:
        preference = LearnedMemory(kind="preference", key="language", value="Python")
        goal = LearnedMemory(kind="goal", key="learning", value="Rust")
        memories = (preference, goal)

        result = select_latest_learned_memories(memories)

        self.assertEqual(result, memories)
        self.assertIs(result[0], preference)
        self.assertIs(result[1], goal)
        self.assertIs(memories[0], preference)

    def test_latest_view_retains_correction_last_occurrence_order(self) -> None:
        python = LearnedMemory(kind="preference", key="language", value="Python")
        goal = LearnedMemory(kind="goal", key="learning", value="Kali")
        rust = LearnedMemory(kind="preference", key="language", value="Rust")

        result = select_latest_learned_memories((python, goal, rust))

        self.assertEqual(result, (goal, rust))
        self.assertIs(result[0], goal)
        self.assertIs(result[1], rust)

    def test_latest_view_retains_multiple_corrections_in_final_order(self) -> None:
        python = LearnedMemory(kind="preference", key="language", value="Python")
        linux = LearnedMemory(kind="goal", key="learning", value="Linux")
        rust = LearnedMemory(kind="preference", key="language", value="Rust")
        kali = LearnedMemory(kind="goal", key="learning", value="Kali")
        go = LearnedMemory(kind="preference", key="language", value="Go")

        result = select_latest_learned_memories((python, linux, rust, kali, go))

        self.assertEqual(result, (kali, go))
        self.assertIs(result[0], kali)
        self.assertIs(result[1], go)

    def test_latest_view_uses_exact_case_sensitive_kind_and_key_groups(
        self,
    ) -> None:
        lower = LearnedMemory(kind="preference", key="language", value="Rust")
        upper = LearnedMemory(kind="preference", key="Language", value="Python")
        different_kind = LearnedMemory(kind="goal", key="language", value="Kali")

        result = select_latest_learned_memories((lower, upper, different_kind))

        self.assertEqual(result, (lower, upper, different_kind))
        self.assertIs(result[0], lower)
        self.assertIs(result[1], upper)
        self.assertIs(result[2], different_kind)

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

    def test_resolves_last_exact_match_by_identity(self) -> None:
        first_match = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="Python",
        )
        unrelated = LearnedMemory(
            kind="user_fact",
            key="name",
            value="Songül",
        )
        second_match = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="Rust",
        )
        latest_match = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="Go",
        )
        memories = (first_match, unrelated, second_match, latest_match)

        result = resolve_latest_learned_memory(
            memories,
            kind="preference",
            key="preferred_language",
        )

        self.assertIs(result, latest_match)

    @patch("memory.LearnedMemoryRetrieval.find_learned_memories")
    def test_latest_resolution_delegates_exact_lookup_once(
        self,
        find_learned_memories,
    ) -> None:
        memories = (LearnedMemory(kind="preference", key="language", value="Python"),)
        latest_match = LearnedMemory(
            kind="preference",
            key="language",
            value="Rust",
        )
        find_learned_memories.return_value = (memories[0], latest_match)

        result = resolve_latest_learned_memory(
            memories,
            kind="preference",
            key="language",
        )

        self.assertIs(result, latest_match)
        find_learned_memories.assert_called_once_with(
            memories,
            kind="preference",
            key="language",
        )

    @patch("memory.LearnedMemoryRetrieval.find_learned_memories")
    def test_latest_resolution_returns_none_or_single_match_identity(
        self,
        find_learned_memories,
    ) -> None:
        memories: tuple[LearnedMemory, ...] = ()
        single_match = LearnedMemory(
            kind="user_fact",
            key="name",
            value="Songül",
        )
        find_learned_memories.side_effect = [(), (single_match,)]

        no_match = resolve_latest_learned_memory(
            memories,
            kind="user_fact",
            key="name",
        )
        one_match = resolve_latest_learned_memory(
            memories,
            kind="user_fact",
            key="name",
        )

        self.assertIsNone(no_match)
        self.assertIs(one_match, single_match)
        self.assertEqual(
            find_learned_memories.call_args_list,
            [
                call(memories, kind="user_fact", key="name"),
                call(memories, kind="user_fact", key="name"),
            ],
        )
