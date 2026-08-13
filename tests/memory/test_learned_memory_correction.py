from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from memory.LearnedMemory import LearnedMemory
from memory.LearnedMemoryCorrection import correct_learned_memory_value
from memory.MemoryManager import MemoryManager
from memory.MemoryRecord import MemoryRecord


class LearnedMemoryCorrectionTests(unittest.TestCase):
    @patch("memory.LearnedMemoryCorrection.correct_learned_memory")
    def test_constructs_exact_memory_and_preserves_record_identity(
        self,
        correct_learned_memory,
    ) -> None:
        memory_manager = MagicMock(spec=MemoryManager)
        sentinel_record = MemoryRecord(
            memory_id="corrected-record",
            content="content",
        )
        correct_learned_memory.return_value = sentinel_record

        result = correct_learned_memory_value(
            memory_manager,
            kind="preference",
            key="preferred_language",
            value="  Rust  ",
        )

        correct_learned_memory.assert_called_once_with(
            memory_manager,
            LearnedMemory(
                kind="preference",
                key="preferred_language",
                value="  Rust  ",
            ),
        )
        self.assertIs(result, sentinel_record)
        memory_manager.add.assert_not_called()
        memory_manager.update.assert_not_called()
        memory_manager.delete.assert_not_called()
