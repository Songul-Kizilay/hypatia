"""Structural tests for the MemoryStore persistence contract."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from memory.MemoryRecord import MemoryRecord
from memory.MemoryStore import MemoryStore


class FakeMemoryStore:
    """Minimal in-memory implementation used to exercise the protocol."""

    def __init__(self) -> None:
        self.records: list[MemoryRecord] = []

    def load(self) -> list[MemoryRecord]:
        return list(self.records)

    def save(self, records: list[MemoryRecord]) -> None:
        self.records = list(records)


class MemoryStoreTests(unittest.TestCase):
    def test_empty_snapshot_can_be_loaded(self) -> None:
        store: MemoryStore = FakeMemoryStore()

        self.assertEqual(store.load(), [])

    def test_saved_snapshot_can_be_loaded(self) -> None:
        store: MemoryStore = FakeMemoryStore()
        records = [MemoryRecord(memory_id="memory-1", content="Saved memory")]

        store.save(records)

        self.assertEqual(store.load(), records)

    def test_save_does_not_retain_the_caller_list(self) -> None:
        store = FakeMemoryStore()
        records = [MemoryRecord(memory_id="memory-1", content="Saved memory")]

        store.save(records)
        records.append(MemoryRecord(memory_id="memory-2", content="New memory"))

        self.assertIsNot(store.records, records)
        self.assertEqual(len(store.load()), 1)


if __name__ == "__main__":
    unittest.main()
