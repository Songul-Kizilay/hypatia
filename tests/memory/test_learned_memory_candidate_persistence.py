from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from memory.LearnedMemory import LearnedMemory
from memory.LearnedMemoryCandidate import (
    LearnedMemoryCandidate,
    LearnedMemoryCandidateBatch,
)
from memory.LearnedMemoryCandidatePersistence import (
    persist_learned_memory_candidate,
    persist_learned_memory_candidate_batch,
)
from memory.MemoryManager import MemoryManager
from memory.MemoryRecord import MemoryRecord


class LearnedMemoryCandidatePersistenceTests(unittest.TestCase):
    def test_batch_delegates_in_order_and_preserves_positional_results(
        self,
    ) -> None:
        memory_manager = MagicMock(spec=MemoryManager)
        candidates = tuple(
            LearnedMemoryCandidate(
                memory=LearnedMemory(
                    kind="preference",
                    key=f"key-{index}",
                    value=f"value-{index}",
                ),
                source_text=f"source-{index}",
            )
            for index in range(3)
        )
        batch = LearnedMemoryCandidateBatch(
            source_text="  exact batch source  ",
            candidates=candidates,
        )
        record_a = MemoryRecord(memory_id="record-a", content="value-0")
        record_c = MemoryRecord(memory_id="record-c", content="value-2")

        with patch(
            "memory.LearnedMemoryCandidatePersistence."
            "persist_learned_memory_candidate",
            side_effect=(record_a, None, record_c),
        ) as persist:
            result = persist_learned_memory_candidate_batch(
                memory_manager,
                batch,
            )

        self.assertEqual(result, (record_a, None, record_c))
        self.assertIs(result[0], record_a)
        self.assertIs(result[2], record_c)
        self.assertEqual(
            persist.call_args_list,
            [
                call(memory_manager, candidates[0]),
                call(memory_manager, candidates[1]),
                call(memory_manager, candidates[2]),
            ],
        )
        self.assertIs(batch.candidates, candidates)
        self.assertEqual(batch.source_text, "  exact batch source  ")

    def test_empty_batch_returns_exact_empty_tuple_without_delegation(
        self,
    ) -> None:
        memory_manager = MagicMock(spec=MemoryManager)
        batch = LearnedMemoryCandidateBatch(
            source_text="anything",
            candidates=(),
        )

        with patch(
            "memory.LearnedMemoryCandidatePersistence."
            "persist_learned_memory_candidate",
        ) as persist:
            result = persist_learned_memory_candidate_batch(
                memory_manager,
                batch,
            )

        self.assertEqual(result, ())
        persist.assert_not_called()

    def test_delegates_exact_candidate_memory_and_returns_record_identity(
        self,
    ) -> None:
        memory_manager = MagicMock(spec=MemoryManager)
        memory = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="  Rust  ",
        )
        candidate = LearnedMemoryCandidate(
            memory=memory,
            source_text="  Ben artık Rust tercih ediyorum.  ",
        )
        sentinel_record = MemoryRecord(
            memory_id="candidate-record",
            content="  Rust  ",
        )

        with patch(
            "memory.LearnedMemoryCandidatePersistence."
            "correct_learned_memory_value_if_changed",
            return_value=sentinel_record,
        ) as correct:
            result = persist_learned_memory_candidate(
                memory_manager,
                candidate,
            )

        correct.assert_called_once_with(
            memory_manager,
            kind="preference",
            key="preferred_language",
            value="  Rust  ",
        )
        self.assertIs(result, sentinel_record)
        self.assertIs(candidate.memory, memory)
        self.assertEqual(
            candidate.source_text,
            "  Ben artık Rust tercih ediyorum.  ",
        )

    def test_propagates_exact_none_from_existing_correction_seam(self) -> None:
        memory_manager = MagicMock(spec=MemoryManager)
        candidate = LearnedMemoryCandidate(
            memory=LearnedMemory(
                kind="preference",
                key="preferred_language",
                value="Python",
            ),
            source_text="Python tercih ediyorum.",
        )

        with patch(
            "memory.LearnedMemoryCandidatePersistence."
            "correct_learned_memory_value_if_changed",
            return_value=None,
        ) as correct:
            result = persist_learned_memory_candidate(
                memory_manager,
                candidate,
            )

        correct.assert_called_once_with(
            memory_manager,
            kind="preference",
            key="preferred_language",
            value="Python",
        )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
