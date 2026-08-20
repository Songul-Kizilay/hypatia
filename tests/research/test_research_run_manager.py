"""Transactional tests for the research-run manager."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from core.Exceptions import ResearchError
from research.ResearchRun import ResearchRun
from research.ResearchRunManager import ResearchRunManager
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSource import ResearchSource


class RecordingRunStore:
    def __init__(self, runs: list[ResearchRun] | None = None) -> None:
        self.runs = list(runs or [])
        self.saved: list[list[ResearchRun]] = []
        self.error: ResearchError | None = None

    def load(self) -> list[ResearchRun]:
        return list(self.runs)

    def save(self, runs: list[ResearchRun]) -> None:
        self.saved.append(list(runs))
        if self.error is not None:
            raise self.error
        self.runs = list(runs)


class SequenceClock:
    def __init__(self, start: datetime) -> None:
        self._next = start

    def __call__(self) -> datetime:
        current = self._next
        self._next += timedelta(minutes=1)
        return current


class ResearchRunManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.start = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
        self.store = RecordingRunStore()
        self.manager = ResearchRunManager(
            self.store,
            clock=SequenceClock(self.start),
            id_factory=lambda: "run-1",
        )

    def test_create_persists_before_publishing_the_run(self) -> None:
        run = self.manager.create("  What should Hypatia research?  ")

        self.assertEqual(run.run_id, "run-1")
        self.assertEqual(run.question, "What should Hypatia research?")
        self.assertEqual(run.status, ResearchRunStatus.COLLECTING)
        self.assertEqual(self.manager.list(), [run])
        self.assertEqual(self.store.runs, [run])

    def test_add_source_persists_provenance_without_page_content(self) -> None:
        run = self.manager.create("Question")
        source = ResearchSource(
            url="https://example.com/research",
            title="Example",
            content="Sensitive full page content.",
            content_type="text/html",
            fetched_at=self.start,
        )

        updated = self.manager.add_source(run.run_id, source, "document-1")

        self.assertEqual(len(updated.sources), 1)
        record = updated.sources[0]
        self.assertEqual(record.document_id, "document-1")
        self.assertEqual(record.url, source.url)
        self.assertNotIn(source.content, repr(record))
        self.assertTrue(self.manager.has_source(run.run_id, "document-1"))

    def test_record_failure_does_not_persist_the_rejected_url(self) -> None:
        run = self.manager.create("Question")
        reason = "Research source must use HTTPS."

        updated = self.manager.record_failure(run.run_id, "source_fetch", reason)

        self.assertEqual(updated.failures[0].reason, reason)
        self.assertNotIn("http://secret@example.com", repr(updated))

    def test_failed_save_does_not_publish_candidate_state(self) -> None:
        run = self.manager.create("Question")
        self.store.error = ResearchError("Store unavailable.")
        source = ResearchSource(
            url="https://example.com/research",
            title="Example",
            content="Evidence.",
            content_type="text/plain",
            fetched_at=self.start,
        )

        with self.assertRaisesRegex(ResearchError, "Store unavailable"):
            self.manager.add_source(run.run_id, source, "document-1")

        self.assertEqual(self.manager.get(run.run_id), run)
        self.assertFalse(self.manager.has_source(run.run_id, "document-1"))

    def test_load_replaces_state_only_after_valid_store_load(self) -> None:
        run = self.manager.create("Question")
        restarted = ResearchRunManager(self.store)

        restarted.load()

        self.assertEqual(restarted.list(), [run])


if __name__ == "__main__":
    unittest.main()
