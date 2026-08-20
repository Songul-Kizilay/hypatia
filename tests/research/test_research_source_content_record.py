"""Tests for integrity-bound accepted research source content."""

from __future__ import annotations

import hashlib
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import patch

from core.Exceptions import ResearchError
from research.ResearchSource import ResearchSource
from research.ResearchSourceContentRecord import ResearchSourceContentRecord


class ResearchSourceContentRecordTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fetched_at = datetime(2026, 8, 21, 1, 0, tzinfo=UTC)
        self.stored_at = datetime(2026, 8, 21, 1, 1, tzinfo=UTC)
        self.source = ResearchSource(
            url="https://example.com/research",
            title="Example",
            content="Türkçe evidence.",
            content_type="TEXT/PLAIN",
            fetched_at=self.fetched_at,
        )

    def test_from_source_binds_exact_utf8_content_and_provenance(self) -> None:
        record = ResearchSourceContentRecord.from_source(
            self.source,
            " document-1 ",
            self.stored_at,
        )
        encoded = self.source.content.encode("utf-8")

        self.assertEqual(record.document_id, "document-1")
        self.assertEqual(record.url, self.source.url)
        self.assertEqual(record.content, self.source.content)
        self.assertEqual(record.content_type, "text/plain")
        self.assertEqual(record.content_byte_count, len(encoded))
        self.assertEqual(record.content_sha256, hashlib.sha256(encoded).hexdigest())
        self.assertEqual(record.fetched_at, self.fetched_at)
        self.assertEqual(record.stored_at, self.stored_at)

    def test_rejects_tampered_hash_and_byte_count(self) -> None:
        record = ResearchSourceContentRecord.from_source(
            self.source,
            "document-1",
            self.stored_at,
        )
        with self.assertRaisesRegex(ResearchError, "byte count"):
            replace(record, content_byte_count=record.content_byte_count + 1)
        with self.assertRaisesRegex(ResearchError, "fingerprint"):
            replace(record, content_sha256="0" * 64)

    def test_rejects_oversized_content_and_naive_times(self) -> None:
        with (
            patch(
                "research.ResearchSourceContentRecord." "MAX_SOURCE_CONTENT_UTF8_BYTES",
                4,
            ),
            self.assertRaisesRegex(ResearchError, "too large"),
        ):
            ResearchSourceContentRecord.from_source(
                self.source,
                "document-1",
                self.stored_at,
            )

        with self.assertRaisesRegex(ResearchError, "timezone-aware"):
            ResearchSourceContentRecord.from_source(
                self.source,
                "document-1",
                datetime(2026, 8, 21, 1, 1),
            )
        with self.assertRaisesRegex(ResearchError, "before it was fetched"):
            ResearchSourceContentRecord.from_source(
                self.source,
                "document-1",
                datetime(2026, 8, 21, 0, 59, tzinfo=UTC),
            )


if __name__ == "__main__":
    unittest.main()
