"""Contracts for immutable research candidate acceptance previews."""

from __future__ import annotations

import unittest

from core.Exceptions import ResearchError
from research.ResearchSourceCandidate import ResearchSourceCandidate
from research.ResearchSourceCandidateAcceptancePreview import (
    ResearchSourceCandidateAcceptancePreview,
)


class ResearchSourceCandidateAcceptancePreviewTests(unittest.TestCase):
    def test_preview_normalizes_identity_and_preserves_candidate(self) -> None:
        candidate = ResearchSourceCandidate(
            "https://example.com/paper", "Paper", "Summary"
        )

        preview = ResearchSourceCandidateAcceptancePreview(
            " run-1 ", " discovery-1 ", candidate, True, " Allowed. "
        )

        self.assertEqual(preview.run_id, "run-1")
        self.assertEqual(preview.discovery_id, "discovery-1")
        self.assertIs(preview.candidate, candidate)
        self.assertEqual(preview.reason, "Allowed.")

    def test_preview_rejects_invalid_contract_values(self) -> None:
        candidate = ResearchSourceCandidate(
            "https://example.com/paper", "Paper", "Summary"
        )
        invalid_values = (
            ("", "discovery-1", candidate, True, "Allowed."),
            ("run-1", "", candidate, True, "Allowed."),
            ("run-1", "discovery-1", object(), True, "Allowed."),
            ("run-1", "discovery-1", candidate, 1, "Allowed."),
            ("run-1", "discovery-1", candidate, True, ""),
        )

        for values in invalid_values:
            with self.subTest(values=values), self.assertRaises(ResearchError):
                ResearchSourceCandidateAcceptancePreview(*values)


if __name__ == "__main__":
    unittest.main()
