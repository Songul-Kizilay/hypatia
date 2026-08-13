from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from memory.LearnedMemory import LearnedMemory
from memory.LearnedMemoryCandidate import LearnedMemoryCandidate
from memory.LearnedMemoryCandidatePersistence import (
    persist_learned_memory_candidate,
)
from memory.MemoryManager import MemoryManager
from memory.MemoryRecord import MemoryRecord


class LearnedMemoryCandidatePersistenceTests(unittest.TestCase):
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
