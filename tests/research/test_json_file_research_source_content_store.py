"""Tests for strict atomic accepted-source content persistence."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from core.Exceptions import ResearchError
from research.JsonFileResearchSourceContentStore import (
    JsonFileResearchSourceContentStore,
)
from research.ResearchSource import ResearchSource
from research.ResearchSourceContentRecord import ResearchSourceContentRecord


class JsonFileResearchSourceContentStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.path = Path(self.temporary_directory.name) / "research" / "content.json"
        self.store = JsonFileResearchSourceContentStore(self.path)
        source = ResearchSource(
            url="https://example.com/research",
            title="Example",
            content="Persisted evidence.",
            content_type="text/plain",
            fetched_at=datetime(2026, 8, 21, 1, 0, tzinfo=UTC),
        )
        self.record = ResearchSourceContentRecord.from_source(
            source,
            "document-1",
            datetime(2026, 8, 21, 1, 1, tzinfo=UTC),
        )

    def test_absent_store_is_empty_and_round_trip_preserves_record(self) -> None:
        self.assertEqual(self.store.load(), [])

        self.store.save([self.record])

        self.assertEqual(self.store.load(), [self.record])
        document = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(document["schema_version"], 2)
        self.assertEqual(
            document["records"][0]["content_sha256"], self.record.content_sha256
        )

    def test_load_rejects_unknown_schema_fields_and_tampered_content(self) -> None:
        self.store.save([self.record])
        valid = json.loads(self.path.read_text(encoding="utf-8"))
        cases = []
        unknown_schema = {**valid, "schema_version": 3}
        cases.append((unknown_schema, "unsupported schema"))
        boolean_schema = {**valid, "schema_version": True}
        cases.append((boolean_schema, "unsupported schema"))
        unknown_field = {**valid, "unexpected": True}
        cases.append((unknown_field, "invalid fields"))
        tampered = json.loads(json.dumps(valid))
        tampered["records"][0]["content"] = "Corrupted evidence."
        cases.append((tampered, "fingerprint"))

        for document, message in cases:
            with self.subTest(message=message):
                self.path.write_text(json.dumps(document), encoding="utf-8")
                with self.assertRaisesRegex(ResearchError, message):
                    self.store.load()

    def test_truncated_valid_prefix_on_load_fails_safely(self) -> None:
        self.store.save([self.record])
        original_bytes = self.path.read_bytes()

        self.path.write_bytes(original_bytes[: len(original_bytes) // 2])

        with self.assertRaises(ResearchError):
            self.store.load()

    def test_save_rejects_duplicate_document_ids(self) -> None:
        with self.assertRaisesRegex(ResearchError, "document IDs"):
            self.store.save(
                [self.record, replace(self.record, url="https://example.com/other")]
            )

    def test_one_url_may_have_several_content_versions(self) -> None:
        # The same URL can serve different text over time; each version is its
        # own immutable record, never collapsed into one document per URL.
        version = replace(self.record, document_id="document-2")

        self.store.save([self.record, version])

        self.assertEqual(
            [record.document_id for record in self.store.load()],
            [self.record.document_id, "document-2"],
        )

    def test_save_enforces_record_total_content_and_serialized_file_limits(
        self,
    ) -> None:
        with (
            patch.object(JsonFileResearchSourceContentStore, "_MAXIMUM_RECORDS", 0),
            self.assertRaisesRegex(ResearchError, "too many records"),
        ):
            self.store.save([self.record])
        with (
            patch.object(
                JsonFileResearchSourceContentStore,
                "_MAXIMUM_TOTAL_CONTENT_BYTES",
                self.record.content_byte_count - 1,
            ),
            self.assertRaisesRegex(ResearchError, "content is too large"),
        ):
            self.store.save([self.record])
        with (
            patch.object(
                JsonFileResearchSourceContentStore,
                "_MAXIMUM_STORE_FILE_BYTES",
                10,
            ),
            self.assertRaisesRegex(ResearchError, "store is too large"),
        ):
            self.store.save([self.record])

    def test_load_rejects_oversized_file_before_json_parsing(self) -> None:
        self.path.parent.mkdir(parents=True)
        self.path.write_bytes(b"x" * 17)

        with (
            patch.object(
                JsonFileResearchSourceContentStore,
                "_MAXIMUM_STORE_FILE_BYTES",
                16,
            ),
            patch(
                "research.JsonFileResearchSourceContentStore.json.loads",
                side_effect=AssertionError("Oversized JSON must not be decoded."),
            ),
            self.assertRaisesRegex(ResearchError, "store is too large"),
        ):
            self.store.load()

    def test_load_uses_the_open_descriptor_without_a_preflight_stat(self) -> None:
        self.store.save([self.record])

        with patch.object(
            Path,
            "stat",
            side_effect=AssertionError("Content load must not preflight file size."),
        ):
            loaded = self.store.load()

        self.assertEqual(loaded, [self.record])

    def test_utf8_file_bound_is_exact_and_preserves_the_previous_snapshot(
        self,
    ) -> None:
        unicode_record = ResearchSourceContentRecord.from_source(
            ResearchSource(
                url=self.record.url,
                title="Songül araştırması",
                content="Kanıt içeriği.",
                content_type=self.record.content_type,
                fetched_at=self.record.fetched_at,
            ),
            self.record.document_id,
            self.record.stored_at,
        )
        self.store.save([unicode_record])
        exact_snapshot = self.path.read_bytes()

        with patch.object(
            JsonFileResearchSourceContentStore,
            "_MAXIMUM_STORE_FILE_BYTES",
            len(exact_snapshot),
        ):
            self.store.save([unicode_record])

        self.assertEqual(self.path.read_bytes(), exact_snapshot)
        with patch.object(
            JsonFileResearchSourceContentStore,
            "_MAXIMUM_STORE_FILE_BYTES",
            len(exact_snapshot) - 1,
        ):
            with self.assertRaisesRegex(ResearchError, "store is too large"):
                self.store.save([unicode_record])

        self.assertEqual(self.path.read_bytes(), exact_snapshot)
        self.assertEqual(list(self.path.parent.glob(".content.json.*.tmp")), [])

    def test_failed_atomic_replace_preserves_previous_snapshot_and_cleans_temp(
        self,
    ) -> None:
        self.store.save([self.record])
        original_bytes = self.path.read_bytes()
        replacement = replace(
            self.record,
            document_id="document-2",
            url="https://example.com/other",
        )

        with (
            patch(
                "research.JsonFileResearchSourceContentStore.os.replace",
                side_effect=OSError("disk failure"),
            ),
            self.assertRaisesRegex(ResearchError, "Unable to write"),
        ):
            self.store.save([replacement])

        self.assertEqual(self.path.read_bytes(), original_bytes)
        self.assertEqual(self.store.load(), [self.record])
        self.assertEqual(list(self.path.parent.glob(".content.json.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
