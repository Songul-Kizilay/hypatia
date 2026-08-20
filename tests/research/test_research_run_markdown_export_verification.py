"""Contract tests for read-only research Markdown integrity results."""

from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from core.Exceptions import ResearchError
from research.ResearchRunMarkdownExportVerification import (
    ResearchRunMarkdownExportVerification,
)


class ResearchRunMarkdownExportVerificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.verification = ResearchRunMarkdownExportVerification(
            run_id="run-1",
            snapshot_updated_at=datetime(2026, 8, 21, tzinfo=UTC),
            source_path=str(Path.cwd() / "research.md"),
            expected_content_sha256="A" * 64,
            observed_content_sha256="a" * 64,
            expected_byte_count=128,
            observed_byte_count=128,
            matches=True,
        )

    def test_normalizes_fingerprints_and_preserves_exact_match(self) -> None:
        self.assertEqual(self.verification.expected_content_sha256, "a" * 64)
        self.assertEqual(self.verification.observed_content_sha256, "a" * 64)
        self.assertTrue(self.verification.matches)

    def test_accepts_an_honest_mismatch(self) -> None:
        mismatch = replace(
            self.verification,
            observed_content_sha256="b" * 64,
            observed_byte_count=127,
            matches=False,
        )

        self.assertFalse(mismatch.matches)

    def test_rejects_invalid_or_inconsistent_contract_values(self) -> None:
        invalid_values = (
            {"run_id": " "},
            {"snapshot_updated_at": datetime(2026, 8, 21)},
            {"source_path": "relative.md"},
            {"source_path": str(Path.cwd() / "research.txt")},
            {"source_path": str(Path.cwd() / "invalid\x00.md")},
            {"expected_content_sha256": "invalid"},
            {"observed_content_sha256": "invalid"},
            {"expected_byte_count": 0},
            {"observed_byte_count": -1},
            {"matches": False},
        )
        for values in invalid_values:
            with self.subTest(values=values), self.assertRaises(ResearchError):
                replace(self.verification, **values)


if __name__ == "__main__":
    unittest.main()
