"""Unit tests for the in-memory MemoryManager."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from eventbus.EventBus import EventBus
from memory.MemoryManager import MemoryManager


class MemoryManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bus = EventBus()
        self.memory = MemoryManager(self.bus)

    def test_add_creates_retrievable_record(self) -> None:
        record = self.memory.add("A saved fact")

        self.assertEqual(self.memory.get(record.memory_id), record)
        self.assertEqual(self.memory.count(), 1)

    def test_add_rejects_blank_content(self) -> None:
        with self.assertRaises(ValueError):
            self.memory.add("  ")

    def test_get_returns_none_for_missing_record(self) -> None:
        self.assertIsNone(self.memory.get("missing"))

    def test_update_replaces_selected_fields(self) -> None:
        record = self.memory.add("Old", tags={"draft"})

        updated = self.memory.update(record.memory_id, content="New", tags={"final"})

        self.assertIsNotNone(updated)
        self.assertEqual(updated.content, "New")
        self.assertEqual(updated.tags, frozenset({"final"}))
        self.assertGreaterEqual(updated.updated_at, updated.created_at)

    def test_update_returns_none_for_missing_record(self) -> None:
        self.assertIsNone(self.memory.update("missing", content="New"))

    def test_delete_reports_existence(self) -> None:
        record = self.memory.add("Delete me")

        self.assertTrue(self.memory.delete(record.memory_id))
        self.assertFalse(self.memory.delete(record.memory_id))

    def test_search_filters_by_text_and_tags(self) -> None:
        self.memory.add("Python planner", tags={"code", "planner"})
        self.memory.add("Python memory", tags={"code", "memory"})

        matches = self.memory.search("python", tags={"planner"})

        self.assertEqual([record.content for record in matches], ["Python planner"])

    def test_expired_record_is_not_returned(self) -> None:
        expired_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        record = self.memory.add("Temporary", expires_at=expired_at)

        self.assertIsNone(self.memory.get(record.memory_id))
        self.assertEqual(self.memory.count(), 0)

    def test_clear_removes_records_and_reports_count(self) -> None:
        self.memory.add("One")
        self.memory.add("Two")

        self.assertEqual(self.memory.clear(), 2)
        self.assertEqual(self.memory.count(), 0)
