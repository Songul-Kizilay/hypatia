"""Transactional tests for the research-run manager."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from functools import partial
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from core.Exceptions import ResearchError
from knowledge.Chunk import Chunk
from research.ResearchClaimConfidence import ResearchClaimConfidence
from research.ResearchEpistemicState import ResearchEpistemicState
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchInformationTrust import ResearchInformationTrust
from research.ResearchRun import ResearchRun
from research.ResearchRunManager import ResearchRunManager
from research.ResearchRunMarkdownExportPreview import (
    MAX_MARKDOWN_EXPORT_PREVIEW_CHARACTERS,
)
from research.ResearchRunMarkdownExportVerification import (
    MAX_MARKDOWN_EXPORT_VERIFICATION_BYTES,
)
from research.ResearchRunMarkdownRenderer import render_research_run_markdown
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSource import ResearchSource
from research.ResearchSourceAssessmentRecord import ResearchSourceAssessmentRecord
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
        claim_ids = iter(("claim-1", "claim-2", "claim-3"))
        self.manager = ResearchRunManager(
            self.store,
            clock=SequenceClock(self.start),
            id_factory=lambda: "run-1",
            evidence_id_factory=evidence_ids.__next__,
            discovery_id_factory=lambda: "discovery-1",
            assessment_id_factory=assessment_ids.__next__,
            comparison_note_id_factory=lambda: "comparison-note-1",
            claim_id_factory=claim_ids.__next__,
            claim_contradiction_id_factory=lambda: "contradiction-1",
        )

    def _prepare_comparison_material(
        self,
    ) -> tuple[
        ResearchRun,
        tuple[ResearchEvidenceRecord, ...],
        tuple[ResearchSourceAssessmentRecord, ...],
    ]:
        run = self.manager.create("Compare sources")
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
        evidence = self.manager.get(run.run_id).evidence
        for number, record in enumerate(evidence, start=1):
            self.manager.record_source_assessment(
                run.run_id,
                f"document-{number}",
                [record.evidence_id],
                f"Assessment {number}.",
            )
        assessments = self.manager.get(run.run_id).assessments
        return run, evidence, assessments

    def test_create_persists_before_publishing_the_run(self) -> None:
        run = self.manager.create("  What should Hypatia research?  ")

        self.assertEqual(run.run_id, "run-1")
        self.assertEqual(run.question, "What should Hypatia research?")
        self.assertEqual(run.status, ResearchRunStatus.COLLECTING)
        self.assertEqual(self.manager.list(), [run])
        self.assertEqual(self.store.runs, [run])

    def test_markdown_export_preview_requires_terminal_run_and_is_read_only(
        self,
    ) -> None:
        run = self.manager.create("Export this run")
        with self.assertRaisesRegex(ResearchError, "collecting"):
            self.manager.preview_markdown_export(run.run_id)
        terminal = self.manager.transition_status(
            run.run_id,
            ResearchRunStatus.CANCELLED,
        )
        saved_snapshot_count = len(self.store.saved)

        preview = self.manager.preview_markdown_export(run.run_id)

        expected_markdown = render_research_run_markdown(terminal)
        self.assertEqual(preview.run_id, terminal.run_id)
        self.assertEqual(preview.run_status, ResearchRunStatus.CANCELLED)
        self.assertEqual(preview.snapshot_updated_at, terminal.updated_at)
        self.assertEqual(preview.suggested_filename, "hypatia-research-run-1.md")
        self.assertEqual(preview.markdown_preview, expected_markdown)
        self.assertEqual(preview.total_character_count, len(expected_markdown))
        self.assertEqual(preview.omitted_character_count, 0)
        self.assertEqual(
            preview.content_sha256,
            sha256(expected_markdown.encode("utf-8")).hexdigest(),
        )
        self.assertEqual(self.manager.get(run.run_id), terminal)
        self.assertEqual(len(self.store.saved), saved_snapshot_count)

    def test_markdown_export_preview_bounds_large_terminal_run_honestly(self) -> None:
        run = self.manager.create("Large failed run")
        for number in range(60):
            self.manager.record_failure(
                run.run_id,
                f"stage-{number}",
                f"Failure {number}: " + "x" * 450,
            )
        terminal = self.manager.transition_status(
            run.run_id,
            ResearchRunStatus.FAILED,
        )

        preview = self.manager.preview_markdown_export(run.run_id)

        self.assertGreater(preview.omitted_character_count, 0)
        self.assertGreater(
            preview.total_character_count,
            MAX_MARKDOWN_EXPORT_PREVIEW_CHARACTERS,
        )
        self.assertIn("Preview truncated:", preview.markdown_preview)
        self.assertLess(
            len(preview.markdown_preview),
            MAX_MARKDOWN_EXPORT_PREVIEW_CHARACTERS + 100,
        )
        full_markdown = render_research_run_markdown(terminal)
        self.assertEqual(
            preview.content_sha256,
            sha256(full_markdown.encode("utf-8")).hexdigest(),
        )

    def test_markdown_export_filename_cannot_escape_to_a_path(self) -> None:
        manager = ResearchRunManager(id_factory=lambda: "../ unsafe / run")
        run = manager.create("Safe export filename")
        manager.transition_status(run.run_id, ResearchRunStatus.CANCELLED)

        preview = manager.preview_markdown_export(run.run_id)

        self.assertEqual(
            preview.suggested_filename,
            "hypatia-research-unsafe-run.md",
        )
        self.assertNotIn("/", preview.suggested_filename)
        self.assertNotIn("\\", preview.suggested_filename)

    def test_markdown_export_save_revalidates_and_atomically_creates_new_file(
        self,
    ) -> None:
        run = self.manager.create("Save this run")
        terminal = self.manager.transition_status(
            run.run_id,
            ResearchRunStatus.CANCELLED,
        )
        preview = self.manager.preview_markdown_export(run.run_id)
        persisted_save_count = len(self.store.saved)

        with TemporaryDirectory() as directory:
            destination = Path(directory) / preview.suggested_filename
            result = self.manager.save_markdown_export(
                run.run_id,
                destination,
                expected_snapshot_updated_at=preview.snapshot_updated_at,
                expected_content_sha256=preview.content_sha256,
            )

            expected_markdown = render_research_run_markdown(terminal)
            self.assertEqual(destination.read_text(encoding="utf-8"), expected_markdown)
            self.assertEqual(result.run_id, run.run_id)
            self.assertEqual(result.destination_path, str(destination))
            self.assertEqual(result.content_sha256, preview.content_sha256)
            self.assertEqual(result.byte_count, len(expected_markdown.encode("utf-8")))
            self.assertEqual(
                tuple(destination.parent.glob(f".{destination.name}.*.tmp")),
                (),
            )

        self.assertEqual(self.manager.get(run.run_id), terminal)
        self.assertEqual(len(self.store.saved), persisted_save_count)

    def test_markdown_export_save_never_replaces_an_existing_file(self) -> None:
        run = self.manager.create("Protect existing file")
        self.manager.transition_status(run.run_id, ResearchRunStatus.CANCELLED)
        preview = self.manager.preview_markdown_export(run.run_id)

        with TemporaryDirectory() as directory:
            destination = Path(directory) / "existing.md"
            destination.write_text("keep this", encoding="utf-8")

            with self.assertRaisesRegex(ResearchError, "already exists"):
                self.manager.save_markdown_export(
                    run.run_id,
                    destination,
                    expected_snapshot_updated_at=preview.snapshot_updated_at,
                    expected_content_sha256=preview.content_sha256,
                )

            self.assertEqual(destination.read_text(encoding="utf-8"), "keep this")
            self.assertEqual(
                tuple(destination.parent.glob(f".{destination.name}.*.tmp")),
                (),
            )

    def test_markdown_export_save_rejects_stale_preview_before_file_access(
        self,
    ) -> None:
        run = self.manager.create("Reject stale export")
        self.manager.transition_status(run.run_id, ResearchRunStatus.CANCELLED)
        preview = self.manager.preview_markdown_export(run.run_id)

        with TemporaryDirectory() as directory:
            for updated_at, fingerprint in (
                (
                    preview.snapshot_updated_at - timedelta(seconds=1),
                    preview.content_sha256,
                ),
                (preview.snapshot_updated_at, "0" * 64),
            ):
                destination = Path(directory) / f"{fingerprint[:8]}.md"
                with self.subTest(updated_at=updated_at, fingerprint=fingerprint):
                    with self.assertRaisesRegex(ResearchError, "stale"):
                        self.manager.save_markdown_export(
                            run.run_id,
                            destination,
                            expected_snapshot_updated_at=updated_at,
                            expected_content_sha256=fingerprint,
                        )
                    self.assertFalse(destination.exists())

    def test_markdown_export_save_rejects_unsafe_destination_and_collecting_run(
        self,
    ) -> None:
        run = self.manager.create("Validate destination")
        collecting_preview_time = run.updated_at

        with self.assertRaisesRegex(ResearchError, "absolute"):
            self.manager.save_markdown_export(
                run.run_id,
                "relative.md",
                expected_snapshot_updated_at=collecting_preview_time,
                expected_content_sha256="0" * 64,
            )

        for invalid_destination, expected_message in (
            (str(Path.cwd() / "export.txt"), "end with .md"),
            (str(Path.cwd() / "missing-directory" / "export.md"), "not found"),
            (str(Path.cwd() / "invalid\x00.md"), "invalid"),
        ):
            with self.subTest(destination=invalid_destination):
                with self.assertRaisesRegex(ResearchError, expected_message):
                    self.manager.save_markdown_export(
                        run.run_id,
                        invalid_destination,
                        expected_snapshot_updated_at=collecting_preview_time,
                        expected_content_sha256="0" * 64,
                    )

        with TemporaryDirectory() as directory:
            destination = Path(directory) / "collecting.md"
            with self.assertRaisesRegex(ResearchError, "collecting"):
                self.manager.save_markdown_export(
                    run.run_id,
                    destination,
                    expected_snapshot_updated_at=collecting_preview_time,
                    expected_content_sha256="0" * 64,
                )
            self.assertFalse(destination.exists())

    def test_markdown_export_verification_matches_exact_saved_document(self) -> None:
        run = self.manager.create("Verify this run")
        terminal = self.manager.transition_status(
            run.run_id,
            ResearchRunStatus.CANCELLED,
        )
        preview = self.manager.preview_markdown_export(run.run_id)
        persisted_save_count = len(self.store.saved)

        with TemporaryDirectory() as directory:
            source = Path(directory) / preview.suggested_filename
            self.manager.save_markdown_export(
                run.run_id,
                source,
                expected_snapshot_updated_at=preview.snapshot_updated_at,
                expected_content_sha256=preview.content_sha256,
            )

            verification = self.manager.verify_markdown_export(run.run_id, source)

            expected_bytes = render_research_run_markdown(terminal).encode("utf-8")
            self.assertTrue(verification.matches)
            self.assertEqual(verification.run_id, run.run_id)
            self.assertEqual(verification.snapshot_updated_at, terminal.updated_at)
            self.assertEqual(verification.source_path, str(source))
            self.assertEqual(
                verification.expected_content_sha256,
                sha256(expected_bytes).hexdigest(),
            )
            self.assertEqual(
                verification.observed_content_sha256,
                verification.expected_content_sha256,
            )
            self.assertEqual(verification.expected_byte_count, len(expected_bytes))
            self.assertEqual(verification.observed_byte_count, len(expected_bytes))

        self.assertEqual(self.manager.get(run.run_id), terminal)
        self.assertEqual(len(self.store.saved), persisted_save_count)

    def test_markdown_export_verification_reports_tampered_or_empty_file(
        self,
    ) -> None:
        run = self.manager.create("Detect changes")
        terminal = self.manager.transition_status(
            run.run_id,
            ResearchRunStatus.CANCELLED,
        )

        with TemporaryDirectory() as directory:
            for name, content in (
                ("tampered.md", b"# changed\n"),
                ("empty.md", b""),
            ):
                source = Path(directory) / name
                source.write_bytes(content)

                with self.subTest(name=name):
                    verification = self.manager.verify_markdown_export(
                        run.run_id,
                        source,
                    )
                    self.assertFalse(verification.matches)
                    self.assertEqual(verification.observed_byte_count, len(content))
                    self.assertEqual(
                        verification.observed_content_sha256,
                        sha256(content).hexdigest(),
                    )

        self.assertEqual(self.manager.get(run.run_id), terminal)

    def test_markdown_export_verification_rejects_collecting_and_unsafe_sources(
        self,
    ) -> None:
        run = self.manager.create("Validate verification source")
        missing_source = Path.cwd() / "missing-export.md"

        with self.assertRaisesRegex(ResearchError, "collecting"):
            self.manager.verify_markdown_export(run.run_id, missing_source)

        self.manager.transition_status(run.run_id, ResearchRunStatus.CANCELLED)
        for source, expected_message in (
            ("relative.md", "absolute"),
            (str(Path.cwd() / "export.txt"), "end with .md"),
            (str(Path.cwd() / "invalid\x00.md"), "invalid"),
            (str(missing_source), "could not be read"),
        ):
            with self.subTest(source=source):
                with self.assertRaisesRegex(ResearchError, expected_message):
                    self.manager.verify_markdown_export(run.run_id, source)

    def test_markdown_export_verification_rejects_non_regular_or_oversized_file(
        self,
    ) -> None:
        run = self.manager.create("Bound verification input")
        self.manager.transition_status(run.run_id, ResearchRunStatus.CANCELLED)

        with TemporaryDirectory() as directory:
            directory_source = Path(directory) / "directory.md"
            directory_source.mkdir()
            with self.assertRaises(ResearchError):
                self.manager.verify_markdown_export(run.run_id, directory_source)

            oversized_source = Path(directory) / "oversized.md"
            with oversized_source.open("wb") as stream:
                stream.truncate(MAX_MARKDOWN_EXPORT_VERIFICATION_BYTES + 1)
            with self.assertRaisesRegex(ResearchError, "too large"):
                self.manager.verify_markdown_export(run.run_id, oversized_source)

    def test_markdown_export_verification_rejects_path_replacement_during_read(
        self,
    ) -> None:
        run = self.manager.create("Detect path replacement")
        terminal = self.manager.transition_status(
            run.run_id,
            ResearchRunStatus.CANCELLED,
        )

        with TemporaryDirectory() as directory:
            source = Path(directory) / "stable.md"
            source.write_text(
                render_research_run_markdown(terminal),
                encoding="utf-8",
                newline="\n",
            )
            current = source.stat()
            replaced_path_state = SimpleNamespace(
                st_dev=current.st_dev,
                st_ino=current.st_ino + 1,
            )

            with (
                patch.object(Path, "stat", return_value=replaced_path_state),
                self.assertRaisesRegex(ResearchError, "changed while it was read"),
            ):
                self.manager.verify_markdown_export(run.run_id, source)

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

    def test_record_failure_preserves_bounded_provider_provenance(self) -> None:
        run = self.manager.create("Question")

        updated = self.manager.record_failure(
            run.run_id,
            "source_discovery",
            "Research source discovery failed.",
            provider=" nvd ",
        )

        self.assertEqual(updated.failures[0].provider, "nvd")

    def test_invalid_failure_provider_changes_nothing(self) -> None:
        run = self.manager.create("Question")

        with self.assertRaises(ResearchError):
            self.manager.record_failure(
                run.run_id,
                "source_discovery",
                "Research source discovery failed.",
                provider="nvd\nforged",
            )

        self.assertEqual(self.manager.get(run.run_id).failures, ())

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

    def test_comparison_note_preview_is_read_only_and_record_is_atomic(self) -> None:
        run, evidence, assessments = self._prepare_comparison_material()
        evidence_ids = [record.evidence_id for record in evidence]
        assessment_ids = [record.assessment_id for record in assessments]
        saves_before = len(self.store.saved)

        preview = self.manager.preview_source_comparison_note_write(
            run.run_id,
            ["document-2", "document-1"],
            list(reversed(evidence_ids)),
            list(reversed(assessment_ids)),
            "  My comparison note.  ",
        )

        self.assertTrue(preview.allowed)
        self.assertEqual(
            tuple(item.source.document_id for item in preview.comparison.sources),
            ("document-2", "document-1"),
        )
        self.assertEqual(
            tuple(record.evidence_id for record in preview.evidence),
            tuple(reversed(evidence_ids)),
        )
        self.assertEqual(preview.text, "My comparison note.")
        self.assertEqual(len(self.store.saved), saves_before)

        updated = self.manager.record_source_comparison_note(
            run.run_id,
            ["document-2", "document-1"],
            list(reversed(evidence_ids)),
            list(reversed(assessment_ids)),
            "My comparison note.",
        )

        note = updated.comparison_notes[-1]
        self.assertEqual(note.note_id, "comparison-note-1")
        self.assertEqual(note.source_document_ids, ("document-2", "document-1"))
        self.assertEqual(note.evidence_ids, tuple(reversed(evidence_ids)))
        self.assertEqual(note.assessment_ids, tuple(reversed(assessment_ids)))
        self.assertEqual(self.store.runs, [updated])
        read_back = self.manager.preview_source_comparison(
            run.run_id,
            ["document-2", "document-1"],
        )
        self.assertEqual(read_back.comparison_notes, (note,))
        self.assertEqual(read_back.total_comparison_note_count, 1)
        reversed_order = self.manager.preview_source_comparison(
            run.run_id,
            ["document-1", "document-2"],
        )
        self.assertEqual(reversed_order.comparison_notes, ())

    def test_comparison_note_requires_complete_current_references(self) -> None:
        run, evidence, assessments = self._prepare_comparison_material()

        with self.assertRaisesRegex(ResearchError, "cover every selected source"):
            self.manager.preview_source_comparison_note_write(
                run.run_id,
                ["document-1", "document-2"],
                [evidence[0].evidence_id],
                [record.assessment_id for record in assessments],
                "Incomplete evidence.",
            )
        alternate = self.manager.add_evidence(
            run.run_id,
            Chunk(
                "document-1",
                1,
                "Alternate evidence.",
                chunk_id="chunk-1-alternate",
            ),
            "Alternate note.",
        ).evidence[-1]
        with self.assertRaisesRegex(ResearchError, "cite each assessment's evidence"):
            self.manager.preview_source_comparison_note_write(
                run.run_id,
                ["document-1", "document-2"],
                [alternate.evidence_id, evidence[1].evidence_id],
                [record.assessment_id for record in assessments],
                "Missing assessment evidence.",
            )

        corrected = self.manager.record_source_assessment(
            run.run_id,
            "document-1",
            [evidence[0].evidence_id],
            "Corrected assessment.",
            assessments[0].assessment_id,
        ).assessments[-1]
        with self.assertRaisesRegex(ResearchError, "must be current"):
            self.manager.preview_source_comparison_note_write(
                run.run_id,
                ["document-1", "document-2"],
                [record.evidence_id for record in evidence],
                [assessments[0].assessment_id, assessments[1].assessment_id],
                "Stale assessment.",
            )
        preview = self.manager.preview_source_comparison_note_write(
            run.run_id,
            ["document-1", "document-2"],
            [record.evidence_id for record in evidence],
            [corrected.assessment_id, assessments[1].assessment_id],
            "Current assessments.",
        )
        self.assertTrue(preview.allowed)

    def test_comparison_note_closed_run_and_failed_save_do_not_mutate(self) -> None:
        run, evidence, assessments = self._prepare_comparison_material()
        values = (
            run.run_id,
            ["document-1", "document-2"],
            [record.evidence_id for record in evidence],
            [record.assessment_id for record in assessments],
            "Comparison note.",
        )
        self.store.error = ResearchError("save failed")

        with self.assertRaisesRegex(ResearchError, "save failed"):
            self.manager.record_source_comparison_note(*values)

        self.assertEqual(self.manager.get(run.run_id).comparison_notes, ())
        self.store.error = None
        self.manager.transition_status(run.run_id, ResearchRunStatus.CANCELLED)
        saves_before = len(self.store.saved)

        preview = self.manager.preview_source_comparison_note_write(*values)

        self.assertFalse(preview.allowed)
        with self.assertRaisesRegex(ResearchError, "closed"):
            self.manager.record_source_comparison_note(*values)
        self.assertEqual(len(self.store.saved), saves_before)

    def test_comparison_note_remains_valid_after_later_assessment_correction(
        self,
    ) -> None:
        run, evidence, assessments = self._prepare_comparison_material()
        updated = self.manager.record_source_comparison_note(
            run.run_id,
            ["document-1", "document-2"],
            [record.evidence_id for record in evidence],
            [record.assessment_id for record in assessments],
            "Historical comparison.",
        )
        note = updated.comparison_notes[-1]

        corrected = self.manager.record_source_assessment(
            run.run_id,
            "document-1",
            [evidence[0].evidence_id],
            "Later correction.",
            assessments[0].assessment_id,
        )

        self.assertEqual(corrected.comparison_notes, (note,))

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
            information_trust="high",
        )

        self.assertTrue(preview.allowed)
        self.assertEqual(preview.evidence, (evidence,))
        self.assertEqual(preview.text, "The source supports the claim.")
        self.assertEqual(preview.information_trust, ResearchInformationTrust.HIGH)
        self.assertEqual(preview.source.instruction_authority, "none")
        self.assertEqual(len(self.store.saved), saves_before)

        updated = self.manager.record_source_assessment(
            run.run_id,
            "document-1",
            [evidence.evidence_id],
            "The source supports the claim.",
            information_trust=ResearchInformationTrust.HIGH,
        )

        self.assertEqual(len(updated.assessments), 1)
        assessment = updated.assessments[0]
        self.assertEqual(assessment.assessment_id, "assessment-1")
        self.assertEqual(assessment.source_document_id, "document-1")
        self.assertEqual(assessment.evidence_ids, (evidence.evidence_id,))
        self.assertEqual(
            assessment.information_trust,
            ResearchInformationTrust.HIGH,
        )
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
            information_trust=ResearchInformationTrust.HIGH,
        ).assessments[-1]
        saves_before = len(self.store.saved)

        preview = self.manager.preview_source_assessment_write(
            run.run_id,
            "document-1",
            [evidence.evidence_id],
            "Corrected assessment.",
            original.assessment_id,
            ResearchInformationTrust.LOW,
        )

        self.assertTrue(preview.allowed)
        self.assertEqual(preview.supersedes_assessment, original)
        self.assertEqual(preview.information_trust, ResearchInformationTrust.LOW)
        self.assertEqual(len(self.store.saved), saves_before)

        updated = self.manager.record_source_assessment(
            run.run_id,
            "document-1",
            [evidence.evidence_id],
            "Corrected assessment.",
            original.assessment_id,
            ResearchInformationTrust.LOW,
        )

        self.assertEqual(len(updated.assessments), 2)
        self.assertEqual(
            updated.assessments[-1].supersedes_assessment_id,
            original.assessment_id,
        )
        self.assertEqual(updated.assessments[0], original)
        self.assertEqual(
            updated.assessments[-1].information_trust,
            ResearchInformationTrust.LOW,
        )
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

    def test_invalid_information_trust_is_rejected_before_mutation(self) -> None:
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
        saves_before = len(self.store.saved)

        with self.assertRaisesRegex(ResearchError, "information trust"):
            self.manager.preview_source_assessment_write(
                run.run_id,
                "document-1",
                [evidence.evidence_id],
                "Assessment.",
                information_trust="trusted",
            )

        self.assertEqual(self.manager.get(run.run_id), before)
        self.assertEqual(len(self.store.saved), saves_before)

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

    def test_claim_preview_record_and_correction_preserve_auditable_history(
        self,
    ) -> None:
        run = self.manager.create("Question")
        evidence = []
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
            evidence.append(
                self.manager.add_evidence(
                    run.run_id,
                    Chunk(
                        f"document-{number}",
                        0,
                        f"Evidence {number}.",
                        chunk_id=f"claim-chunk-{number}",
                    ),
                    f"Claim evidence {number}.",
                ).evidence[-1]
            )
        saves_before = len(self.store.saved)

        empty_history = self.manager.preview_claims(run.run_id)
        preview = self.manager.preview_claim_write(
            run.run_id,
            [evidence[1].evidence_id, evidence[0].evidence_id],
            "  The combined evidence likely supports the claim.  ",
            "likely",
            "medium",
        )

        self.assertEqual(empty_history.claims, ())
        self.assertEqual(len(self.store.saved), saves_before)
        self.assertTrue(preview.allowed)
        self.assertEqual(
            preview.text, "The combined evidence likely supports the claim."
        )
        self.assertEqual(preview.epistemic_state, ResearchEpistemicState.LIKELY)
        self.assertEqual(preview.confidence, ResearchClaimConfidence.MEDIUM)
        self.assertEqual(
            tuple(source.document_id for source in preview.sources),
            ("document-2", "document-1"),
        )

        original = self.manager.record_claim(
            run.run_id,
            [evidence[1].evidence_id, evidence[0].evidence_id],
            "The combined evidence likely supports the claim.",
            ResearchEpistemicState.LIKELY,
            ResearchClaimConfidence.MEDIUM,
        ).claims[-1]
        correction_preview = self.manager.preview_claim_write(
            run.run_id,
            [evidence[0].evidence_id],
            "The available evidence contradicts the original claim.",
            ResearchEpistemicState.CONTRADICTED,
            ResearchClaimConfidence.HIGH,
            original.claim_id,
        )
        corrected_run = self.manager.record_claim(
            run.run_id,
            [evidence[0].evidence_id],
            "The available evidence contradicts the original claim.",
            ResearchEpistemicState.CONTRADICTED,
            ResearchClaimConfidence.HIGH,
            original.claim_id,
        )

        self.assertEqual(original.claim_id, "claim-1")
        self.assertEqual(correction_preview.supersedes_claim, original)
        self.assertEqual(len(corrected_run.claims), 2)
        correction = corrected_run.claims[-1]
        self.assertEqual(correction.claim_id, "claim-2")
        self.assertEqual(correction.supersedes_claim_id, original.claim_id)
        self.assertEqual(correction.source_document_ids, ("document-1",))
        self.assertEqual(
            self.manager.preview_claims(run.run_id).claims,
            corrected_run.claims,
        )
        with self.assertRaisesRegex(ResearchError, "already been superseded"):
            self.manager.record_claim(
                run.run_id,
                [evidence[1].evidence_id],
                "Competing correction.",
                ResearchEpistemicState.UNKNOWN,
                ResearchClaimConfidence.UNASSESSED,
                original.claim_id,
            )

    def test_claim_contradiction_preview_record_and_duplicate_guard_are_atomic(
        self,
    ) -> None:
        run = self.manager.create("Compare claims")
        evidence = []
        claims = []
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
            evidence_record = self.manager.add_evidence(
                run.run_id,
                Chunk(
                    f"document-{number}",
                    0,
                    f"Evidence {number}.",
                    chunk_id=f"contradiction-chunk-{number}",
                ),
                f"Contradiction evidence {number}.",
            ).evidence[-1]
            evidence.append(evidence_record)
            claim = self.manager.record_claim(
                run.run_id,
                [evidence_record.evidence_id],
                f"Claim {number}.",
                ResearchEpistemicState.LIKELY,
                ResearchClaimConfidence.MEDIUM,
            ).claims[-1]
            claims.append(claim)
        saves_before_preview = len(self.store.saved)

        empty_history = self.manager.preview_claim_contradictions(run.run_id)
        preview = self.manager.preview_claim_contradiction_write(
            run.run_id,
            [claims[1].claim_id, claims[0].claim_id],
            "  The conclusions conflict under the same conditions.  ",
        )

        self.assertEqual(empty_history.contradictions, ())
        self.assertEqual(len(self.store.saved), saves_before_preview)
        self.assertTrue(preview.allowed)
        self.assertEqual(preview.claims, (claims[1], claims[0]))
        self.assertEqual(
            tuple(record.evidence_id for record in preview.evidence),
            (evidence[1].evidence_id, evidence[0].evidence_id),
        )
        self.assertEqual(
            preview.note,
            "The conclusions conflict under the same conditions.",
        )

        updated = self.manager.record_claim_contradiction(
            run.run_id,
            [claims[1].claim_id, claims[0].claim_id],
            "The conclusions conflict under the same conditions.",
        )
        contradiction = updated.claim_contradictions[-1]

        self.assertEqual(contradiction.contradiction_id, "contradiction-1")
        self.assertEqual(
            contradiction.claim_ids,
            (claims[1].claim_id, claims[0].claim_id),
        )
        self.assertEqual(
            contradiction.evidence_ids,
            (evidence[1].evidence_id, evidence[0].evidence_id),
        )
        self.assertEqual(
            self.manager.preview_claim_contradictions(run.run_id).contradictions,
            (contradiction,),
        )
        duplicate_preview = self.manager.preview_claim_contradiction_write(
            run.run_id,
            [claims[0].claim_id, claims[1].claim_id],
            "Duplicate relationship.",
        )
        self.assertFalse(duplicate_preview.allowed)
        self.assertIn("already exists", duplicate_preview.reason)
        before_duplicate = self.manager.get(run.run_id)
        saves_before_duplicate = len(self.store.saved)
        with self.assertRaisesRegex(ResearchError, "already exists"):
            self.manager.record_claim_contradiction(
                run.run_id,
                [claims[0].claim_id, claims[1].claim_id],
                "Duplicate relationship.",
            )
        self.assertEqual(self.manager.get(run.run_id), before_duplicate)
        self.assertEqual(len(self.store.saved), saves_before_duplicate)

    def test_claim_contradiction_rejects_unknown_closed_and_failed_save(self) -> None:
        run = self.manager.create("Compare claims")
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
            Chunk("document-1", 0, "Evidence.", chunk_id="contradiction-chunk"),
            "Relevant.",
        ).evidence[-1]
        first = self.manager.record_claim(
            run.run_id,
            [evidence.evidence_id],
            "Claim one.",
            ResearchEpistemicState.UNKNOWN,
        ).claims[-1]
        second = self.manager.record_claim(
            run.run_id,
            [evidence.evidence_id],
            "Claim two.",
            ResearchEpistemicState.UNKNOWN,
        ).claims[-1]
        before = self.manager.get(run.run_id)
        with self.assertRaisesRegex(ResearchError, "requires claims from this run"):
            self.manager.preview_claim_contradiction_write(
                run.run_id,
                [first.claim_id, "claim-missing"],
                "Unknown claim.",
            )
        self.assertEqual(self.manager.get(run.run_id), before)

        self.store.error = ResearchError("Store unavailable.")
        with self.assertRaisesRegex(ResearchError, "Store unavailable"):
            self.manager.record_claim_contradiction(
                run.run_id,
                [first.claim_id, second.claim_id],
                "The claims conflict.",
            )
        self.assertEqual(self.manager.get(run.run_id), before)
        self.store.error = None
        self.manager.transition_status(run.run_id, ResearchRunStatus.COMPLETED)
        closed_preview = self.manager.preview_claim_contradiction_write(
            run.run_id,
            [first.claim_id, second.claim_id],
            "Too late.",
        )
        self.assertFalse(closed_preview.allowed)
        self.assertIn("closed", closed_preview.reason)
        with self.assertRaisesRegex(ResearchError, "closed"):
            self.manager.record_claim_contradiction(
                run.run_id,
                [first.claim_id, second.claim_id],
                "Too late.",
            )

    def test_claim_write_rejects_invalid_inputs_before_mutation(self) -> None:
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
            Chunk("document-1", 0, "Evidence.", chunk_id="claim-chunk"),
            "Relevant.",
        ).evidence[-1]
        before = self.manager.get(run.run_id)
        saves_before = len(self.store.saved)

        invalid_values = (
            (["missing-evidence"], "Claim.", "unknown", "unassessed"),
            ([evidence.evidence_id], "Claim.", "certain", "high"),
            ([evidence.evidence_id], "Claim.", "fact", "certain"),
        )
        for evidence_ids, text, state, confidence in invalid_values:
            with self.subTest(state=state, confidence=confidence):
                with self.assertRaises(ResearchError):
                    self.manager.preview_claim_write(
                        run.run_id,
                        evidence_ids,
                        text,
                        state,
                        confidence,
                    )

        self.assertEqual(self.manager.get(run.run_id), before)
        self.assertEqual(len(self.store.saved), saves_before)

    def test_closed_run_blocks_claim_write_and_failed_save_is_atomic(self) -> None:
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
            Chunk("document-1", 0, "Evidence.", chunk_id="claim-chunk"),
            "Relevant.",
        ).evidence[-1]
        before = self.manager.get(run.run_id)
        self.store.error = ResearchError("Store unavailable.")

        with self.assertRaisesRegex(ResearchError, "Store unavailable"):
            self.manager.record_claim(
                run.run_id,
                [evidence.evidence_id],
                "Claim.",
                ResearchEpistemicState.UNKNOWN,
            )
        self.assertEqual(self.manager.get(run.run_id), before)
        self.store.error = None
        self.manager.transition_status(run.run_id, ResearchRunStatus.COMPLETED)

        preview = self.manager.preview_claim_write(
            run.run_id,
            [evidence.evidence_id],
            "Too late.",
            ResearchEpistemicState.UNKNOWN,
        )

        self.assertFalse(preview.allowed)
        self.assertIn("closed", preview.reason)
        with self.assertRaisesRegex(ResearchError, "closed"):
            self.manager.record_claim(
                run.run_id,
                [evidence.evidence_id],
                "Too late.",
                ResearchEpistemicState.UNKNOWN,
            )


if __name__ == "__main__":
    unittest.main()
