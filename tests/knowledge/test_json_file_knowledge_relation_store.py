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
        self.path.write_text(
            json.dumps({"schema_version": 2, "relations": []}), encoding="utf-8"
        )

        with self.assertRaisesRegex(KnowledgeError, "unsupported schema version"):
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
