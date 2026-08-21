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
from memory.JsonFileMemoryStore import (
    MAX_MEMORY_CONTENT_CHARACTERS,
    MAX_MEMORY_ID_CHARACTERS,
    MAX_MEMORY_TAG_CHARACTERS,
    JsonFileMemoryStore,
)
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

    def test_wrong_schema_version_raises_memory_error_without_coercion(self) -> None:
        for schema_version in (2, True):
            with self.subTest(schema_version=schema_version):
                self._write_document({"schema_version": schema_version, "records": []})

                with self.assertRaisesRegex(MemoryError, "unsupported schema"):
                    self.store.load()

    def test_invalid_json_raises_memory_error(self) -> None:
        self.path.write_text("{invalid", encoding="utf-8")

        with self.assertRaises(MemoryError):
            self.store.load()

    def test_oversized_file_is_rejected_before_json_decoding(self) -> None:
        self.path.write_bytes(b"{}")

        with (
            patch("memory.JsonFileMemoryStore.MAX_MEMORY_STORE_BYTES", 1),
            patch(
                "memory.JsonFileMemoryStore.json.loads",
                side_effect=AssertionError("Oversized JSON must not be decoded."),
            ),
        ):
            with self.assertRaisesRegex(MemoryError, "too large"):
                self.store.load()

    def test_load_uses_open_descriptor_without_preflight_stat(self) -> None:
        records = [self._record()]
        self.store.save(records)

        with patch.object(
            Path,
            "stat",
            side_effect=AssertionError("Memory load must not preflight file size."),
        ):
            loaded = self.store.load()

        self.assertEqual(loaded, records)

    def test_record_bound_is_checked_before_parse_and_serialization(self) -> None:
        records = [self._record("memory-1"), self._record("memory-2")]
        with patch("memory.JsonFileMemoryStore.MAX_MEMORY_RECORDS", 2):
            self.store.save(records)
            self.assertEqual(self.store.load(), records)
        self._write_document(
            {
                "schema_version": 1,
                "records": [
                    self._record_document(memory_id="memory-1"),
                    self._record_document(memory_id="memory-2"),
                ],
            }
        )

        with (
            patch("memory.JsonFileMemoryStore.MAX_MEMORY_RECORDS", 1),
            patch.object(
                self.store,
                "_parse_record",
                side_effect=AssertionError("Oversized records must not be parsed."),
            ),
        ):
            with self.assertRaisesRegex(MemoryError, "too many records"):
                self.store.load()

        with (
            patch("memory.JsonFileMemoryStore.MAX_MEMORY_RECORDS", 1),
            patch.object(
                self.store,
                "_serialize_record",
                side_effect=AssertionError("Oversized records must not be serialized."),
            ),
        ):
            with self.assertRaisesRegex(MemoryError, "too many records"):
                self.store.save(records)

    def test_id_and_content_bounds_apply_before_serialization(self) -> None:
        maximum_record = self._record(
            memory_id="i" * MAX_MEMORY_ID_CHARACTERS,
            content="ç" * MAX_MEMORY_CONTENT_CHARACTERS,
        )
        self.store.save([maximum_record])
        self.assertEqual(self.store.load(), [maximum_record])

        invalid_records = (
            self._record(memory_id="i" * (MAX_MEMORY_ID_CHARACTERS + 1)),
            self._record(content="c" * (MAX_MEMORY_CONTENT_CHARACTERS + 1)),
        )
        error_patterns = ("memory ID.*too long", "memory content.*too long")
        for invalid_record, error_pattern in zip(
            invalid_records,
            error_patterns,
            strict=True,
        ):
            with self.subTest(error_pattern=error_pattern):
                self._write_document(
                    {
                        "schema_version": 1,
                        "records": [
                            self._record_document(
                                memory_id=invalid_record.memory_id,
                                content=invalid_record.content,
                            )
                        ],
                    }
                )
                with self.assertRaisesRegex(MemoryError, error_pattern):
                    self.store.load()
                with patch.object(
                    self.store,
                    "_serialize_record",
                    side_effect=AssertionError(
                        "Oversized fields must not be serialized."
                    ),
                ):
                    with self.assertRaisesRegex(MemoryError, error_pattern):
                        self.store.save([invalid_record])

    def test_metadata_entry_bound_applies_on_load_and_before_serialization(
        self,
    ) -> None:
        records = [
            self._record("memory-1", metadata={"first": 1}),
            self._record("memory-2", metadata={"second": 2}),
        ]
        with patch("memory.JsonFileMemoryStore.MAX_MEMORY_METADATA_ENTRIES", 2):
            self.store.save(records)
            self.assertEqual(self.store.load(), records)
        self._write_document(
            {
                "schema_version": 1,
                "records": [
                    self._record_document(
                        memory_id=record.memory_id,
                        metadata=dict(record.metadata),
                    )
                    for record in records
                ],
            }
        )

        with patch("memory.JsonFileMemoryStore.MAX_MEMORY_METADATA_ENTRIES", 1):
            with self.assertRaisesRegex(MemoryError, "too many metadata entries"):
                self.store.load()
            with patch.object(
                self.store,
                "_serialize_record",
                side_effect=AssertionError("Excess metadata must not be serialized."),
            ):
                with self.assertRaisesRegex(
                    MemoryError,
                    "too many metadata entries",
                ):
                    self.store.save(records)

    def test_exact_metadata_utf8_aggregate_bound_is_enforced(self) -> None:
        records = [
            self._record("memory-1", metadata={"şehir": "İzmir"}),
            self._record("memory-2", metadata={"dil": "Türkçe"}),
        ]
        exact_metadata_bytes = sum(
            len(
                json.dumps(
                    dict(record.metadata),
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8")
            )
            for record in records
        )

        with patch(
            "memory.JsonFileMemoryStore.MAX_MEMORY_METADATA_UTF8_BYTES",
            exact_metadata_bytes,
        ):
            self.store.save(records)
            self.assertEqual(self.store.load(), records)
        exact_snapshot = self.path.read_bytes()

        with patch(
            "memory.JsonFileMemoryStore.MAX_MEMORY_METADATA_UTF8_BYTES",
            exact_metadata_bytes - 1,
        ):
            with self.assertRaisesRegex(MemoryError, "metadata is too large"):
                self.store.save(records)

        self.assertEqual(self.path.read_bytes(), exact_snapshot)
        self.assertEqual(list(self.path.parent.glob(f".{self.path.name}.*.tmp")), [])

    def test_tag_count_and_character_bounds_apply_before_serialization(self) -> None:
        records = [
            self._record("memory-1", tags=frozenset({"first"})),
            self._record("memory-2", tags=frozenset({"second"})),
        ]
        with patch("memory.JsonFileMemoryStore.MAX_MEMORY_TAGS", 2):
            self.store.save(records)
            self.assertEqual(self.store.load(), records)
        self._write_document(
            {
                "schema_version": 1,
                "records": [
                    self._record_document(
                        memory_id=record.memory_id,
                        tags=sorted(record.tags),
                    )
                    for record in records
                ],
            }
        )

        with patch("memory.JsonFileMemoryStore.MAX_MEMORY_TAGS", 1):
            with self.assertRaisesRegex(MemoryError, "too many tags"):
                self.store.load()
            with patch.object(
                self.store,
                "_serialize_record",
                side_effect=AssertionError("Excess tags must not be serialized."),
            ):
                with self.assertRaisesRegex(MemoryError, "too many tags"):
                    self.store.save(records)

        self._write_document(
            {
                "schema_version": 1,
                "records": [self._record_document(tags=["same", "same"])],
            }
        )
        with (
            patch("memory.JsonFileMemoryStore.MAX_MEMORY_TAGS", 1),
            patch.object(
                self.store,
                "_parse_record",
                side_effect=AssertionError("Excess raw tags must not be parsed."),
            ),
        ):
            with self.assertRaisesRegex(MemoryError, "too many tags"):
                self.store.load()

        maximum_tag_record = self._record(
            tags=frozenset({"t" * MAX_MEMORY_TAG_CHARACTERS})
        )
        self.store.save([maximum_tag_record])
        self.assertEqual(self.store.load(), [maximum_tag_record])
        oversized_tag_record = self._record(
            tags=frozenset({"t" * (MAX_MEMORY_TAG_CHARACTERS + 1)})
        )
        self._write_document(
            {
                "schema_version": 1,
                "records": [
                    self._record_document(tags=sorted(oversized_tag_record.tags))
                ],
            }
        )
        with self.assertRaisesRegex(MemoryError, "tag.*too long"):
            self.store.load()
        with patch.object(
            self.store,
            "_serialize_record",
            side_effect=AssertionError("Oversized tags must not be serialized."),
        ):
            with self.assertRaisesRegex(MemoryError, "tag.*too long"):
                self.store.save([oversized_tag_record])

    def test_exact_utf8_file_bound_preserves_the_snapshot(self) -> None:
        records = [
            self._record(
                content="Kayıt ş",
                metadata={"şehir": "İzmir"},
                tags=frozenset({"hafıza"}),
            )
        ]
        self.store.save(records)
        exact_snapshot = self.path.read_bytes()

        with patch(
            "memory.JsonFileMemoryStore.MAX_MEMORY_STORE_BYTES",
            len(exact_snapshot),
        ):
            self.store.save(records)

        self.assertEqual(self.path.read_bytes(), exact_snapshot)
        with patch(
            "memory.JsonFileMemoryStore.MAX_MEMORY_STORE_BYTES",
            len(exact_snapshot) - 1,
        ):
            with self.assertRaisesRegex(MemoryError, "too large"):
                self.store.save(records)

        self.assertEqual(self.path.read_bytes(), exact_snapshot)
        self.assertEqual(list(self.path.parent.glob(f".{self.path.name}.*.tmp")), [])

    def test_invalid_save_preserves_the_existing_snapshot(self) -> None:
        original = [self._record()]
        self.store.save(original)
        invalid_snapshots = (
            [self._record(memory_id="")],
            [self._record(content=" ")],
            [self._record("duplicate"), self._record("duplicate")],
            [
                self._record(
                    created_at=datetime(2026, 8, 4, 12, 0),
                )
            ],
        )

        for invalid_snapshot in invalid_snapshots:
            with self.subTest(invalid_snapshot=invalid_snapshot):
                with self.assertRaises(MemoryError):
                    self.store.save(invalid_snapshot)
                self.assertEqual(self.store.load(), original)

    def test_circular_metadata_is_rejected_before_writing(self) -> None:
        original = [self._record()]
        self.store.save(original)
        circular: dict[str, object] = {}
        circular["self"] = circular

        with self.assertRaisesRegex(MemoryError, "invalid metadata"):
            self.store.save([self._record(metadata=circular)])

        self.assertEqual(self.store.load(), original)
        self.assertEqual(list(self.path.parent.glob(f".{self.path.name}.*.tmp")), [])

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
        memory_id: str = "memory-1",
        content: str = "Saved conversation",
        metadata: dict[str, object] | None = None,
        tags: list[str] | None = None,
        created_at: str = "2026-08-04T12:00:00+00:00",
    ) -> dict[str, object]:
        return {
            "memory_id": memory_id,
            "content": content,
            "metadata": {} if metadata is None else metadata,
            "tags": ["brain"] if tags is None else tags,
            "created_at": created_at,
            "updated_at": created_at,
            "expires_at": None,
        }

    @staticmethod
    def _record(
        memory_id: str = "memory-1",
        *,
        content: str = "Saved conversation",
        metadata: dict[str, object] | None = None,
        tags: frozenset[str] | None = None,
        created_at: datetime | None = datetime(2026, 8, 4, 12, 0, tzinfo=UTC),
    ) -> MemoryRecord:
        return MemoryRecord(
            memory_id=memory_id,
            content=content,
            metadata={} if metadata is None else metadata,
            tags=frozenset({"brain"}) if tags is None else tags,
            created_at=created_at,
            updated_at=created_at,
        )


if __name__ == "__main__":
    unittest.main()
