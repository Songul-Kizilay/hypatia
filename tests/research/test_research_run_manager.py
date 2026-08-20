"""Transactional tests for the research-run manager."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from functools import partial

from core.Exceptions import ResearchError
from knowledge.Chunk import Chunk
from research.ResearchRun import ResearchRun
from research.ResearchRunManager import ResearchRunManager
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSource import ResearchSource
from research.ResearchSourceCandidate import ResearchSourceCandidate


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
        evidence_ids = iter(f"evidence-{number}" for number in range(1, 10))
        assessment_ids = iter(("assessment-1", "assessment-2", "assessment-3"))
        self.manager = ResearchRunManager(
            self.store,
            clock=SequenceClock(self.start),
            id_factory=lambda: "run-1",
            evidence_id_factory=evidence_ids.__next__,
            discovery_id_factory=lambda: "discovery-1",
            assessment_id_factory=assessment_ids.__next__,
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

    def test_add_discovery_persists_ordered_unaccepted_candidates(self) -> None:
        run = self.manager.create("  Find trustworthy evidence  ")
        candidate = ResearchSourceCandidate(
            url="https://example.com/evidence",
            title="Evidence",
            snippet="Potentially relevant.",
        )

        updated = self.manager.add_discovery(
            run.run_id,
            run.question,
            "test-provider",
            [candidate],
        )

        self.assertEqual(len(updated.discoveries), 1)
        discovery = updated.discoveries[0]
        self.assertEqual(discovery.discovery_id, "discovery-1")
        self.assertEqual(discovery.query, "Find trustworthy evidence")
        self.assertEqual(discovery.provider, "test-provider")
        self.assertEqual(discovery.candidates, (candidate,))
        self.assertEqual(updated.sources, ())
        self.assertEqual(updated.evidence, ())
        self.assertEqual(self.store.runs, [updated])

    def test_discovery_save_failure_does_not_publish_candidate_state(self) -> None:
        run = self.manager.create("Question")
        self.store.error = ResearchError("Store unavailable.")

        with self.assertRaisesRegex(ResearchError, "Store unavailable"):
            self.manager.add_discovery(
                run.run_id,
                run.question,
                "test-provider",
                [],
            )

        self.assertEqual(self.manager.get(run.run_id), run)
        self.assertEqual(self.manager.get(run.run_id).discoveries, ())

    def test_add_evidence_requires_an_attached_source_and_persists_before_publish(
        self,
    ) -> None:
        run = self.manager.create("Question")
        source = ResearchSource(
            url="https://example.com/research",
            title="Example",
            content="Evidence paragraph.",
            content_type="text/plain",
            fetched_at=self.start,
        )
        self.manager.add_source(run.run_id, source, "document-1")
        chunk = Chunk(
            document_id="document-1",
            index=3,
            content="Evidence paragraph.",
            chunk_id="chunk-1",
        )

        updated = self.manager.add_evidence(
            run.run_id,
            chunk,
            "  Supports the selected claim.  ",
        )

        self.assertEqual(len(updated.evidence), 1)
        self.assertEqual(updated.evidence[0].evidence_id, "evidence-1")
        self.assertEqual(updated.evidence[0].chunk_id, "chunk-1")
        self.assertEqual(updated.evidence[0].note, "Supports the selected claim.")
        self.assertEqual(self.store.runs, [updated])

    def test_add_evidence_rejects_unattached_source_and_failed_save(self) -> None:
        run = self.manager.create("Question")
        unattached = Chunk(
            document_id="other-document",
            index=0,
            content="Unattached.",
            chunk_id="chunk-other",
        )
        with self.assertRaisesRegex(ResearchError, "attached to this run"):
            self.manager.add_evidence(run.run_id, unattached, "Not allowed.")

        source = ResearchSource(
            url="https://example.com/research",
            title="Example",
            content="Evidence.",
            content_type="text/plain",
            fetched_at=self.start,
        )
        attached_run = self.manager.add_source(run.run_id, source, "document-1")
        attached = Chunk(
            document_id="document-1",
            index=0,
            content="Evidence.",
            chunk_id="chunk-1",
        )
        self.store.error = ResearchError("Store unavailable.")

        with self.assertRaisesRegex(ResearchError, "Store unavailable"):
            self.manager.add_evidence(run.run_id, attached, "Relevant.")

        self.assertEqual(self.manager.get(run.run_id), attached_run)
        self.assertEqual(self.manager.get(run.run_id).evidence, ())

    def test_completed_preview_requires_source_and_evidence_without_saving(
        self,
    ) -> None:
        run = self.manager.create("Question")
        saves_after_create = len(self.store.saved)

        without_source = self.manager.preview_status_transition(
            run.run_id,
            ResearchRunStatus.COMPLETED,
        )
        source = ResearchSource(
            url="https://example.com/research",
            title="Example",
            content="Evidence.",
            content_type="text/plain",
            fetched_at=self.start,
        )
        self.manager.add_source(run.run_id, source, "document-1")
        saves_after_source = len(self.store.saved)
        without_evidence = self.manager.preview_status_transition(
            run.run_id,
            ResearchRunStatus.COMPLETED,
        )
        self.manager.add_evidence(
            run.run_id,
            Chunk(
                document_id="document-1",
                index=0,
                content="Evidence.",
                chunk_id="chunk-1",
            ),
            "Supports completion.",
        )
        saves_after_evidence = len(self.store.saved)

        allowed = self.manager.preview_status_transition(
            run.run_id,
            ResearchRunStatus.COMPLETED,
        )

        self.assertFalse(without_source.allowed)
        self.assertIn("accepted source", without_source.reason)
        self.assertFalse(without_evidence.allowed)
        self.assertIn("evidence record", without_evidence.reason)
        self.assertTrue(allowed.allowed)
        self.assertEqual(allowed.current_status, ResearchRunStatus.COLLECTING)
        self.assertEqual(allowed.target_status, ResearchRunStatus.COMPLETED)
        self.assertEqual(len(self.store.saved), saves_after_evidence)
        self.assertEqual(saves_after_create + 1, saves_after_source)

    def test_terminal_transition_is_persisted_and_closes_further_mutation(self) -> None:
        run = self.manager.create("Question")
        source = ResearchSource(
            url="https://example.com/research",
            title="Example",
            content="Evidence.",
            content_type="text/plain",
            fetched_at=self.start,
        )
        self.manager.add_source(run.run_id, source, "document-1")
        chunk = Chunk(
            document_id="document-1",
            index=0,
            content="Evidence.",
            chunk_id="chunk-1",
        )
        self.manager.add_evidence(run.run_id, chunk, "Supports completion.")

        completed = self.manager.transition_status(
            run.run_id,
            ResearchRunStatus.COMPLETED,
        )

        self.assertEqual(completed.status, ResearchRunStatus.COMPLETED)
        self.assertTrue(completed.status.terminal)
        self.assertEqual(self.store.runs, [completed])
        blocked = self.manager.preview_status_transition(
            run.run_id,
            ResearchRunStatus.CANCELLED,
        )
        self.assertFalse(blocked.allowed)
        self.assertIn("closed", blocked.reason)
        for mutation in (
            lambda: self.manager.add_source(run.run_id, source, "document-2"),
            lambda: self.manager.add_evidence(
                run.run_id,
                chunk,
                "Another note.",
            ),
            lambda: self.manager.record_failure(run.run_id, "stage", "Reason."),
            lambda: self.manager.add_discovery(
                run.run_id,
                run.question,
                "test-provider",
                [],
            ),
            lambda: self.manager.record_source_assessment(
                run.run_id,
                "document-1",
                ["evidence-1"],
                "Assessment.",
            ),
        ):
            with self.assertRaisesRegex(ResearchError, "closed"):
                mutation()

    def test_cancelled_is_valid_when_empty_but_failed_requires_a_failure(self) -> None:
        cancelled_store = RecordingRunStore()
        cancelled_manager = ResearchRunManager(
            cancelled_store,
            id_factory=partial(str, "run-cancelled"),
        )
        cancelled_run = cancelled_manager.create("Question")

        cancelled_preview = cancelled_manager.preview_status_transition(
            cancelled_run.run_id,
            ResearchRunStatus.CANCELLED,
        )
        cancelled = cancelled_manager.transition_status(
            cancelled_run.run_id,
            ResearchRunStatus.CANCELLED,
        )

        failed_store = RecordingRunStore()
        failed_manager = ResearchRunManager(
            failed_store,
            id_factory=partial(str, "run-failed"),
        )
        failed_run = failed_manager.create("Question")
        blocked = failed_manager.preview_status_transition(
            failed_run.run_id,
            ResearchRunStatus.FAILED,
        )
        failed_manager.record_failure(failed_run.run_id, "source_load", "Timed out.")
        allowed = failed_manager.preview_status_transition(
            failed_run.run_id,
            ResearchRunStatus.FAILED,
        )
        failed = failed_manager.transition_status(
            failed_run.run_id,
            ResearchRunStatus.FAILED,
        )

        self.assertTrue(cancelled_preview.allowed)
        self.assertEqual(cancelled.status, ResearchRunStatus.CANCELLED)
        self.assertEqual(cancelled_store.runs, [cancelled])
        self.assertFalse(blocked.allowed)
        self.assertIn("failure record", blocked.reason)
        self.assertTrue(allowed.allowed)
        self.assertEqual(failed.status, ResearchRunStatus.FAILED)
        self.assertEqual(failed_store.runs, [failed])

    def test_failed_status_save_does_not_publish_terminal_state(self) -> None:
        run = self.manager.create("Question")
        self.store.error = ResearchError("Store unavailable.")

        with self.assertRaisesRegex(ResearchError, "Store unavailable"):
            self.manager.transition_status(run.run_id, ResearchRunStatus.CANCELLED)

        self.assertEqual(self.manager.get(run.run_id), run)

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

    def test_candidate_acceptance_preview_matches_persisted_discovery_only(
        self,
    ) -> None:
        run = self.manager.create("Question")
        candidate = ResearchSourceCandidate(
            "https://example.com/paper", "Paper", "Summary"
        )
        updated = self.manager.add_discovery(
            run.run_id, run.question, "provider", [candidate]
        )
        saves_before = len(self.store.saved)

        preview = self.manager.preview_candidate_acceptance(
            run.run_id,
            updated.discoveries[0].discovery_id,
            candidate.url,
        )

        self.assertTrue(preview.allowed)
        self.assertEqual(preview.candidate, candidate)
        self.assertEqual(len(self.store.saved), saves_before)
        self.assertEqual(self.manager.get(run.run_id), updated)

    def test_candidate_acceptance_preview_rejects_unknown_selection(self) -> None:
        run = self.manager.create("Question")
        candidate = ResearchSourceCandidate(
            "https://example.com/paper", "Paper", "Summary"
        )
        self.manager.add_discovery(run.run_id, run.question, "provider", [candidate])

        with self.assertRaisesRegex(ResearchError, "discovery was not found"):
            self.manager.preview_candidate_acceptance(
                run.run_id, "missing", candidate.url
            )
        with self.assertRaisesRegex(ResearchError, "not found in this discovery"):
            self.manager.preview_candidate_acceptance(
                run.run_id, "discovery-1", "https://example.com/unlisted"
            )

    def test_closed_run_returns_blocked_candidate_acceptance_preview(self) -> None:
        run = self.manager.create("Question")
        candidate = ResearchSourceCandidate(
            "https://example.com/paper", "Paper", "Summary"
        )
        self.manager.add_discovery(run.run_id, run.question, "provider", [candidate])
        self.manager.transition_status(run.run_id, ResearchRunStatus.CANCELLED)

        preview = self.manager.preview_candidate_acceptance(
            run.run_id, "discovery-1", candidate.url
        )

        self.assertFalse(preview.allowed)
        self.assertIn("closed", preview.reason)

    def test_source_assessment_preview_filters_evidence_without_saving(self) -> None:
        run = self.manager.create("Question")
        first_source = ResearchSource(
            "https://example.com/first",
            "First",
            "First evidence.",
            "text/plain",
            self.start,
        )
        second_source = ResearchSource(
            "https://example.com/second",
            "Second",
            "Second evidence.",
            "text/plain",
            self.start,
        )
        self.manager.add_source(run.run_id, first_source, "document-1")
        self.manager.add_source(run.run_id, second_source, "document-2")
        first_evidence = self.manager.add_evidence(
            run.run_id,
            Chunk("document-1", 0, "First evidence.", chunk_id="chunk-1"),
            "First note.",
        ).evidence[-1]
        saves_before = len(self.store.saved)

        preview = self.manager.preview_source_assessment(run.run_id, "document-1")

        self.assertEqual(preview.source.document_id, "document-1")
        self.assertEqual(preview.evidence, (first_evidence,))
        self.assertTrue(preview.has_recorded_evidence)
        self.assertEqual(len(self.store.saved), saves_before)

    def test_source_comparison_is_ordered_current_and_read_only(self) -> None:
        run = self.manager.create("Compare sources")
        for number in (1, 2):
            source = ResearchSource(
                f"https://example.com/{number}",
                f"Source {number}",
                f"Evidence {number}.",
                "text/plain",
                self.start,
            )
            self.manager.add_source(run.run_id, source, f"document-{number}")
            self.manager.add_evidence(
                run.run_id,
                Chunk(
                    f"document-{number}",
                    0,
                    f"Evidence {number}.",
                    chunk_id=f"chunk-{number}",
                ),
                f"Note {number}.",
            )
        current_run = self.manager.get(run.run_id)
        first_evidence = current_run.evidence[0]
        original = self.manager.record_source_assessment(
            run.run_id,
            "document-1",
            [first_evidence.evidence_id],
            "Original.",
        ).assessments[-1]
        correction = self.manager.record_source_assessment(
            run.run_id,
            "document-1",
            [first_evidence.evidence_id],
            "Correction.",
            original.assessment_id,
        ).assessments[-1]
        saves_before = len(self.store.saved)

        preview = self.manager.preview_source_comparison(
            run.run_id,
            [" document-2 ", "document-1"],
        )

        self.assertEqual(
            tuple(item.source.document_id for item in preview.sources),
            ("document-2", "document-1"),
        )
        self.assertEqual(preview.sources[0].current_assessments, ())
        self.assertEqual(preview.sources[1].current_assessments, (correction,))
        self.assertEqual(len(self.store.saved), saves_before)

    def test_source_comparison_remains_available_after_run_closes(self) -> None:
        run = self.manager.create("Question")
        for number in (1, 2):
            self.manager.add_source(
                run.run_id,
                ResearchSource(
                    f"https://example.com/{number}",
                    f"Source {number}",
                    "Evidence.",
                    "text/plain",
                    self.start,
                ),
                f"document-{number}",
            )
        self.manager.transition_status(run.run_id, ResearchRunStatus.CANCELLED)

        preview = self.manager.preview_source_comparison(
            run.run_id,
            ["document-1", "document-2"],
        )

        self.assertEqual(preview.run_status, ResearchRunStatus.CANCELLED)

    def test_source_comparison_rejects_invalid_or_unaccepted_selection(self) -> None:
        run = self.manager.create("Question")
        self.manager.add_source(
            run.run_id,
            ResearchSource(
                "https://example.com/1",
                "Source 1",
                "Evidence.",
                "text/plain",
                self.start,
            ),
            "document-1",
        )
        for document_ids, message in (
            (["document-1"], "2 to 5"),
            (["document-1", "document-1"], "duplicate"),
            (["document-1", "missing"], "accepted sources"),
        ):
            with self.subTest(document_ids=document_ids):
                with self.assertRaisesRegex(ResearchError, message):
                    self.manager.preview_source_comparison(run.run_id, document_ids)

    def test_source_comparison_bounds_material_and_reports_omissions(self) -> None:
        evidence_ids = iter(f"bounded-evidence-{number}" for number in range(30))
        assessment_ids = iter(f"bounded-assessment-{number}" for number in range(20))
        manager = ResearchRunManager(
            RecordingRunStore(),
            clock=SequenceClock(self.start),
            id_factory=lambda: "bounded-run",
            evidence_id_factory=evidence_ids.__next__,
            assessment_id_factory=assessment_ids.__next__,
        )
        run = manager.create("Question")
        for number in (1, 2):
            manager.add_source(
                run.run_id,
                ResearchSource(
                    f"https://example.com/bounded-{number}",
                    f"Source {number}",
                    "Evidence.",
                    "text/plain",
                    self.start,
                ),
                f"document-{number}",
            )
        for number in range(21):
            manager.add_evidence(
                run.run_id,
                Chunk(
                    "document-1",
                    number,
                    f"Evidence {number}.",
                    chunk_id=f"chunk-{number}",
                ),
                f"Note {number}.",
            )
        first_evidence_id = manager.get(run.run_id).evidence[0].evidence_id
        for number in range(11):
            manager.record_source_assessment(
                run.run_id,
                "document-1",
                [first_evidence_id],
                f"Assessment {number}.",
            )

        preview = manager.preview_source_comparison(
            run.run_id,
            ["document-1", "document-2"],
        )

        item = preview.sources[0]
        self.assertEqual(len(item.evidence), 20)
        self.assertEqual(item.total_evidence_count, 21)
        self.assertEqual(item.omitted_evidence_count, 1)
        self.assertEqual(len(item.current_assessments), 10)
        self.assertEqual(item.total_current_assessment_count, 11)
        self.assertEqual(item.omitted_current_assessment_count, 1)

    def test_source_assessment_preview_is_read_only_for_terminal_run(self) -> None:
        run = self.manager.create("Question")
        source = ResearchSource(
            "https://example.com/source",
            "Source",
            "Evidence.",
            "text/plain",
            self.start,
        )
        self.manager.add_source(run.run_id, source, "document-1")
        self.manager.transition_status(run.run_id, ResearchRunStatus.CANCELLED)

        preview = self.manager.preview_source_assessment(run.run_id, "document-1")

        self.assertEqual(preview.run_status, ResearchRunStatus.CANCELLED)
        self.assertFalse(preview.has_recorded_evidence)
        self.assertIn("no user-selected evidence", preview.reason)

    def test_source_assessment_rejects_source_from_another_run(self) -> None:
        run = self.manager.create("Question")

        with self.assertRaisesRegex(ResearchError, "accepted sources"):
            self.manager.preview_source_assessment(run.run_id, "document-1")

    def test_authored_assessment_preview_is_read_only_and_record_is_atomic(
        self,
    ) -> None:
        run = self.manager.create("Question")
        source = ResearchSource(
            "https://example.com/source",
            "Source",
            "Evidence.",
            "text/plain",
            self.start,
        )
        self.manager.add_source(run.run_id, source, "document-1")
        evidence = self.manager.add_evidence(
            run.run_id,
            Chunk("document-1", 0, "Evidence.", chunk_id="chunk-1"),
            "Supports the assessment.",
        ).evidence[-1]
        saves_before = len(self.store.saved)

        preview = self.manager.preview_source_assessment_write(
            run.run_id,
            "document-1",
            [evidence.evidence_id],
            "  The source supports the claim.  ",
        )

        self.assertTrue(preview.allowed)
        self.assertEqual(preview.evidence, (evidence,))
        self.assertEqual(preview.text, "The source supports the claim.")
        self.assertEqual(len(self.store.saved), saves_before)

        updated = self.manager.record_source_assessment(
            run.run_id,
            "document-1",
            [evidence.evidence_id],
            "The source supports the claim.",
        )

        self.assertEqual(len(updated.assessments), 1)
        assessment = updated.assessments[0]
        self.assertEqual(assessment.assessment_id, "assessment-1")
        self.assertEqual(assessment.source_document_id, "document-1")
        self.assertEqual(assessment.evidence_ids, (evidence.evidence_id,))
        self.assertEqual(self.store.runs, [updated])
        history = self.manager.preview_source_assessment(run.run_id, "document-1")
        self.assertEqual(history.assessments, (assessment,))

    def test_authored_assessment_correction_preserves_history_and_revalidates(
        self,
    ) -> None:
        run = self.manager.create("Question")
        self.manager.add_source(
            run.run_id,
            ResearchSource(
                "https://example.com/source",
                "Source",
                "Evidence.",
                "text/plain",
                self.start,
            ),
            "document-1",
        )
        evidence = self.manager.add_evidence(
            run.run_id,
            Chunk("document-1", 0, "Evidence.", chunk_id="chunk-1"),
            "Relevant.",
        ).evidence[-1]
        original = self.manager.record_source_assessment(
            run.run_id,
            "document-1",
            [evidence.evidence_id],
            "Original assessment.",
        ).assessments[-1]
        saves_before = len(self.store.saved)

        preview = self.manager.preview_source_assessment_write(
            run.run_id,
            "document-1",
            [evidence.evidence_id],
            "Corrected assessment.",
            original.assessment_id,
        )

        self.assertTrue(preview.allowed)
        self.assertEqual(preview.supersedes_assessment, original)
        self.assertEqual(len(self.store.saved), saves_before)

        updated = self.manager.record_source_assessment(
            run.run_id,
            "document-1",
            [evidence.evidence_id],
            "Corrected assessment.",
            original.assessment_id,
        )

        self.assertEqual(len(updated.assessments), 2)
        self.assertEqual(
            updated.assessments[-1].supersedes_assessment_id,
            original.assessment_id,
        )
        self.assertEqual(updated.assessments[0], original)
        history = self.manager.preview_source_assessment(run.run_id, "document-1")
        self.assertEqual(history.assessments, updated.assessments)

        with self.assertRaisesRegex(ResearchError, "already been superseded"):
            self.manager.record_source_assessment(
                run.run_id,
                "document-1",
                [evidence.evidence_id],
                "Competing correction.",
                original.assessment_id,
            )

    def test_authored_assessment_correction_rejects_missing_or_cross_source_target(
        self,
    ) -> None:
        run = self.manager.create("Question")
        for number in (1, 2):
            self.manager.add_source(
                run.run_id,
                ResearchSource(
                    f"https://example.com/{number}",
                    f"Source {number}",
                    f"Evidence {number}.",
                    "text/plain",
                    self.start,
                ),
                f"document-{number}",
            )
        evidence_1 = self.manager.add_evidence(
            run.run_id,
            Chunk("document-1", 0, "Evidence 1.", chunk_id="chunk-1"),
            "First evidence.",
        ).evidence[-1]
        evidence_2 = self.manager.add_evidence(
            run.run_id,
            Chunk("document-2", 0, "Evidence 2.", chunk_id="chunk-2"),
            "Second evidence.",
        ).evidence[-1]
        original = self.manager.record_source_assessment(
            run.run_id,
            "document-1",
            [evidence_1.evidence_id],
            "Original assessment.",
        ).assessments[-1]

        with self.assertRaisesRegex(ResearchError, "not found in this run"):
            self.manager.preview_source_assessment_write(
                run.run_id,
                "document-1",
                [evidence_1.evidence_id],
                "Correction.",
                "assessment-missing",
            )
        with self.assertRaisesRegex(ResearchError, "selected source"):
            self.manager.preview_source_assessment_write(
                run.run_id,
                "document-2",
                [evidence_2.evidence_id],
                "Cross-source correction.",
                original.assessment_id,
            )

    def test_authored_assessment_rejects_cross_source_or_missing_evidence(self) -> None:
        run = self.manager.create("Question")
        for number in (1, 2):
            self.manager.add_source(
                run.run_id,
                ResearchSource(
                    f"https://example.com/{number}",
                    f"Source {number}",
                    f"Evidence {number}.",
                    "text/plain",
                    self.start,
                ),
                f"document-{number}",
            )
        evidence = self.manager.add_evidence(
            run.run_id,
            Chunk("document-2", 0, "Evidence 2.", chunk_id="chunk-2"),
            "Second source evidence.",
        ).evidence[-1]

        with self.assertRaisesRegex(ResearchError, "selected source"):
            self.manager.preview_source_assessment_write(
                run.run_id,
                "document-1",
                [evidence.evidence_id],
                "Invalid cross-source assessment.",
            )
        with self.assertRaisesRegex(ResearchError, "not found in this run"):
            self.manager.preview_source_assessment_write(
                run.run_id,
                "document-1",
                ["missing-evidence"],
                "Missing evidence assessment.",
            )

    def test_closed_run_blocks_preview_and_record_without_saving(self) -> None:
        run = self.manager.create("Question")
        self.manager.add_source(
            run.run_id,
            ResearchSource(
                "https://example.com/source",
                "Source",
                "Evidence.",
                "text/plain",
                self.start,
            ),
            "document-1",
        )
        evidence = self.manager.add_evidence(
            run.run_id,
            Chunk("document-1", 0, "Evidence.", chunk_id="chunk-1"),
            "Relevant.",
        ).evidence[-1]
        self.manager.transition_status(run.run_id, ResearchRunStatus.COMPLETED)
        saves_before = len(self.store.saved)

        preview = self.manager.preview_source_assessment_write(
            run.run_id,
            "document-1",
            [evidence.evidence_id],
            "Too late.",
        )

        self.assertFalse(preview.allowed)
        self.assertIn("closed", preview.reason)
        self.assertEqual(len(self.store.saved), saves_before)
        with self.assertRaisesRegex(ResearchError, "closed"):
            self.manager.record_source_assessment(
                run.run_id,
                "document-1",
                [evidence.evidence_id],
                "Too late.",
            )
        self.assertEqual(len(self.store.saved), saves_before)

    def test_failed_assessment_save_does_not_publish_record(self) -> None:
        run = self.manager.create("Question")
        self.manager.add_source(
            run.run_id,
            ResearchSource(
                "https://example.com/source",
                "Source",
                "Evidence.",
                "text/plain",
                self.start,
            ),
            "document-1",
        )
        evidence = self.manager.add_evidence(
            run.run_id,
            Chunk("document-1", 0, "Evidence.", chunk_id="chunk-1"),
            "Relevant.",
        ).evidence[-1]
        before = self.manager.get(run.run_id)
        self.store.error = ResearchError("Store unavailable.")

        with self.assertRaisesRegex(ResearchError, "Store unavailable"):
            self.manager.record_source_assessment(
                run.run_id,
                "document-1",
                [evidence.evidence_id],
                "Assessment.",
            )

        self.assertEqual(self.manager.get(run.run_id), before)


if __name__ == "__main__":
    unittest.main()
