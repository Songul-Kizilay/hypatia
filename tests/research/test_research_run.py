"""Validation tests for persistent research-run records."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from core.Exceptions import ResearchError
from research.ResearchRun import ResearchRun
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSourceRecord import ResearchSourceRecord


class ResearchRunTests(unittest.TestCase):
    def test_normalizes_identity_and_question(self) -> None:
        now = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)

        run = ResearchRun(
            run_id=" run-1 ",
            question="  What evidence supports the finding?  ",
            status=ResearchRunStatus.COLLECTING,
            sources=(),
            failures=(),
            created_at=now,
            updated_at=now,
        )

        self.assertEqual(run.run_id, "run-1")
        self.assertEqual(run.question, "What evidence supports the finding?")

    def test_rejects_invalid_time_order_and_duplicate_sources(self) -> None:
        now = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
        with self.assertRaisesRegex(ResearchError, "cannot precede"):
            ResearchRun(
                run_id="run-1",
                question="Question",
                status=ResearchRunStatus.COLLECTING,
                sources=(),
                failures=(),
                created_at=now,
                updated_at=datetime(2026, 8, 20, 11, 0, tzinfo=UTC),
            )

        source = ResearchSourceRecord(
            document_id="document-1",
            url="https://example.com/source",
            title="Example",
            content_type="text/plain",
            fetched_at=now,
            added_at=now,
        )
        duplicate = ResearchSourceRecord(
            document_id="document-1",
            url="https://example.org/duplicate",
            title="Duplicate",
            content_type="text/html",
            fetched_at=now,
            added_at=now,
        )
        with self.assertRaisesRegex(ResearchError, "duplicate source documents"):
            ResearchRun(
                run_id="run-1",
                question="Question",
                status=ResearchRunStatus.COLLECTING,
                sources=(source, duplicate),
                failures=(),
                created_at=now,
                updated_at=now,
            )


if __name__ == "__main__":
    unittest.main()
