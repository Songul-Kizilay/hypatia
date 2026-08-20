"""Tests for the bounded accepted-content restoration status contract."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError
from research.ResearchSourceContentRestorationStatus import (
    ResearchSourceContentRestorationStatus,
)


class ResearchSourceContentRestorationStatusTests(unittest.TestCase):
    def test_ready_status_exposes_only_nonnegative_aggregate_counts(self) -> None:
        status = ResearchSourceContentRestorationStatus(True, 3, 12)

        self.assertTrue(status.available)
        self.assertEqual(status.state, "ready")
        self.assertEqual(status.restored_document_count, 3)
        self.assertEqual(status.restored_paragraph_count, 12)

    def test_unavailable_status_has_no_counts(self) -> None:
        status = ResearchSourceContentRestorationStatus.unavailable()

        self.assertFalse(status.available)
        self.assertEqual(status.state, "unavailable")
        self.assertEqual(status.restored_document_count, 0)
        self.assertEqual(status.restored_paragraph_count, 0)

    def test_invalid_availability_counts_and_unavailable_leaks_are_rejected(
        self,
    ) -> None:
        with self.assertRaisesRegex(ResearchError, "availability"):
            ResearchSourceContentRestorationStatus("yes", 0, 0)  # type: ignore[arg-type]
        with self.assertRaisesRegex(ResearchError, "document count"):
            ResearchSourceContentRestorationStatus(True, True, 0)
        with self.assertRaisesRegex(ResearchError, "paragraph count"):
            ResearchSourceContentRestorationStatus(True, 0, -1)
        with self.assertRaisesRegex(ResearchError, "cannot report counts"):
            ResearchSourceContentRestorationStatus(False, 1, 0)


if __name__ == "__main__":
    unittest.main()
