"""Headless regression coverage for the narrow desktop-to-Brain adapter."""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from core.CancellationSignal import CancellationSignal
from desktop.DesktopController import DesktopController
from research.ResearchRunMarkdownExportPreview import (
    ResearchRunMarkdownExportPreview,
)
from research.ResearchRunStatus import ResearchRunStatus


class RecordingBrain:
    """Minimal deterministic Brain substitute for desktop adapter tests."""

    def __init__(self, response: BrainResponse) -> None:
        self.requests: list[BrainRequest | str] = []
        self._response = response

    def process(self, request: BrainRequest | str) -> BrainResponse:
        self.requests.append(request)
        return self._response


class DesktopControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.response = BrainResponse(
            message="Completed.",
            request_id="desktop-test",
            intent="message",
            memory_count=0,
        )
        self.brain = RecordingBrain(self.response)
        self.controller = DesktopController(self.brain)

    def test_submit_message_preserves_non_empty_composer_text(self) -> None:
        message = "  Explain my active project.  "

        response = self.controller.submit_message(message)

        self.assertIs(response, self.response)
        self.assertEqual(self.brain.requests, [message])

    def test_submit_message_rejects_empty_text_without_calling_brain(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            self.controller.submit_message(" \t\n ")

        self.assertEqual(self.brain.requests, [])

    def test_select_session_uses_existing_explicit_session_command(self) -> None:
        response = self.controller.select_session("  Work-1  ")

        self.assertIs(response, self.response)
        self.assertEqual(self.brain.requests, ["use session Work-1"])

    def test_select_session_rejects_empty_id_without_calling_brain(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            self.controller.select_session("   ")

        self.assertEqual(self.brain.requests, [])

    def test_session_overview_uses_the_read_only_runtime_command(self) -> None:
        response = self.controller.session_overview()

        self.assertIs(response, self.response)
        self.assertEqual(self.brain.requests, ["session overview"])

    def test_session_details_uses_the_explicit_read_only_command(self) -> None:
        response = self.controller.session_details("  Work-1  ")

        self.assertIs(response, self.response)
        self.assertEqual(self.brain.requests, ["session details Work-1"])

    def test_session_recent_uses_the_explicit_read_only_command(self) -> None:
        response = self.controller.session_recent("  Work-1  ")

        self.assertIs(response, self.response)
        self.assertEqual(self.brain.requests, ["session recent Work-1"])

    def test_session_activity_uses_the_explicit_read_only_command(self) -> None:
        response = self.controller.session_activity("  Work-1  ")

        self.assertIs(response, self.response)
        self.assertEqual(self.brain.requests, ["session activity Work-1"])

    def test_session_specific_views_reject_empty_id_without_calling_brain(self) -> None:
        for action in (
            self.controller.session_details,
            self.controller.session_recent,
            self.controller.session_activity,
        ):
            with self.subTest(action=action.__name__):
                with self.assertRaisesRegex(ValueError, "cannot be empty"):
                    action("   ")

        self.assertEqual(self.brain.requests, [])

    def test_session_search_uses_the_existing_read_only_command(self) -> None:
        response = self.controller.session_search("  Work-1  ", " project plan ")

        self.assertIs(response, self.response)
        self.assertEqual(
            self.brain.requests,
            ["session search Work-1 -- project plan"],
        )

    def test_session_search_rejects_missing_session_or_query_without_brain_call(
        self,
    ) -> None:
        for session_id, query in (("", "project"), ("Work-1", " \t ")):
            with self.subTest(session_id=session_id, query=query):
                with self.assertRaisesRegex(ValueError, "cannot be empty"):
                    self.controller.session_search(session_id, query)

        self.assertEqual(self.brain.requests, [])

    def test_session_rename_preview_uses_the_existing_read_only_command(self) -> None:
        response = self.controller.preview_session_rename("  Work-1  ", " Archive ")

        self.assertIs(response, self.response)
        self.assertEqual(
            self.brain.requests,
            ["preview rename session Work-1 -- Archive"],
        )

    def test_session_rename_uses_the_existing_transactional_command(self) -> None:
        response = self.controller.rename_session("  Work-1  ", " Archive ")

        self.assertIs(response, self.response)
        self.assertEqual(self.brain.requests, ["rename session Work-1 -- Archive"])

    def test_session_rename_actions_reject_missing_ids_without_calling_brain(
        self,
    ) -> None:
        for action in (
            self.controller.preview_session_rename,
            self.controller.rename_session,
        ):
            for source_id, target_id in (("", "Archive"), ("Work-1", " \t ")):
                with self.subTest(action=action.__name__, ids=(source_id, target_id)):
                    with self.assertRaisesRegex(ValueError, "Both session IDs"):
                        action(source_id, target_id)

        self.assertEqual(self.brain.requests, [])

    def test_session_delete_actions_use_existing_guarded_commands(self) -> None:
        preview = self.controller.preview_session_delete("  Work-1  ")
        deleted = self.controller.delete_session("  Work-1  ")

        self.assertIs(preview, self.response)
        self.assertIs(deleted, self.response)
        self.assertEqual(
            self.brain.requests,
            ["preview delete session Work-1", "delete session Work-1"],
        )

    def test_recall_uses_the_explicit_lexical_command(self) -> None:
        response = self.controller.recall("  project plan  ")

        self.assertIs(response, self.response)
        self.assertEqual(self.brain.requests, ["recall project plan"])

    def test_semantic_recall_uses_the_explicit_opt_in_command(self) -> None:
        response = self.controller.semantic_recall("  project plan  ")

        self.assertIs(response, self.response)
        self.assertEqual(self.brain.requests, ["semantic recall project plan"])

    def test_recall_actions_reject_empty_query_without_calling_brain(self) -> None:
        for action in (self.controller.recall, self.controller.semantic_recall):
            with self.subTest(action=action.__name__):
                with self.assertRaisesRegex(ValueError, "cannot be empty"):
                    action(" \t\n ")

        self.assertEqual(self.brain.requests, [])

    def test_knowledge_context_uses_the_explicit_local_command(self) -> None:
        response = self.controller.knowledge_context("  project plan  ")

        self.assertIs(response, self.response)
        self.assertEqual(self.brain.requests, ["knowledge context project plan"])

    def test_knowledge_context_rejects_empty_query_without_calling_brain(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            self.controller.knowledge_context(" \t\n ")

        self.assertEqual(self.brain.requests, [])

    def test_knowledge_graph_uses_the_explicit_local_command(self) -> None:
        response = self.controller.knowledge_graph("  project plan  ")

        self.assertIs(response, self.response)
        self.assertEqual(self.brain.requests, ["knowledge graph project plan"])

    def test_knowledge_graph_rejects_empty_query_without_calling_brain(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            self.controller.knowledge_graph(" \t\n ")

        self.assertEqual(self.brain.requests, [])

    def test_load_knowledge_uses_a_structured_brain_request_for_a_spaced_path(
        self,
    ) -> None:
        response = self.controller.load_knowledge("  C:/Local Notes/project plan.md  ")

        self.assertIs(response, self.response)
        self.assertEqual(len(self.brain.requests), 1)
        request = self.brain.requests[0]
        self.assertIsInstance(request, BrainRequest)
        assert isinstance(request, BrainRequest)
        self.assertEqual(request.message, "Load selected local knowledge source")
        self.assertEqual(request.source, "desktop")
        self.assertEqual(
            request.metadata,
            {
                "intent": "knowledge_load",
                "knowledge_path": "C:/Local Notes/project plan.md",
            },
        )

    def test_load_knowledge_rejects_an_empty_path_without_calling_brain(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            self.controller.load_knowledge(" \t ")

        self.assertEqual(self.brain.requests, [])

    def test_load_research_source_uses_a_structured_explicit_request(self) -> None:
        cancellation_signal = CancellationSignal()
        response = self.controller.load_research_source(
            "  https://example.com/research  ",
            cancellation_token=cancellation_signal,
        )

        self.assertIs(response, self.response)
        self.assertEqual(len(self.brain.requests), 1)
        request = self.brain.requests[0]
        self.assertIsInstance(request, BrainRequest)
        assert isinstance(request, BrainRequest)
        self.assertEqual(request.message, "Load selected internet research source")
        self.assertEqual(request.source, "desktop")
        self.assertEqual(
            request.metadata,
            {
                "intent": "research_source_load",
                "research_url": "https://example.com/research",
            },
        )
        self.assertIs(request.cancellation_token, cancellation_signal)

    def test_create_research_run_uses_a_structured_explicit_request(self) -> None:
        response = self.controller.create_research_run("  Compare local models  ")

        self.assertIs(response, self.response)
        request = self.brain.requests[0]
        self.assertIsInstance(request, BrainRequest)
        assert isinstance(request, BrainRequest)
        self.assertEqual(request.message, "Create internet research run")
        self.assertEqual(request.source, "desktop")
        self.assertEqual(
            request.metadata,
            {
                "intent": "research_run_create",
                "research_question": "Compare local models",
            },
        )

    def test_create_research_run_rejects_empty_question_locally(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            self.controller.create_research_run(" \t ")

        self.assertEqual(self.brain.requests, [])

    def test_list_research_runs_uses_a_structured_read_only_request(self) -> None:
        response = self.controller.list_research_runs()

        self.assertIs(response, self.response)
        request = self.brain.requests[0]
        self.assertIsInstance(request, BrainRequest)
        assert isinstance(request, BrainRequest)
        self.assertEqual(request.message, "List internet research runs")
        self.assertEqual(request.source, "desktop")
        self.assertEqual(request.metadata, {"intent": "research_run_list"})

    def test_markdown_export_preview_uses_selected_run_without_a_path(self) -> None:
        response = self.controller.preview_research_run_markdown_export("  run-123  ")

        self.assertIs(response, self.response)
        request = self.brain.requests[0]
        self.assertIsInstance(request, BrainRequest)
        assert isinstance(request, BrainRequest)
        self.assertEqual(request.message, "Preview terminal research run as Markdown")
        self.assertEqual(request.source, "desktop")
        self.assertEqual(
            request.metadata,
            {
                "intent": "research_run_markdown_export_preview",
                "research_run_id": "run-123",
            },
        )

    def test_markdown_export_preview_rejects_empty_run_id_locally(self) -> None:
        with self.assertRaisesRegex(ValueError, "run ID cannot be empty"):
            self.controller.preview_research_run_markdown_export(" \t ")

        self.assertEqual(self.brain.requests, [])

    def test_markdown_export_save_binds_destination_to_exact_preview(self) -> None:
        markdown = "# Export\n"
        preview = ResearchRunMarkdownExportPreview(
            run_id="run-123",
            run_status=ResearchRunStatus.CANCELLED,
            snapshot_updated_at=datetime(2026, 8, 21, tzinfo=UTC),
            suggested_filename="hypatia-research-run-123.md",
            markdown_preview=markdown,
            total_character_count=len(markdown),
            omitted_character_count=0,
            content_sha256="a" * 64,
        )
        destination = str(Path.cwd() / "research export.md")

        response = self.controller.save_research_run_markdown_export(
            preview,
            f"  {destination}  ",
        )

        self.assertIs(response, self.response)
        request = self.brain.requests[0]
        self.assertIsInstance(request, BrainRequest)
        assert isinstance(request, BrainRequest)
        self.assertEqual(request.message, "Save previewed research run as Markdown")
        self.assertEqual(request.source, "desktop")
        self.assertEqual(
            request.metadata,
            {
                "intent": "research_run_markdown_export_save",
                "research_run_id": "run-123",
                "research_export_snapshot_updated_at": "2026-08-21T00:00:00+00:00",
                "research_export_content_sha256": "a" * 64,
                "research_export_destination_path": destination,
            },
        )

    def test_markdown_export_save_requires_preview_and_destination_locally(
        self,
    ) -> None:
        with self.assertRaisesRegex(ValueError, "preview is required"):
            self.controller.save_research_run_markdown_export(
                cast(ResearchRunMarkdownExportPreview, None),
                str(Path.cwd() / "export.md"),
            )

        markdown = "# Export\n"
        preview = ResearchRunMarkdownExportPreview(
            run_id="run-123",
            run_status=ResearchRunStatus.CANCELLED,
            snapshot_updated_at=datetime(2026, 8, 21, tzinfo=UTC),
            suggested_filename="hypatia-research-run-123.md",
            markdown_preview=markdown,
            total_character_count=len(markdown),
            omitted_character_count=0,
            content_sha256="a" * 64,
        )
        with self.assertRaisesRegex(ValueError, "destination cannot be empty"):
            self.controller.save_research_run_markdown_export(preview, " \t ")

        self.assertEqual(self.brain.requests, [])

    def test_markdown_export_verify_uses_selected_run_and_existing_file(self) -> None:
        source = str(Path.cwd() / "existing research.md")

        response = self.controller.verify_research_run_markdown_export(
            "  run-123  ",
            f"  {source}  ",
        )

        self.assertIs(response, self.response)
        request = self.brain.requests[0]
        self.assertIsInstance(request, BrainRequest)
        assert isinstance(request, BrainRequest)
        self.assertEqual(request.message, "Verify existing research Markdown export")
        self.assertEqual(request.source, "desktop")
        self.assertEqual(
            request.metadata,
            {
                "intent": "research_run_markdown_export_verify",
                "research_run_id": "run-123",
                "research_export_source_path": source,
            },
        )

    def test_markdown_export_verify_rejects_empty_selection_locally(self) -> None:
        source = str(Path.cwd() / "existing.md")
        for run_id, source_path, message in (
            ("", source, "run ID cannot be empty"),
            ("run-123", "", "verification file cannot be empty"),
        ):
            with self.subTest(run_id=run_id, source_path=source_path):
                with self.assertRaisesRegex(ValueError, message):
                    self.controller.verify_research_run_markdown_export(
                        run_id,
                        source_path,
                    )

        self.assertEqual(self.brain.requests, [])

    def test_discover_research_sources_uses_a_structured_explicit_request(
        self,
    ) -> None:
        cancellation_signal = CancellationSignal()
        response = self.controller.discover_research_sources(
            "  run-123  ",
            cancellation_token=cancellation_signal,
        )

        self.assertIs(response, self.response)
        request = self.brain.requests[-1]
        self.assertIsInstance(request, BrainRequest)
        assert isinstance(request, BrainRequest)
        self.assertEqual(request.message, "Discover candidate research sources")
        self.assertEqual(request.source, "desktop")
        self.assertEqual(
            request.metadata,
            {
                "intent": "research_source_discover",
                "research_run_id": "run-123",
            },
        )
        self.assertIs(request.cancellation_token, cancellation_signal)

    def test_discover_research_sources_rejects_empty_run_id_locally(self) -> None:
        with self.assertRaisesRegex(ValueError, "run ID cannot be empty"):
            self.controller.discover_research_sources(" \t ")

        self.assertEqual(self.brain.requests, [])

    def test_candidate_preview_and_accept_use_explicit_structured_requests(
        self,
    ) -> None:
        values = (" run-123 ", " discovery-1 ", " https://example.com/paper ")
        cancellation_signal = CancellationSignal()

        self.controller.preview_research_source_candidate_acceptance(*values)
        self.controller.accept_research_source_candidate(
            *values,
            cancellation_token=cancellation_signal,
        )

        expected = {
            "research_run_id": "run-123",
            "research_discovery_id": "discovery-1",
            "research_url": "https://example.com/paper",
        }
        first, second = self.brain.requests
        assert isinstance(first, BrainRequest)
        assert isinstance(second, BrainRequest)
        self.assertEqual(
            first.metadata,
            {"intent": "research_source_candidate_acceptance_preview", **expected},
        )
        self.assertEqual(
            second.metadata,
            {"intent": "research_source_candidate_accept", **expected},
        )
        self.assertIsNone(first.cancellation_token)
        self.assertIs(second.cancellation_token, cancellation_signal)

    def test_candidate_requests_reject_empty_identifiers_locally(self) -> None:
        for values in (
            ("", "discovery-1", "https://example.com/paper"),
            ("run-1", "", "https://example.com/paper"),
            ("run-1", "discovery-1", ""),
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.controller.preview_research_source_candidate_acceptance(*values)

        self.assertEqual(self.brain.requests, [])

    def test_record_research_evidence_uses_an_explicit_structured_request(self) -> None:
        response = self.controller.record_research_evidence(
            " run-123 ",
            " chunk-456 ",
            " This paragraph supports the comparison. ",
        )

        self.assertIs(response, self.response)
        request = self.brain.requests[0]
        self.assertIsInstance(request, BrainRequest)
        assert isinstance(request, BrainRequest)
        self.assertEqual(request.message, "Record selected research evidence")
        self.assertEqual(request.source, "desktop")
        self.assertEqual(
            request.metadata,
            {
                "intent": "research_evidence_record",
                "research_run_id": "run-123",
                "research_chunk_id": "chunk-456",
                "research_evidence_note": ("This paragraph supports the comparison."),
            },
        )

    def test_record_research_evidence_rejects_empty_fields_locally(self) -> None:
        for run_id, chunk_id, note in (
            ("", "chunk-1", "Note"),
            ("run-1", " ", "Note"),
            ("run-1", "chunk-1", "\t"),
        ):
            with self.subTest(values=(run_id, chunk_id, note)):
                with self.assertRaisesRegex(ValueError, "cannot be empty"):
                    self.controller.record_research_evidence(run_id, chunk_id, note)

        self.assertEqual(self.brain.requests, [])

    def test_list_research_evidence_uses_a_structured_read_only_request(self) -> None:
        response = self.controller.list_research_evidence(" run-123 ")

        self.assertIs(response, self.response)
        request = self.brain.requests[0]
        self.assertIsInstance(request, BrainRequest)
        assert isinstance(request, BrainRequest)
        self.assertEqual(request.message, "List selected research evidence")
        self.assertEqual(request.source, "desktop")
        self.assertEqual(
            request.metadata,
            {
                "intent": "research_evidence_list",
                "research_run_id": "run-123",
            },
        )

    def test_list_research_evidence_rejects_empty_run_id_locally(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            self.controller.list_research_evidence(" \t ")

        self.assertEqual(self.brain.requests, [])

    def test_claim_history_uses_structured_read_only_request(self) -> None:
        response = self.controller.preview_research_claims(" run-123 ")

        self.assertIs(response, self.response)
        request = cast(BrainRequest, self.brain.requests[0])
        self.assertEqual(request.message, "View evidence-linked research claims")
        self.assertEqual(
            request.metadata,
            {
                "intent": "research_claim_preview",
                "research_run_id": "run-123",
            },
        )

    def test_claim_preview_and_record_use_exact_authored_metadata(self) -> None:
        values = (
            " run-123 ",
            " evidence-2, evidence-1 ",
            "  The evidence contradicts the claim.  ",
            " contradicted ",
            " high ",
            " claim-previous ",
        )

        preview = self.controller.preview_research_claim_write(*values)
        recorded = self.controller.record_research_claim(*values)

        self.assertIs(preview, self.response)
        self.assertIs(recorded, self.response)
        expected = {
            "research_run_id": "run-123",
            "research_claim_evidence_ids": ["evidence-2", "evidence-1"],
            "research_claim_text": "The evidence contradicts the claim.",
            "research_claim_epistemic_state": "contradicted",
            "research_claim_confidence": "high",
            "research_claim_supersedes_id": "claim-previous",
        }
        self.assertEqual(
            cast(BrainRequest, self.brain.requests[0]).metadata,
            {"intent": "research_claim_write_preview", **expected},
        )
        self.assertEqual(
            cast(BrainRequest, self.brain.requests[1]).metadata,
            {"intent": "research_claim_record", **expected},
        )

    def test_claim_actions_reject_invalid_values_locally(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            self.controller.preview_research_claims(" ")
        invalid_values = (
            ("", "evidence-1", "Claim.", "unknown"),
            ("run-1", "", "Claim.", "unknown"),
            ("run-1", "evidence-1", "", "unknown"),
            ("run-1", "evidence-1, evidence-1", "Claim.", "unknown"),
            ("run-1", "evidence-1", "Claim.", "certain"),
            ("run-1", "evidence-1", "Claim.", "fact", "certain"),
        )
        for action in (
            self.controller.preview_research_claim_write,
            self.controller.record_research_claim,
        ):
            for values in invalid_values:
                with self.subTest(action=action.__name__, values=values):
                    with self.assertRaises(ValueError):
                        action(*values)

        self.assertEqual(self.brain.requests, [])

    def test_claim_contradiction_history_uses_structured_read_only_request(
        self,
    ) -> None:
        response = self.controller.preview_research_claim_contradictions(" run-123 ")

        self.assertIs(response, self.response)
        request = cast(BrainRequest, self.brain.requests[0])
        self.assertEqual(
            request.message,
            "View user-reviewed research claim contradictions",
        )
        self.assertEqual(
            request.metadata,
            {
                "intent": "research_claim_contradiction_preview",
                "research_run_id": "run-123",
            },
        )

    def test_claim_contradiction_suggestion_is_explicit_and_cancellable(self) -> None:
        cancellation_signal = CancellationSignal()

        response = self.controller.suggest_research_claim_contradictions(
            " run-123 ",
            cancellation_token=cancellation_signal,
        )

        self.assertIs(response, self.response)
        request = cast(BrainRequest, self.brain.requests[0])
        self.assertEqual(request.message, "suggest research claim contradictions")
        self.assertEqual(
            request.metadata,
            {
                "intent": "research_claim_contradiction_proposal",
                "research_run_id": "run-123",
            },
        )
        self.assertIs(request.cancellation_token, cancellation_signal)

    def test_claim_contradiction_suggestion_rejects_empty_run_locally(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            self.controller.suggest_research_claim_contradictions(" ")

        self.assertEqual(self.brain.requests, [])

    def test_claim_contradiction_preview_and_record_use_exact_authored_metadata(
        self,
    ) -> None:
        values = (
            " run-123 ",
            " claim-2, claim-1 ",
            "  The conclusions conflict under the same conditions.  ",
        )

        preview = self.controller.preview_research_claim_contradiction_write(*values)
        recorded = self.controller.record_research_claim_contradiction(*values)

        self.assertIs(preview, self.response)
        self.assertIs(recorded, self.response)
        expected = {
            "research_run_id": "run-123",
            "research_claim_contradiction_claim_ids": ["claim-2", "claim-1"],
            "research_claim_contradiction_note": (
                "The conclusions conflict under the same conditions."
            ),
        }
        self.assertEqual(
            cast(BrainRequest, self.brain.requests[0]).metadata,
            {"intent": "research_claim_contradiction_write_preview", **expected},
        )
        self.assertEqual(
            cast(BrainRequest, self.brain.requests[1]).metadata,
            {"intent": "research_claim_contradiction_record", **expected},
        )

    def test_claim_contradiction_actions_reject_invalid_values_locally(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            self.controller.preview_research_claim_contradictions(" ")
        invalid_values = (
            ("", "claim-1, claim-2", "Note."),
            ("run-1", "claim-1", "Note."),
            ("run-1", "claim-1, claim-1", "Note."),
            ("run-1", "claim-1, claim-2", ""),
        )
        for action in (
            self.controller.preview_research_claim_contradiction_write,
            self.controller.record_research_claim_contradiction,
        ):
            for values in invalid_values:
                with self.subTest(action=action.__name__, values=values):
                    with self.assertRaises(ValueError):
                        action(*values)

        self.assertEqual(self.brain.requests, [])

    def test_source_assessment_preview_uses_structured_read_only_request(self) -> None:
        response = self.controller.preview_research_source_assessment(
            " run-123 ",
            " document-456 ",
        )

        self.assertIs(response, self.response)
        request = self.brain.requests[0]
        self.assertIsInstance(request, BrainRequest)
        assert isinstance(request, BrainRequest)
        self.assertEqual(request.message, "Preview accepted research source assessment")
        self.assertEqual(request.source, "desktop")
        self.assertEqual(
            request.metadata,
            {
                "intent": "research_source_assessment_preview",
                "research_run_id": "run-123",
                "research_source_document_id": "document-456",
            },
        )

    def test_source_assessment_preview_rejects_empty_fields_locally(self) -> None:
        for values in (("", "document-1"), ("run-1", "")):
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.controller.preview_research_source_assessment(*values)

        self.assertEqual(self.brain.requests, [])

    def test_source_comparison_preview_uses_ordered_structured_request(self) -> None:
        response = self.controller.preview_research_source_comparison(
            " run-123 ",
            " document-2, document-1 ",
        )

        self.assertIs(response, self.response)
        request = self.brain.requests[0]
        self.assertIsInstance(request, BrainRequest)
        assert isinstance(request, BrainRequest)
        self.assertEqual(
            request.metadata,
            {
                "intent": "research_source_comparison_preview",
                "research_run_id": "run-123",
                "research_source_document_ids": ["document-2", "document-1"],
            },
        )

    def test_source_comparison_rejects_count_or_duplicates_locally(self) -> None:
        for source_ids in ("document-1", "document-1, document-1"):
            with self.subTest(source_ids=source_ids), self.assertRaises(ValueError):
                self.controller.preview_research_source_comparison(
                    "run-123",
                    source_ids,
                )

        self.assertEqual(self.brain.requests, [])

    def test_comparison_note_preview_and_record_use_exact_references(self) -> None:
        values = (
            " run-123 ",
            " document-2, document-1 ",
            " evidence-2, evidence-1 ",
            " assessment-2, assessment-1 ",
            "  My comparison note.  ",
        )

        preview = self.controller.preview_research_source_comparison_note_write(*values)
        recorded = self.controller.record_research_source_comparison_note(*values)

        self.assertIs(preview, self.response)
        self.assertIs(recorded, self.response)
        expected = {
            "research_run_id": "run-123",
            "research_source_document_ids": ["document-2", "document-1"],
            "research_comparison_evidence_ids": ["evidence-2", "evidence-1"],
            "research_comparison_assessment_ids": [
                "assessment-2",
                "assessment-1",
            ],
            "research_comparison_note_text": "My comparison note.",
        }
        preview_request = cast(BrainRequest, self.brain.requests[0])
        record_request = cast(BrainRequest, self.brain.requests[1])
        self.assertEqual(
            preview_request.metadata,
            {
                "intent": "research_source_comparison_note_write_preview",
                **expected,
            },
        )
        self.assertEqual(
            record_request.metadata,
            {"intent": "research_source_comparison_note_record", **expected},
        )

    def test_comparison_note_rejects_incomplete_or_duplicate_values(self) -> None:
        invalid_values = (
            ("", "document-1,document-2", "evidence-1", "assessment-1", "Note"),
            ("run-1", "document-1", "evidence-1", "assessment-1", "Note"),
            (
                "run-1",
                "document-1,document-1",
                "evidence-1",
                "assessment-1",
                "Note",
            ),
            (
                "run-1",
                "document-1,document-2",
                "",
                "assessment-1",
                "Note",
            ),
            (
                "run-1",
                "document-1,document-2",
                "evidence-1",
                "assessment-1,assessment-1",
                "Note",
            ),
            (
                "run-1",
                "document-1,document-2",
                "evidence-1",
                "assessment-1",
                "",
            ),
        )
        for action in (
            self.controller.preview_research_source_comparison_note_write,
            self.controller.record_research_source_comparison_note,
        ):
            for values in invalid_values:
                with self.subTest(action=action.__name__, values=values):
                    with self.assertRaises(ValueError):
                        action(*values)

        self.assertEqual(self.brain.requests, [])

    def test_assessment_write_preview_and_record_use_explicit_evidence(self) -> None:
        values = (
            " run-123 ",
            " document-456 ",
            " evidence-1, evidence-2 ",
            "  The source supports the claim.  ",
            " assessment-previous ",
            " high ",
        )

        preview = self.controller.preview_research_source_assessment_write(*values)
        recorded = self.controller.record_research_source_assessment(*values)

        self.assertIs(preview, self.response)
        self.assertIs(recorded, self.response)
        preview_request = self.brain.requests[0]
        record_request = self.brain.requests[1]
        self.assertIsInstance(preview_request, BrainRequest)
        self.assertIsInstance(record_request, BrainRequest)
        assert isinstance(preview_request, BrainRequest)
        assert isinstance(record_request, BrainRequest)
        expected = {
            "research_run_id": "run-123",
            "research_source_document_id": "document-456",
            "research_assessment_evidence_ids": ["evidence-1", "evidence-2"],
            "research_assessment_text": "The source supports the claim.",
            "research_assessment_supersedes_id": "assessment-previous",
            "research_information_trust": "high",
        }
        self.assertEqual(
            preview_request.metadata,
            {"intent": "research_source_assessment_write_preview", **expected},
        )
        self.assertEqual(
            record_request.metadata,
            {"intent": "research_source_assessment_record", **expected},
        )

    def test_assessment_write_rejects_empty_or_duplicate_values_locally(self) -> None:
        invalid_values = (
            ("", "document-1", "evidence-1", "Assessment."),
            ("run-1", "", "evidence-1", "Assessment."),
            ("run-1", "document-1", "", "Assessment."),
            ("run-1", "document-1", "evidence-1", ""),
            (
                "run-1",
                "document-1",
                "evidence-1, evidence-1",
                "Assessment.",
            ),
            (
                "run-1",
                "document-1",
                "evidence-1",
                "Assessment.",
                "",
                "trusted",
            ),
        )
        for action in (
            self.controller.preview_research_source_assessment_write,
            self.controller.record_research_source_assessment,
        ):
            for values in invalid_values:
                with self.subTest(action=action.__name__, values=values):
                    with self.assertRaises(ValueError):
                        action(*values)

        self.assertEqual(self.brain.requests, [])

    def test_research_status_preview_and_update_use_structured_requests(self) -> None:
        preview = self.controller.preview_research_run_status(
            " run-123 ",
            " CANCELLED ",
        )
        updated = self.controller.update_research_run_status(
            " run-123 ",
            " CANCELLED ",
        )

        self.assertIs(preview, self.response)
        self.assertIs(updated, self.response)
        requests = self.brain.requests
        self.assertEqual(len(requests), 2)
        self.assertTrue(all(isinstance(request, BrainRequest) for request in requests))
        assert isinstance(requests[0], BrainRequest)
        assert isinstance(requests[1], BrainRequest)
        expected_values = {
            "research_run_id": "run-123",
            "research_target_status": "cancelled",
        }
        self.assertEqual(
            requests[0].metadata,
            {"intent": "research_run_status_preview", **expected_values},
        )
        self.assertEqual(
            requests[1].metadata,
            {"intent": "research_run_status_update", **expected_values},
        )

    def test_research_status_actions_reject_invalid_values_locally(self) -> None:
        for action in (
            self.controller.preview_research_run_status,
            self.controller.update_research_run_status,
        ):
            for run_id, target in (("", "completed"), ("run-1", "collecting")):
                with self.subTest(action=action.__name__, values=(run_id, target)):
                    with self.assertRaises(ValueError):
                        action(run_id, target)

        self.assertEqual(self.brain.requests, [])

    def test_load_research_source_can_attach_to_an_explicit_run(self) -> None:
        response = self.controller.load_research_source(
            " https://example.com/research ",
            " run-123 ",
        )

        self.assertIs(response, self.response)
        request = self.brain.requests[0]
        self.assertIsInstance(request, BrainRequest)
        assert isinstance(request, BrainRequest)
        self.assertEqual(
            request.metadata,
            {
                "intent": "research_source_load",
                "research_url": "https://example.com/research",
                "research_run_id": "run-123",
            },
        )

    def test_load_research_source_rejects_empty_url_without_calling_brain(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            self.controller.load_research_source(" \t ")

        self.assertEqual(self.brain.requests, [])

    def test_ask_knowledge_uses_the_explicit_local_rag_command(self) -> None:
        response = self.controller.ask_knowledge("  what is the project plan?  ")

        self.assertIs(response, self.response)
        self.assertEqual(
            self.brain.requests,
            ["ask knowledge what is the project plan?"],
        )

    def test_ask_knowledge_rejects_empty_query_without_calling_brain(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            self.controller.ask_knowledge(" \t\n ")

        self.assertEqual(self.brain.requests, [])

    def test_knowledge_relation_preview_uses_the_existing_read_only_command(
        self,
    ) -> None:
        response = self.controller.preview_knowledge_relation("  source  ", " target ")

        self.assertIs(response, self.response)
        self.assertEqual(
            self.brain.requests,
            ["preview knowledge relation source -- target"],
        )

    def test_knowledge_relation_apply_uses_the_existing_mutating_command(self) -> None:
        response = self.controller.apply_knowledge_relation("  source  ", " target ")

        self.assertIs(response, self.response)
        self.assertEqual(
            self.brain.requests,
            ["apply knowledge relation source -- target"],
        )

    def test_knowledge_relation_actions_reject_missing_ids_without_calling_brain(
        self,
    ) -> None:
        for action in (
            self.controller.preview_knowledge_relation,
            self.controller.apply_knowledge_relation,
        ):
            for source_id, target_id in (("", "target"), ("source", " \t ")):
                with self.subTest(action=action.__name__, ids=(source_id, target_id)):
                    with self.assertRaisesRegex(
                        ValueError, "Both knowledge source IDs"
                    ):
                        action(source_id, target_id)

        self.assertEqual(self.brain.requests, [])

    def test_knowledge_relation_removal_preview_uses_the_existing_command(
        self,
    ) -> None:
        response = self.controller.preview_knowledge_relation_removal(
            "  source  ",
            " target ",
        )

        self.assertIs(response, self.response)
        self.assertEqual(
            self.brain.requests,
            ["preview remove knowledge relation source -- target"],
        )

    def test_knowledge_relation_removal_uses_the_existing_mutating_command(
        self,
    ) -> None:
        response = self.controller.remove_knowledge_relation("  source  ", " target ")

        self.assertIs(response, self.response)
        self.assertEqual(
            self.brain.requests,
            ["remove knowledge relation source -- target"],
        )

    def test_knowledge_relation_removal_actions_reject_missing_ids(self) -> None:
        for action in (
            self.controller.preview_knowledge_relation_removal,
            self.controller.remove_knowledge_relation,
        ):
            for source_id, target_id in (("", "target"), ("source", " \t ")):
                with self.subTest(action=action.__name__, ids=(source_id, target_id)):
                    with self.assertRaisesRegex(
                        ValueError, "Both knowledge source IDs"
                    ):
                        action(source_id, target_id)

        self.assertEqual(self.brain.requests, [])

    def test_list_knowledge_relations_uses_the_existing_read_only_command(
        self,
    ) -> None:
        response = self.controller.list_knowledge_relations()

        self.assertIs(response, self.response)
        self.assertEqual(self.brain.requests, ["list knowledge relations"])

    def test_list_knowledge_uses_the_existing_read_only_catalog_command(self) -> None:
        response = self.controller.list_knowledge()

        self.assertIs(response, self.response)
        self.assertEqual(self.brain.requests, ["list knowledge"])

    def test_semantic_status_uses_the_read_only_runtime_command(self) -> None:
        response = self.controller.semantic_status()

        self.assertIs(response, self.response)
        self.assertEqual(self.brain.requests, ["semantic recall status"])

    def test_research_content_status_uses_the_read_only_runtime_command(self) -> None:
        response = self.controller.research_content_status()

        self.assertIs(response, self.response)
        self.assertEqual(self.brain.requests, ["research content status"])

    def test_research_evidence_status_uses_the_read_only_runtime_command(self) -> None:
        response = self.controller.research_evidence_status()

        self.assertIs(response, self.response)
        self.assertEqual(self.brain.requests, ["research evidence status"])


if __name__ == "__main__":
    unittest.main()
