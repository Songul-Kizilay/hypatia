"""Tests for atomic JSON persistence of explicit knowledge relations."""

from __future__ import annotations

import json
import tempfile
import unittest
from importlib import import_module
from pathlib import Path
from unittest.mock import patch

from core.Exceptions import KnowledgeError
from knowledge.JsonFileKnowledgeRelationStore import JsonFileKnowledgeRelationStore
from knowledge.KnowledgeGraph import KnowledgeGraphRelation
from knowledge.KnowledgeRelationRecord import KnowledgeRelationRecord


class JsonFileKnowledgeRelationStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary_directory.name) / "relations.json"
        self.store = JsonFileKnowledgeRelationStore(self.path)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_missing_file_loads_an_empty_relation_snapshot(self) -> None:
        self.assertEqual(self.store.load(), [])

    def test_save_and_load_round_trip_preserves_relation_order(self) -> None:
        records = [
            self._record("source-1", "target-1"),
            self._record("source-2", "target-2"),
        ]

        self.store.save(records)

        self.assertEqual(self.store.load(), records)
        document = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(document["schema_version"], 1)
        self.assertEqual(document["relations"][0]["source_document_id"], "source-1")

    def test_rejects_invalid_or_duplicate_persisted_relations(self) -> None:
        self.path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "relations": [
                        {
                            "source_document_id": "source",
                            "relation": "related_to",
                            "target_document_id": "target",
                        },
                        {
                            "source_document_id": "source",
                            "relation": "related_to",
                            "target_document_id": "target",
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            KnowledgeError, "Knowledge relation store contains duplicate relations."
        ):
            self.store.load()

    def test_rejects_unsupported_schema_without_coercing_data(self) -> None:
        for schema_version in (2, True):
            with self.subTest(schema_version=schema_version):
                self.path.write_text(
                    json.dumps({"schema_version": schema_version, "relations": []}),
                    encoding="utf-8",
                )

                with self.assertRaisesRegex(
                    KnowledgeError, "unsupported schema version"
                ):
                    self.store.load()

    def test_oversized_file_is_rejected_before_json_decoding(self) -> None:
        self.path.write_bytes(b"{}")

        with (
            patch(
                "knowledge.JsonFileKnowledgeRelationStore."
                "MAX_KNOWLEDGE_RELATION_STORE_BYTES",
                1,
            ),
            patch(
                "knowledge.JsonFileKnowledgeRelationStore.json.loads",
                side_effect=AssertionError("Oversized JSON must not be decoded."),
            ),
        ):
            with self.assertRaisesRegex(KnowledgeError, "too large"):
                self.store.load()

    def test_load_uses_open_descriptor_without_preflight_stat(self) -> None:
        records = [self._record("source", "target")]
        self.store.save(records)

        with patch.object(
            Path,
            "stat",
            side_effect=AssertionError("Relation load must not preflight file size."),
        ):
            loaded = self.store.load()

        self.assertEqual(loaded, records)

    def test_relation_bound_is_checked_before_parse_and_serialization(self) -> None:
        record = self._record("source", "target")
        self.store.save([record])

        with (
            patch(
                "knowledge.JsonFileKnowledgeRelationStore.MAX_KNOWLEDGE_RELATIONS",
                0,
            ),
            patch.object(
                self.store,
                "_parse_record",
                side_effect=AssertionError("Oversized relations must not be parsed."),
            ),
        ):
            with self.assertRaisesRegex(KnowledgeError, "too many relations"):
                self.store.load()

        with (
            patch(
                "knowledge.JsonFileKnowledgeRelationStore.MAX_KNOWLEDGE_RELATIONS",
                0,
            ),
            patch.object(
                self.store,
                "_serialize_record",
                side_effect=AssertionError(
                    "Oversized relations must not be serialized."
                ),
            ),
        ):
            with self.assertRaisesRegex(KnowledgeError, "too many relations"):
                self.store.save([record])

    def test_document_id_bound_applies_on_load_and_before_serialization(self) -> None:
        oversized_id = "s" * 1_025
        record = self._record(oversized_id, "target")
        document = {
            "schema_version": 1,
            "relations": [
                {
                    "source_document_id": oversized_id,
                    "relation": "related_to",
                    "target_document_id": "target",
                }
            ],
        }
        self.path.write_text(json.dumps(document), encoding="utf-8")

        with self.assertRaisesRegex(KnowledgeError, "document ID.*too long"):
            self.store.load()
        with patch.object(
            self.store,
            "_serialize_record",
            side_effect=AssertionError("Oversized IDs must not be serialized."),
        ):
            with self.assertRaisesRegex(KnowledgeError, "document ID.*too long"):
                self.store.save([record])

    def test_exact_count_and_utf8_byte_bounds_preserve_the_snapshot(self) -> None:
        record = self._record("kaynak-ş", "hedef-ğ")

        with patch(
            "knowledge.JsonFileKnowledgeRelationStore.MAX_KNOWLEDGE_RELATIONS",
            1,
        ):
            self.store.save([record])
            self.assertEqual(self.store.load(), [record])
        exact_snapshot = self.path.read_bytes()

        with patch(
            "knowledge.JsonFileKnowledgeRelationStore."
            "MAX_KNOWLEDGE_RELATION_STORE_BYTES",
            len(exact_snapshot),
        ):
            self.store.save([record])

        self.assertEqual(self.path.read_bytes(), exact_snapshot)
        with patch(
            "knowledge.JsonFileKnowledgeRelationStore."
            "MAX_KNOWLEDGE_RELATION_STORE_BYTES",
            len(exact_snapshot) - 1,
        ):
            with self.assertRaisesRegex(KnowledgeError, "too large"):
                self.store.save([record])

        self.assertEqual(self.path.read_bytes(), exact_snapshot)
        self.assertEqual(list(self.path.parent.glob(f".{self.path.name}.*.tmp")), [])

    def test_truncated_valid_prefix_on_load_fails_safely(self) -> None:
        records = [
            self._record("source-1", "target-1"),
            self._record("source-2", "target-2"),
        ]
        self.store.save(records)
        original_bytes = self.path.read_bytes()

        self.path.write_bytes(original_bytes[: len(original_bytes) // 2])

        with self.assertRaises(KnowledgeError):
            self.store.load()

    def test_failed_replace_preserves_existing_snapshot_and_cleans_temp_file(
        self,
    ) -> None:
        original = [self._record("source", "target")]
        self.store.save(original)
        module = import_module("knowledge.JsonFileKnowledgeRelationStore")

        with patch.object(module.os, "replace", side_effect=OSError("replace failed")):
            with self.assertRaises(KnowledgeError):
                self.store.save([self._record("other-source", "other-target")])

        self.assertEqual(self.store.load(), original)
        self.assertEqual(list(self.path.parent.glob(f".{self.path.name}.*.tmp")), [])

    @staticmethod
    def _record(
        source_document_id: str, target_document_id: str
    ) -> KnowledgeRelationRecord:
        return KnowledgeRelationRecord(
            source_document_id,
            KnowledgeGraphRelation.RELATED_TO,
            target_document_id,
        )
