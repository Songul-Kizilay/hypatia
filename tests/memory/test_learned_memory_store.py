from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from memory.LearnedMemory import LearnedMemory
from memory.LearnedMemoryStore import (
    load_latest_learned_memory,
    load_learned_memories,
)
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

    @patch("memory.LearnedMemoryStore.resolve_latest_learned_memory")
    @patch("memory.LearnedMemoryStore.load_learned_memories")
    def test_loads_and_resolves_latest_memory_once_with_identity_preserved(
        self,
        load_learned_memories,
        resolve_latest_learned_memory,
    ) -> None:
        memory_manager = MagicMock(spec=MemoryManager)
        memory_a = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="Python",
        )
        memory_b = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="Rust",
        )
        sentinel_memories = (memory_a, memory_b)
        load_learned_memories.return_value = sentinel_memories
        resolve_latest_learned_memory.return_value = memory_b

        result = load_latest_learned_memory(
            memory_manager,
            kind="preference",
            key="preferred_language",
        )

        load_learned_memories.assert_called_once_with(memory_manager)
        resolve_latest_learned_memory.assert_called_once_with(
            sentinel_memories,
            kind="preference",
            key="preferred_language",
        )
        self.assertIs(result, memory_b)
        memory_manager.add.assert_not_called()
        memory_manager.update.assert_not_called()
        memory_manager.delete.assert_not_called()

    @patch("memory.LearnedMemoryStore.resolve_latest_learned_memory")
    @patch("memory.LearnedMemoryStore.load_learned_memories")
    def test_propagates_none_from_latest_resolver(
        self,
        load_learned_memories,
        resolve_latest_learned_memory,
    ) -> None:
        memory_manager = MagicMock(spec=MemoryManager)
        sentinel_memories: tuple[LearnedMemory, ...] = ()
        load_learned_memories.return_value = sentinel_memories
        resolve_latest_learned_memory.return_value = None

        result = load_latest_learned_memory(
            memory_manager,
            kind="user_fact",
            key="name",
        )

        load_learned_memories.assert_called_once_with(memory_manager)
        resolve_latest_learned_memory.assert_called_once_with(
            sentinel_memories,
            kind="user_fact",
            key="name",
        )
        self.assertIsNone(result)
