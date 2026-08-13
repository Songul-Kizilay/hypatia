from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from memory.LearnedMemory import LearnedMemory
from memory.LearnedMemoryStore import load_learned_memories
from memory.MemoryManager import MemoryManager
from memory.MemoryRecord import MemoryRecord


class LearnedMemoryStoreTests(unittest.TestCase):
    @patch("memory.LearnedMemoryStore.collect_learned_memories")
    def test_loads_exact_snapshot_once_and_returns_collector_identity(
        self,
        collect_learned_memories,
    ) -> None:
        record_a = MemoryRecord(memory_id="record-a", content="content-a")
        record_b = MemoryRecord(memory_id="record-b", content="content-b")
        memory_manager = MagicMock(spec=MemoryManager)
        memory_manager.all.return_value = [record_a, record_b]
        sentinel_memories = (
            LearnedMemory(kind="preference", key="language", value="Python"),
            LearnedMemory(kind="user_fact", key="name", value="Songül"),
        )
        collect_learned_memories.return_value = sentinel_memories

        result = load_learned_memories(memory_manager)

        memory_manager.all.assert_called_once_with()
        collect_learned_memories.assert_called_once_with((record_a, record_b))
        self.assertIs(result, sentinel_memories)
        memory_manager.add.assert_not_called()
        memory_manager.update.assert_not_called()
        memory_manager.delete.assert_not_called()
