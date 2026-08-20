"""Validation tests for bounded traceable research evidence records."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime
from hashlib import sha256

from core.Exceptions import ResearchError
from knowledge.Chunk import Chunk
from research.ResearchEvidenceRecord import (
    MAX_EVIDENCE_EXCERPT_CHARACTERS,
    ResearchEvidenceRecord,
)


class ResearchEvidenceRecordTests(unittest.TestCase):
    def test_from_chunk_keeps_locator_bounded_excerpt_and_full_fingerprint(
        self,
    ) -> None:
        content = "e" * (MAX_EVIDENCE_EXCERPT_CHARACTERS + 25)
        chunk = Chunk(
            document_id="document-1",
            index=2,
            content=content,
            chunk_id="chunk-1",
        )
        now = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)

        record = ResearchEvidenceRecord.from_chunk(
            " evidence-1 ",
            chunk,
            "  This paragraph supports the comparison.  ",
            now,
        )

        self.assertEqual(record.evidence_id, "evidence-1")
        self.assertEqual(record.source_document_id, "document-1")
        self.assertEqual(record.chunk_id, "chunk-1")
        self.assertEqual(record.chunk_index, 2)
        self.assertEqual(len(record.excerpt), MAX_EVIDENCE_EXCERPT_CHARACTERS)
        self.assertTrue(record.excerpt_truncated)
        self.assertEqual(record.chunk_sha256, sha256(content.encode()).hexdigest())
        self.assertEqual(record.note, "This paragraph supports the comparison.")

    def test_rejects_invalid_fingerprint_note_and_time(self) -> None:
        now = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
        valid = {
            "evidence_id": "evidence-1",
            "source_document_id": "document-1",
            "chunk_id": "chunk-1",
            "chunk_index": 0,
            "excerpt": "Evidence.",
            "excerpt_truncated": False,
            "chunk_sha256": "a" * 64,
            "note": "Relevant.",
            "recorded_at": now,
        }
        for field, value, message in (
            ("chunk_sha256", "invalid", "fingerprint"),
            ("note", " ", "note cannot be empty"),
            ("recorded_at", datetime(2026, 8, 20), "timezone-aware"),
        ):
            with self.subTest(field=field):
                values = {**valid, field: value}
                with self.assertRaisesRegex(ResearchError, message):
                    ResearchEvidenceRecord(**values)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
