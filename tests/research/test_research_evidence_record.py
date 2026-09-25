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


class EvidenceNoteSensitiveInputRefusalTests(unittest.TestCase):
    """`ResearchEvidenceRecord.note` refuses the same explicit secret-bearing
    forms `ResearchSessionContextRecord`/`ResearchAssetObservationRecord`
    already refuse, using the same fixed category-only message discipline:
    the raised error names only the refused category, never the candidate
    value. `excerpt` is raw fetched source content, not operator input, and
    stays out of scope.
    """

    SENTINEL = "distinct-secret-sentinel"

    def _valid(self) -> dict[str, object]:
        return {
            "evidence_id": "evidence-1",
            "source_document_id": "document-1",
            "chunk_id": "chunk-1",
            "chunk_index": 0,
            "excerpt": "Evidence.",
            "excerpt_truncated": False,
            "chunk_sha256": "a" * 64,
            "note": "Relevant.",
            "recorded_at": datetime(2026, 8, 20, 12, 0, tzinfo=UTC),
        }

    def _cases(self) -> dict[str, str]:
        sentinel = self.SENTINEL
        return {
            "credential_bearing_url": f"https://user:{sentinel}@example.test",
            "authentication_header": f"Authorization: Bearer {sentinel}",
            "private_key_material": "-----BEGIN PRIVATE KEY-----",
            "secret_assignment": f"password={sentinel}",
            "token_format": "sk-abcdefghijklmnopqrstuvwxyz123456",
        }

    def test_note_refuses_every_explicit_category(self) -> None:
        for category, value in self._cases().items():
            with self.subTest(category=category):
                values = {**self._valid(), "note": value}
                with self.assertRaises(ResearchError) as raised:
                    ResearchEvidenceRecord(**values)  # type: ignore[arg-type]
                self.assertIn("refused as", str(raised.exception))
                self.assertNotIn(self.SENTINEL, str(raised.exception))

    def test_benign_near_miss_note_still_constructs(self) -> None:
        benign = "No password was used and no token was recorded."
        values = {**self._valid(), "note": benign}
        record = ResearchEvidenceRecord(**values)  # type: ignore[arg-type]
        self.assertEqual(record.note, benign)

    def test_excerpt_is_out_of_scope_and_unaffected(self) -> None:
        """`excerpt` is raw fetched source content, not operator input, and
        must remain unclassified even when it contains secret-shaped text.
        """
        values = {
            **self._valid(),
            "excerpt": f"Authorization: Bearer {self.SENTINEL}",
        }
        record = ResearchEvidenceRecord(**values)  # type: ignore[arg-type]
        self.assertEqual(record.excerpt, f"Authorization: Bearer {self.SENTINEL}")

    def test_non_note_fields_are_unaffected_by_the_new_check(self) -> None:
        """Differential regression: non-note accept/refuse outcomes on
        non-default fixtures are byte-for-byte unchanged by adding note
        classification.
        """
        values = {
            **self._valid(),
            "evidence_id": "evidence-9",
            "source_document_id": "document-9",
            "chunk_id": "chunk-9",
            "chunk_index": 3,
            "excerpt": "A different excerpt entirely.",
            "chunk_sha256": "b" * 64,
        }
        record = ResearchEvidenceRecord(**values)  # type: ignore[arg-type]
        self.assertEqual(record.evidence_id, "evidence-9")
        self.assertEqual(record.source_document_id, "document-9")
        self.assertEqual(record.chunk_id, "chunk-9")
        self.assertEqual(record.chunk_index, 3)
        self.assertEqual(record.excerpt, "A different excerpt entirely.")
        self.assertFalse(record.excerpt_truncated)
        self.assertEqual(record.chunk_sha256, "b" * 64)
        with self.assertRaises(ResearchError):
            ResearchEvidenceRecord(
                **{**self._valid(), "chunk_sha256": "invalid"}  # type: ignore[arg-type]
            )
        with self.assertRaises(ResearchError):
            ResearchEvidenceRecord(
                **{**self._valid(), "chunk_index": -1}  # type: ignore[arg-type]
            )
        with self.assertRaises(ResearchError):
            ResearchEvidenceRecord(
                **{**self._valid(), "excerpt": ""}  # type: ignore[arg-type]
            )


if __name__ == "__main__":
    unittest.main()
