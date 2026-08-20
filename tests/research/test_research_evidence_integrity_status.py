"""Validation tests for bounded evidence integrity aggregate status."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError
from research.ResearchEvidenceIntegrityStatus import ResearchEvidenceIntegrityStatus


class ResearchEvidenceIntegrityStatusTests(unittest.TestCase):
    def test_ready_status_requires_complete_nonnegative_classification(self) -> None:
        status = ResearchEvidenceIntegrityStatus(True, 6, 3, 2, 1)

        self.assertTrue(status.available)
        self.assertEqual(status.state, "ready")
        self.assertEqual(status.recorded_evidence_count, 6)
        self.assertEqual(status.matched_evidence_count, 3)
        self.assertEqual(status.missing_evidence_count, 2)
        self.assertEqual(status.changed_evidence_count, 1)

    def test_unavailable_status_has_no_counts(self) -> None:
        status = ResearchEvidenceIntegrityStatus.unavailable()

        self.assertFalse(status.available)
        self.assertEqual(status.state, "unavailable")
        self.assertEqual(
            (
                status.recorded_evidence_count,
                status.matched_evidence_count,
                status.missing_evidence_count,
                status.changed_evidence_count,
            ),
            (0, 0, 0, 0),
        )

    def test_invalid_counts_and_incomplete_classification_are_rejected(self) -> None:
        with self.assertRaisesRegex(ResearchError, "recorded count"):
            ResearchEvidenceIntegrityStatus(True, True, 0, 0, 0)
        with self.assertRaisesRegex(ResearchError, "do not match"):
            ResearchEvidenceIntegrityStatus(True, 2, 1, 0, 0)
        with self.assertRaisesRegex(ResearchError, "cannot report counts"):
            ResearchEvidenceIntegrityStatus(False, 1, 0, 1, 0)


if __name__ == "__main__":
    unittest.main()
