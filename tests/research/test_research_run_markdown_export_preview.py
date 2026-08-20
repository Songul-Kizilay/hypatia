"""Contracts for bounded immutable research Markdown export previews."""

from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import UTC, datetime

from core.Exceptions import ResearchError
from research.ResearchRunMarkdownExportPreview import (
    ResearchRunMarkdownExportPreview,
)
from research.ResearchRunStatus import ResearchRunStatus


class ResearchRunMarkdownExportPreviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.preview = ResearchRunMarkdownExportPreview(
            run_id=" run-1 ",
            run_status=ResearchRunStatus.COMPLETED,
            snapshot_updated_at=datetime(2026, 8, 21, tzinfo=UTC),
            suggested_filename=" hypatia-research-run-1.md ",
            markdown_preview="# Export\n",
            total_character_count=9,
            omitted_character_count=0,
            content_sha256="a" * 64,
        )

    def test_normalizes_identity_without_changing_preview_content(self) -> None:
        self.assertEqual(self.preview.run_id, "run-1")
        self.assertEqual(
            self.preview.suggested_filename,
            "hypatia-research-run-1.md",
        )
        self.assertEqual(self.preview.markdown_preview, "# Export\n")
        self.assertEqual(self.preview.content_sha256, "a" * 64)

    def test_rejects_non_terminal_unsafe_or_inconsistent_values(self) -> None:
        invalid_changes = (
            {"run_status": ResearchRunStatus.COLLECTING},
            {"snapshot_updated_at": datetime(2026, 8, 21)},
            {"suggested_filename": "../report.md"},
            {"suggested_filename": "report.txt"},
            {"omitted_character_count": 10},
            {"total_character_count": 10},
            {"content_sha256": "not-a-fingerprint"},
        )
        for changes in invalid_changes:
            with self.subTest(changes=changes):
                with self.assertRaises(ResearchError):
                    replace(self.preview, **changes)


if __name__ == "__main__":
    unittest.main()
