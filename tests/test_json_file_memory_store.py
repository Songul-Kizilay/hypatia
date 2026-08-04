"""Unit tests for JSON-backed memory snapshot persistence."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import MemoryError
from memory.JsonFileMemoryStore import JsonFileMemoryStore
from memory.MemoryRecord import MemoryRecord


class JsonFileMemoryStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary_directory.name) / "memory.json"
        self.store = JsonFileMemoryStore(self.path)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_missing_file_loads_as_an_empty_snapshot(self) -> None:
        self.assertEqual(self.store.load(), [])

    def test_empty_valid_document_loads(self) -> None:
        self._write_document({"schema_version": 1, "records": []})

        self.assertEqual(self.store.load(), [])

    def test_single_record_loads_with_all_fields(self) -> None:
        created_at = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)
        self._write_document(
            {
                "schema_version": 1,
                "records": [
                    {
                        "memory_id": "memory-1",
                        "content": "Saved conversation",
                        "metadata": {"intent": "message"},
                        "tags": ["brain", "conversation"],
                        "created_at": created_at.isoformat(),
                        "updated_at": created_at.isoformat(),
                        "expires_at": None,
                    }
                ],
            }
        )

        records = self.store.load()

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].memory_id, "memory-1")
        self.assertEqual(records[0].content, "Saved conversation")
        self.assertEqual(records[0].metadata, {"intent": "message"})
        self.assertEqual(records[0].tags, frozenset({"brain", "conversation"}))
        self.assertEqual(records[0].created_at, created_at)
        self.assertEqual(records[0].updated_at, created_at)
        self.assertIsNone(records[0].expires_at)

    def test_tags_load_as_a_frozenset(self) -> None:
        self._write_document(
            {
                "schema_version": 1,
                "records": [self._record_document(tags=["brain", "conversation"])],
            }
        )

        self.assertIsInstance(self.store.load()[0].tags, frozenset)

    def test_duplicate_memory_ids_raise_memory_error(self) -> None:
        record = self._record_document()
        self._write_document({"schema_version": 1, "records": [record, record]})

        with self.assertRaises(MemoryError):
            self.store.load()

    def test_wrong_schema_version_raises_memory_error(self) -> None:
        self._write_document({"schema_version": 2, "records": []})

        with self.assertRaises(MemoryError):
            self.store.load()

    def test_invalid_json_raises_memory_error(self) -> None:
        self.path.write_text("{invalid", encoding="utf-8")

        with self.assertRaises(MemoryError):
            self.store.load()

    def test_timezone_naive_datetime_raises_memory_error(self) -> None:
        self._write_document(
            {
                "schema_version": 1,
                "records": [self._record_document(created_at="2026-08-04T12:00:00")],
            }
        )

        with self.assertRaises(MemoryError):
            self.store.load()

    def test_invalid_records_type_raises_memory_error(self) -> None:
        self._write_document({"schema_version": 1, "records": {}})

        with self.assertRaises(MemoryError):
            self.store.load()

    def test_save_and_load_round_trip(self) -> None:
        created_at = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)
        record = MemoryRecord(
            memory_id="memory-1",
            content="Saved conversation",
            metadata={"intent": "message"},
            tags=frozenset({"brain", "conversation"}),
            created_at=created_at,
            updated_at=created_at,
        )

        self.store.save([record])

        self.assertEqual(self.store.load(), [record])

    def test_save_creates_a_missing_parent_directory(self) -> None:
        nested_path = self.path.parent / "nested" / "memory.json"
        store = JsonFileMemoryStore(nested_path)

        store.save([])

        self.assertTrue(nested_path.exists())

    def test_save_writes_valid_json(self) -> None:
        self.store.save([MemoryRecord(memory_id="memory-1", content="Saved")])

        with self.path.open(encoding="utf-8") as file:
            document = json.load(file)

        self.assertEqual(document["schema_version"], 1)
        self.assertEqual(document["records"][0]["memory_id"], "memory-1")

    def test_save_replaces_an_existing_snapshot(self) -> None:
        self.store.save([MemoryRecord(memory_id="memory-1", content="Old")])

        self.store.save([MemoryRecord(memory_id="memory-2", content="New")])

        self.assertEqual(
            self.store.load(),
            [MemoryRecord(memory_id="memory-2", content="New")],
        )

    def test_failed_replace_preserves_existing_snapshot_and_cleans_temporary_file(
        self,
    ) -> None:
        original_record = MemoryRecord(memory_id="memory-1", content="Old")
        self.store.save([original_record])
        module = import_module("memory.JsonFileMemoryStore")

        with patch.object(module.os, "replace", side_effect=OSError("replace failed")):
            with self.assertRaises(MemoryError):
                self.store.save([MemoryRecord(memory_id="memory-2", content="New")])

        self.assertEqual(self.store.load(), [original_record])
        self.assertEqual(list(self.path.parent.glob(f".{self.path.name}.*.tmp")), [])

    def _write_document(self, document: dict[str, object]) -> None:
        self.path.write_text(json.dumps(document), encoding="utf-8")

    @staticmethod
    def _record_document(
        *,
        tags: list[str] | None = None,
        created_at: str = "2026-08-04T12:00:00+00:00",
    ) -> dict[str, object]:
        return {
            "memory_id": "memory-1",
            "content": "Saved conversation",
            "metadata": {},
            "tags": tags or ["brain"],
            "created_at": created_at,
            "updated_at": created_at,
            "expires_at": None,
        }


if __name__ == "__main__":
    unittest.main()
