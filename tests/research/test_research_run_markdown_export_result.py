"""Contract tests for a completed research Markdown file export."""

from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from core.Exceptions import ResearchError
from research.ResearchRunMarkdownExportResult import (
    ResearchRunMarkdownExportResult,
)


class ResearchRunMarkdownExportResultTests(unittest.TestCase):
    def setUp(self) -> None:
        self.result = ResearchRunMarkdownExportResult(
            run_id="run-1",
            snapshot_updated_at=datetime(2026, 8, 21, tzinfo=UTC),
            destination_path=str(Path.cwd() / "research.md"),
            content_sha256="A" * 64,
            byte_count=128,
        )

    def test_normalizes_identity_and_fingerprint(self) -> None:
        self.assertEqual(self.result.run_id, "run-1")
        self.assertEqual(self.result.content_sha256, "a" * 64)
        self.assertEqual(self.result.byte_count, 128)

    def test_rejects_invalid_contract_values(self) -> None:
        invalid_values = (
            {"run_id": " "},
            {"snapshot_updated_at": datetime(2026, 8, 21)},
            {"destination_path": "relative.md"},
            {"destination_path": "C:/Exports/research.txt"},
            {"destination_path": str(Path.cwd() / "invalid\x00.md")},
            {"content_sha256": "invalid"},
            {"byte_count": 0},
        )
        for values in invalid_values:
            with self.subTest(values=values), self.assertRaises(ResearchError):
                replace(self.result, **values)


if __name__ == "__main__":
    unittest.main()
