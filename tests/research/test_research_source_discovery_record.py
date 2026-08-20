"""Validation tests for persisted source-discovery audit records."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from core.Exceptions import ResearchError
from research.ResearchSourceCandidate import ResearchSourceCandidate
from research.ResearchSourceDiscoveryRecord import ResearchSourceDiscoveryRecord


class ResearchSourceDiscoveryRecordTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
        self.candidate = ResearchSourceCandidate(
            url="https://example.com/source",
            title="Example",
            snippet="Summary",
        )

    def test_preserves_ordered_candidates_and_audit_identity(self) -> None:
        record = ResearchSourceDiscoveryRecord(
            discovery_id=" discovery-1 ",
            query=" research question ",
            provider=" test-provider ",
            candidates=(self.candidate,),
            discovered_at=self.now,
        )

        self.assertEqual(record.discovery_id, "discovery-1")
        self.assertEqual(record.query, "research question")
        self.assertEqual(record.provider, "test-provider")
        self.assertEqual(record.candidates, (self.candidate,))

    def test_rejects_duplicates_excess_results_and_naive_time(self) -> None:
        with self.assertRaisesRegex(ResearchError, "duplicate URLs"):
            ResearchSourceDiscoveryRecord(
                "discovery-1",
                "Question",
                "Provider",
                (self.candidate, self.candidate),
                self.now,
            )
        with self.assertRaisesRegex(ResearchError, "more than 10"):
            ResearchSourceDiscoveryRecord(
                "discovery-1",
                "Question",
                "Provider",
                tuple(
                    ResearchSourceCandidate(
                        f"https://example.com/{index}",
                        f"Candidate {index}",
                        "",
                    )
                    for index in range(11)
                ),
                self.now,
            )
        with self.assertRaisesRegex(ResearchError, "timezone-aware"):
            ResearchSourceDiscoveryRecord(
                "discovery-1",
                "Question",
                "Provider",
                (),
                datetime(2026, 8, 20, 12, 0),
            )


if __name__ == "__main__":
    unittest.main()
