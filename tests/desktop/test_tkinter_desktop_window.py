"""Headless unit coverage for desktop-only presentation helpers."""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainResponse import BrainResponse
from desktop.TkinterDesktopWindow import (
    TkinterDesktopWindow,
    _accessibility_palette,
    _format_citations,
    _next_font_size,
    _preview_and_confirm_knowledge_relation,
    _preview_and_confirm_knowledge_relation_removal,
    _preview_and_confirm_session_rename,
)
from knowledge.Document import DocumentType
from knowledge.KnowledgeCitation import KnowledgeCitation
from knowledge.KnowledgeDocumentReference import KnowledgeDocumentReference
from research.ResearchRun import ResearchRun
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchRunStatusTransitionPreview import (
    ResearchRunStatusTransitionPreview,
)
from research.ResearchSourceAssessmentPreview import ResearchSourceAssessmentPreview
from research.ResearchSourceCandidate import ResearchSourceCandidate
from research.ResearchSourceCandidateAcceptancePreview import (
    ResearchSourceCandidateAcceptancePreview,
)
from research.ResearchSourceDiscoveryRecord import ResearchSourceDiscoveryRecord
from research.ResearchSourceRecord import ResearchSourceRecord


class AccessibilityPreferenceTests(unittest.TestCase):
    def test_text_size_adjustments_remain_within_a_readable_range(self) -> None:
        self.assertEqual(_next_font_size(12, 1), 13)
        self.assertEqual(_next_font_size(10, -1), 10)
        self.assertEqual(_next_font_size(20, 1), 20)

    def test_high_contrast_palette_uses_explicit_readable_colors(self) -> None:
        palette = _accessibility_palette(high_contrast=True)

        self.assertEqual(palette.background, "#000000")
        self.assertEqual(palette.foreground, "#FFFFFF")
        self.assertEqual(palette.field_background, "#000000")
        self.assertNotEqual(palette.selection_background, palette.background)
        self.assertNotEqual(palette.focus_color, palette.background)

    def test_window_applies_text_size_and_high_contrast_to_text_controls(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        window._font_size = 18
        window._high_contrast = RecordingBoolean(True)
        window._font_size_label = RecordingStatus()
        window._root = RecordingWidget()
        window._style = RecordingStyle()
        window._session_list = RecordingWidget()
        window._transcript = RecordingWidget()
        window._composer = RecordingWidget()

        window._apply_accessibility_preferences()

        self.assertEqual(window._font_size_label.values, ["Text size: 18 pt"])
        self.assertEqual(window._root.configurations["background"], "#000000")
        self.assertEqual(
            window._session_list.configurations["font"], ("TkDefaultFont", 18)
        )
        self.assertEqual(window._composer.configurations["foreground"], "#FFFFFF")
        self.assertIn("TButton", window._style.configurations)
        self.assertIn("TEntry", window._style.mappings)


class RecordingBoolean:
    def __init__(self, value: bool) -> None:
        self._value = value

    def get(self) -> bool:
        return self._value


class RecordingWidget:
    def __init__(self) -> None:
        self.configurations: dict[str, object] = {}

    def configure(self, **kwargs: object) -> None:
        self.configurations.update(kwargs)


class RecordingStyle:
    def __init__(self) -> None:
        self.configurations: dict[str, dict[str, object]] = {}
        self.mappings: dict[str, dict[str, object]] = {}

    def configure(self, style_name: str, **kwargs: object) -> None:
        self.configurations[style_name] = kwargs

    def map(self, style_name: str, **kwargs: object) -> None:
        self.mappings[style_name] = kwargs


class CitationFormattingTests(unittest.TestCase):
    def test_formats_existing_citations_in_response_order(self) -> None:
        citations = [
            KnowledgeCitation(
                document_id="project-notes",
                document_title="Project Notes",
                source="C:/knowledge/project.md",
                chunk_index=2,
                chunk_id="project-notes:2",
            ),
            KnowledgeCitation(
                document_id="ideas",
                document_title="Ideas",
                source="C:/knowledge/ideas.txt",
                chunk_index=0,
                chunk_id="ideas:0",
            ),
        ]

        rendered = _format_citations(citations)

        self.assertEqual(
            rendered,
            "1. Project Notes — C:/knowledge/project.md "
            "(paragraph 3; project-notes:2)\n"
            "2. Ideas — C:/knowledge/ideas.txt (paragraph 1; ideas:0)",
        )

    def test_uses_a_safe_source_fallback_and_keeps_empty_responses_empty(self) -> None:
        citation = KnowledgeCitation(
            document_id="untitled",
            document_title="(untitled)",
            source="",
            chunk_index=0,
            chunk_id="untitled:0",
        )

        self.assertEqual(_format_citations([]), "")
        self.assertEqual(
            _format_citations([citation]),
            "1. (untitled) — local source unavailable (paragraph 1; untitled:0)",
        )


class LocalKnowledgeFileSelectionTests(unittest.TestCase):
    def test_selected_file_is_passed_to_the_existing_controller_boundary(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingKnowledgeLoadController()
        responses: list[BrainResponse] = []
        window._root = object()
        window._controller = controller
        window._status = RecordingStatus()
        window._append_response = responses.append

        with patch(
            "desktop.TkinterDesktopWindow.filedialog.askopenfilename",
            return_value="C:/Local Notes/project plan.md",
        ) as choose_file:
            window._load_knowledge()

        self.assertEqual(controller.paths, ["C:/Local Notes/project plan.md"])
        self.assertEqual(responses, [controller.response])
        self.assertEqual(
            choose_file.call_args.kwargs["title"],
            "Load local knowledge source",
        )
        self.assertEqual(
            choose_file.call_args.kwargs["filetypes"][0],
            ("Knowledge files", "*.md *.txt"),
        )

    def test_cancelled_file_selection_does_not_call_the_controller(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingKnowledgeLoadController()
        status = RecordingStatus()
        window._root = object()
        window._controller = controller
        window._status = status
        window._append_response = lambda _response: self.fail("must not append")

        with patch(
            "desktop.TkinterDesktopWindow.filedialog.askopenfilename",
            return_value="",
        ):
            window._load_knowledge()

        self.assertEqual(controller.paths, [])
        self.assertEqual(status.values, ["knowledge load: cancelled"])


class InternetResearchSourceSelectionTests(unittest.TestCase):
    def test_entered_url_is_passed_to_the_existing_controller_boundary(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        responses: list[BrainResponse] = []
        window._controller = controller
        window._research_url = RecordingInput("https://example.com/research")
        window._research_run_id = RecordingInput("run-123")
        window._status = RecordingStatus()
        window._append_response = responses.append

        window._load_research_source()

        self.assertEqual(
            controller.sources,
            [("https://example.com/research", "run-123")],
        )
        self.assertEqual(responses, [controller.response])

    def test_empty_url_stays_local_and_is_shown_as_status(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        status = RecordingStatus()
        window._controller = controller
        window._research_url = RecordingInput("  ")
        window._research_run_id = RecordingInput("")
        window._status = status
        window._append_response = lambda _response: self.fail("must not append")

        window._load_research_source()

        self.assertEqual(controller.sources, [])
        self.assertEqual(status.values, ["A research source URL cannot be empty."])

    def test_created_run_identifier_is_selected_for_the_next_source(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        responses: list[BrainResponse] = []
        run_id = RecordingVariable("")
        window._controller = controller
        window._research_question = RecordingInput("Compare local models")
        window._research_run_id = run_id
        window._research_candidate = RecordingVariable("old candidate")
        window._research_candidate_selector = RecordingCandidateSelector(
            selected_index=0
        )
        window._research_candidates = (
            ResearchSourceCandidate(
                url="https://doi.org/10.1000/old",
                title="Old paper",
                snippet="",
            ),
        )
        window._research_candidate_run_id = "old-run"
        window._status = RecordingStatus()
        window._append_response = responses.append

        window._create_research_run()

        self.assertEqual(controller.questions, ["Compare local models"])
        self.assertEqual(run_id.value, "run-123")
        self.assertEqual(window._research_candidates, ())
        self.assertEqual(window._research_candidate_run_id, "")
        self.assertEqual(responses, [controller.create_response])

    def test_research_run_catalog_is_requested_without_network_fetch(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        responses: list[BrainResponse] = []
        window._controller = controller
        window._append_response = responses.append

        window._show_research_runs()

        self.assertEqual(controller.list_calls, 1)
        self.assertEqual(controller.sources, [])
        self.assertEqual(responses, [controller.list_response])

    def test_discovery_renders_unaccepted_candidates_without_loading_them(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        responses: list[BrainResponse] = []
        selector = RecordingCandidateSelector()
        window._controller = controller
        window._research_run_id = RecordingInput("run-123")
        window._research_candidate = RecordingVariable("stale")
        window._research_candidate_selector = selector
        window._research_candidates = ()
        window._research_candidate_run_id = ""
        window._status = RecordingStatus()
        window._append_response = responses.append

        window._discover_research_sources()

        self.assertEqual(controller.discovery_calls, ["run-123"])
        self.assertEqual(controller.sources, [])
        self.assertEqual(responses, [controller.discovery_response])
        self.assertEqual(window._research_candidates, controller.candidates)
        self.assertEqual(window._research_candidate_run_id, "run-123")
        self.assertEqual(
            selector.values,
            (
                "1. First paper — https://doi.org/10.1000/first",
                "2. Second paper — https://doi.org/10.1000/second",
            ),
        )
        self.assertEqual(selector.selected_index, 0)

    def test_selected_candidate_only_copies_its_url_until_load_is_separate(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        selector = RecordingCandidateSelector(selected_index=1)
        url = RecordingVariable("")
        status = RecordingStatus()
        window._controller = controller
        window._research_candidate_selector = selector
        window._research_candidates = controller.candidates
        window._research_candidate_run_id = "run-123"
        window._research_run_id = RecordingInput("run-123")
        window._research_url = url
        window._status = status

        window._use_selected_research_candidate()

        self.assertEqual(url.value, "https://doi.org/10.1000/second")
        self.assertEqual(controller.sources, [])
        self.assertEqual(
            status.values,
            ["research candidate: URL copied; source not loaded"],
        )

    def test_missing_candidate_selection_does_not_copy_or_load_a_url(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        url = RecordingVariable("https://example.com/existing")
        status = RecordingStatus()
        window._controller = controller
        window._research_candidate_selector = RecordingCandidateSelector()
        window._research_candidates = ()
        window._research_candidate_run_id = "run-123"
        window._research_run_id = RecordingInput("run-123")
        window._research_url = url
        window._status = status

        window._use_selected_research_candidate()

        self.assertEqual(url.value, "https://example.com/existing")
        self.assertEqual(controller.sources, [])
        self.assertEqual(
            status.values,
            ["Select a discovered source candidate first."],
        )

    def test_candidate_from_another_run_cannot_be_copied(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        url = RecordingVariable("")
        status = RecordingStatus()
        window._controller = controller
        window._research_candidate_selector = RecordingCandidateSelector(
            selected_index=0
        )
        window._research_candidates = controller.candidates
        window._research_candidate_run_id = "run-123"
        window._research_run_id = RecordingInput("run-456")
        window._research_url = url
        window._status = status

        window._use_selected_research_candidate()

        self.assertEqual(url.value, "")
        self.assertEqual(controller.sources, [])
        self.assertEqual(
            status.values,
            ["Select a discovered source candidate first."],
        )

    def test_empty_run_id_stays_local_before_candidate_discovery(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        status = RecordingStatus()
        window._controller = controller
        window._research_run_id = RecordingInput("  ")
        window._status = status
        window._append_response = lambda _response: self.fail("must not append")

        window._discover_research_sources()

        self.assertEqual(controller.discovery_calls, [])
        self.assertEqual(status.values, ["A research run ID cannot be empty."])

    def test_selected_chunk_and_note_are_passed_to_evidence_boundary(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        responses: list[BrainResponse] = []
        window._controller = controller
        window._research_run_id = RecordingInput("run-123")
        window._research_chunk_id = RecordingInput("chunk-456")
        window._research_evidence_note = RecordingInput("Supports the comparison.")
        window._status = RecordingStatus()
        window._append_response = responses.append

        window._record_research_evidence()

        self.assertEqual(
            controller.evidence_calls,
            [("run-123", "chunk-456", "Supports the comparison.")],
        )
        self.assertEqual(responses, [controller.evidence_response])

    def test_empty_evidence_note_stays_local_and_is_shown_as_status(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        status = RecordingStatus()
        window._controller = controller
        window._research_run_id = RecordingInput("run-123")
        window._research_chunk_id = RecordingInput("chunk-456")
        window._research_evidence_note = RecordingInput(" ")
        window._status = status
        window._append_response = lambda _response: self.fail("must not append")

        window._record_research_evidence()

        self.assertEqual(controller.evidence_calls, [])
        self.assertEqual(
            status.values,
            ["A research evidence note cannot be empty."],
        )

    def test_selected_run_evidence_catalog_is_requested_read_only(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        responses: list[BrainResponse] = []
        window._controller = controller
        window._research_run_id = RecordingInput("run-123")
        window._status = RecordingStatus()
        window._append_response = responses.append

        window._show_research_evidence()

        self.assertEqual(controller.evidence_list_calls, ["run-123"])
        self.assertEqual(responses, [controller.evidence_list_response])

    def test_source_assessment_preview_uses_selected_run_and_document(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        responses: list[BrainResponse] = []
        window._controller = controller
        window._research_run_id = RecordingInput("run-123")
        window._research_source_document_id = RecordingInput("document-123")
        window._status = RecordingStatus()
        window._append_response = responses.append

        window._preview_research_source_assessment()

        self.assertEqual(
            controller.assessment_previews,
            [("run-123", "document-123")],
        )
        self.assertEqual(responses, [controller.assessment_preview_response])

    def test_accepted_load_selects_its_source_document_for_assessment(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        selected = RecordingVariable("")
        window._research_source_document_id = selected
        now = datetime(2026, 8, 20, tzinfo=UTC)
        source = ResearchSourceRecord(
            "document-123",
            "https://example.com/paper",
            "Paper",
            "text/plain",
            now,
            now,
        )
        run = ResearchRun(
            "run-123",
            "Question",
            ResearchRunStatus.COLLECTING,
            (source,),
            (),
            now,
            now,
        )
        response = BrainResponse(
            message="Loaded.",
            request_id="load",
            intent="research_source_load",
            memory_count=0,
            knowledge_documents=[
                KnowledgeDocumentReference(
                    "document-123",
                    "Paper",
                    "https://example.com/paper",
                    DocumentType.WEB,
                    1,
                )
            ],
            research_runs=[run],
        )

        window._capture_accepted_research_source(response)

        self.assertEqual(selected.value, "document-123")

    def test_empty_source_assessment_document_stays_local(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        status = RecordingStatus()
        window._controller = controller
        window._research_run_id = RecordingInput("run-123")
        window._research_source_document_id = RecordingInput(" ")
        window._status = status
        window._append_response = lambda _response: self.fail("must not append")

        window._preview_research_source_assessment()

        self.assertEqual(controller.assessment_previews, [])
        self.assertEqual(
            status.values,
            ["A research source document ID cannot be empty."],
        )

    def test_allowed_research_status_preview_requires_confirmation_before_update(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        responses: list[BrainResponse] = []
        window._root = object()
        window._controller = controller
        window._research_run_id = RecordingInput("run-123")
        window._research_target_status = RecordingInput("cancelled")
        window._status = RecordingStatus()
        window._append_response = responses.append

        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno",
            return_value=True,
        ) as confirm:
            window._preview_and_update_research_status()

        self.assertEqual(controller.status_previews, [("run-123", "cancelled")])
        self.assertEqual(controller.status_updates, [("run-123", "cancelled")])
        self.assertEqual(
            responses,
            [controller.status_preview_response, controller.status_update_response],
        )
        confirm.assert_called_once()

    def test_declined_research_status_preview_does_not_update(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        status = RecordingStatus()
        window._root = object()
        window._controller = controller
        window._research_run_id = RecordingInput("run-123")
        window._research_target_status = RecordingInput("cancelled")
        window._status = status
        window._append_response = lambda _response: None

        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno",
            return_value=False,
        ):
            window._preview_and_update_research_status()

        self.assertEqual(controller.status_updates, [])
        self.assertEqual(status.values, ["research status: not updated"])

    def test_blocked_research_status_preview_cannot_request_confirmation(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        blocked = ResearchRunStatusTransitionPreview(
            run_id="run-123",
            current_status=ResearchRunStatus.COLLECTING,
            target_status=ResearchRunStatus.COMPLETED,
            allowed=False,
            reason="A completed research run requires evidence.",
        )
        controller.status_preview_response = BrainResponse(
            message="Preview blocked.",
            request_id="research-status-preview-blocked",
            intent="research_run_status_preview",
            memory_count=0,
            research_run_status_transition_preview=blocked,
        )
        window._root = object()
        window._controller = controller
        window._research_run_id = RecordingInput("run-123")
        window._research_target_status = RecordingInput("completed")
        window._status = RecordingStatus()
        window._append_response = lambda _response: None

        with patch("desktop.TkinterDesktopWindow.messagebox.askyesno") as confirm:
            window._preview_and_update_research_status()

        confirm.assert_not_called()
        self.assertEqual(controller.status_updates, [])

    def test_allowed_candidate_preview_requires_confirmation_before_accept(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        responses: list[BrainResponse] = []
        window._root = object()
        window._controller = controller
        window._research_run_id = RecordingInput("run-123")
        window._research_candidate_run_id = "run-123"
        window._research_candidate_discovery_id = "discovery-1"
        window._research_candidates = controller.candidates
        window._research_candidate_selector = RecordingCandidateSelector(0)
        window._status = RecordingStatus()
        window._append_response = responses.append

        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=True
        ) as confirm:
            window._preview_and_accept_research_candidate()

        expected = ("run-123", "discovery-1", controller.candidates[0].url)
        self.assertEqual(controller.candidate_previews, [expected])
        self.assertEqual(controller.candidate_accepts, [expected])
        self.assertEqual(
            responses,
            [
                controller.candidate_preview_response,
                controller.candidate_accept_response,
            ],
        )
        confirm.assert_called_once()

    def test_declined_candidate_preview_does_not_accept(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        status = RecordingStatus()
        window._root = object()
        window._controller = controller
        window._research_run_id = RecordingInput("run-123")
        window._research_candidate_run_id = "run-123"
        window._research_candidate_discovery_id = "discovery-1"
        window._research_candidates = controller.candidates
        window._research_candidate_selector = RecordingCandidateSelector(0)
        window._status = status
        window._append_response = lambda _response: None

        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=False
        ):
            window._preview_and_accept_research_candidate()

        self.assertEqual(controller.candidate_accepts, [])
        self.assertEqual(status.values, ["research candidate: not loaded"])

    def test_stale_candidate_selection_never_requests_preview(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        status = RecordingStatus()
        window._controller = controller
        window._research_run_id = RecordingInput("other-run")
        window._research_candidate_run_id = "run-123"
        window._research_candidate_discovery_id = "discovery-1"
        window._research_candidates = controller.candidates
        window._research_candidate_selector = RecordingCandidateSelector(0)
        window._status = status

        window._preview_and_accept_research_candidate()

        self.assertEqual(controller.candidate_previews, [])
        self.assertEqual(status.values, ["Select a discovered source candidate first."])


class RecordingKnowledgeLoadController:
    def __init__(self) -> None:
        self.paths: list[str] = []
        self.response = BrainResponse(
            message="Loaded.",
            request_id="load",
            intent="knowledge_load",
            memory_count=0,
        )

    def load_knowledge(self, path: str) -> BrainResponse:
        self.paths.append(path)
        return self.response


class RecordingResearchSourceLoadController:
    def __init__(self) -> None:
        self.sources: list[tuple[str, str]] = []
        self.questions: list[str] = []
        self.list_calls = 0
        self.discovery_calls: list[str] = []
        self.evidence_calls: list[tuple[str, str, str]] = []
        self.evidence_list_calls: list[str] = []
        self.status_previews: list[tuple[str, str]] = []
        self.status_updates: list[tuple[str, str]] = []
        self.candidate_previews: list[tuple[str, str, str]] = []
        self.candidate_accepts: list[tuple[str, str, str]] = []
        self.assessment_previews: list[tuple[str, str]] = []
        self.response = BrainResponse(
            message="Loaded.",
            request_id="research-source-load",
            intent="research_source_load",
            memory_count=0,
        )
        now = datetime(2026, 8, 20, tzinfo=UTC)
        run = ResearchRun(
            run_id="run-123",
            question="Compare local models",
            status=ResearchRunStatus.COLLECTING,
            sources=(),
            failures=(),
            created_at=now,
            updated_at=now,
        )
        self.candidates = (
            ResearchSourceCandidate(
                url="https://doi.org/10.1000/first",
                title="First paper",
                snippet="Journal · 2025",
            ),
            ResearchSourceCandidate(
                url="https://doi.org/10.1000/second",
                title="Second paper",
                snippet="Journal · 2024",
            ),
        )
        discovered_run = ResearchRun(
            run_id=run.run_id,
            question=run.question,
            status=run.status,
            sources=run.sources,
            failures=run.failures,
            created_at=run.created_at,
            updated_at=run.updated_at,
            discoveries=(
                ResearchSourceDiscoveryRecord(
                    discovery_id="discovery-1",
                    query=run.question,
                    provider="crossref-rest-v1",
                    candidates=self.candidates,
                    discovered_at=now,
                ),
            ),
        )
        accepted_source = ResearchSourceRecord(
            document_id="document-123",
            url="https://example.com/paper",
            title="Accepted paper",
            content_type="text/plain",
            fetched_at=now,
            added_at=now,
        )
        accepted_run = ResearchRun(
            run_id=run.run_id,
            question=run.question,
            status=run.status,
            sources=(accepted_source,),
            failures=run.failures,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )
        self.create_response = BrainResponse(
            message="Created.",
            request_id="research-run-create",
            intent="research_run_create",
            memory_count=0,
            research_runs=[run],
        )
        self.list_response = BrainResponse(
            message="Listed.",
            request_id="research-run-list",
            intent="research_run_list",
            memory_count=0,
            research_runs=[run],
        )
        self.discovery_response = BrainResponse(
            message="Candidates discovered.",
            request_id="research-source-discover",
            intent="research_source_discover",
            memory_count=0,
            research_runs=[discovered_run],
        )
        candidate_preview = ResearchSourceCandidateAcceptancePreview(
            "run-123",
            "discovery-1",
            self.candidates[0],
            True,
            "Candidate can be loaded.",
        )
        self.candidate_preview_response = BrainResponse(
            message="Candidate preview allowed.",
            request_id="candidate-preview",
            intent="research_source_candidate_acceptance_preview",
            memory_count=0,
            research_source_candidate_acceptance_preview=candidate_preview,
        )
        self.candidate_accept_response = BrainResponse(
            message="Candidate accepted.",
            request_id="candidate-accept",
            intent="research_source_candidate_accept",
            memory_count=0,
        )
        self.evidence_response = BrainResponse(
            message="Evidence recorded.",
            request_id="research-evidence-record",
            intent="research_evidence_record",
            memory_count=0,
            research_runs=[run],
        )
        self.evidence_list_response = BrainResponse(
            message="Evidence listed.",
            request_id="research-evidence-list",
            intent="research_evidence_list",
            memory_count=0,
            research_runs=[run],
        )
        assessment_preview = ResearchSourceAssessmentPreview(
            run_id=run.run_id,
            run_status=run.status,
            source=accepted_source,
            evidence=(),
            has_recorded_evidence=False,
            reason="No evidence has been selected.",
        )
        self.assessment_preview_response = BrainResponse(
            message="Assessment preview.",
            request_id="research-source-assessment-preview",
            intent="research_source_assessment_preview",
            memory_count=0,
            research_runs=[accepted_run],
            research_source_assessment_preview=assessment_preview,
        )
        status_preview = ResearchRunStatusTransitionPreview(
            run_id="run-123",
            current_status=ResearchRunStatus.COLLECTING,
            target_status=ResearchRunStatus.CANCELLED,
            allowed=True,
            reason="Research run can be marked cancelled.",
        )
        self.status_preview_response = BrainResponse(
            message="Preview allowed.",
            request_id="research-status-preview",
            intent="research_run_status_preview",
            memory_count=0,
            research_run_status_transition_preview=status_preview,
        )
        self.status_update_response = BrainResponse(
            message="Updated.",
            request_id="research-status-update",
            intent="research_run_status_update",
            memory_count=0,
            research_runs=[run],
        )

    def load_research_source(
        self, url: str, research_run_id: str = ""
    ) -> BrainResponse:
        if not url.strip():
            raise ValueError("A research source URL cannot be empty.")
        self.sources.append((url, research_run_id))
        return self.response

    def create_research_run(self, question: str) -> BrainResponse:
        if not question.strip():
            raise ValueError("A research question cannot be empty.")
        self.questions.append(question)
        return self.create_response

    def list_research_runs(self) -> BrainResponse:
        self.list_calls += 1
        return self.list_response

    def discover_research_sources(self, run_id: str) -> BrainResponse:
        if not run_id.strip():
            raise ValueError("A research run ID cannot be empty.")
        self.discovery_calls.append(run_id)
        return self.discovery_response

    def record_research_evidence(
        self,
        run_id: str,
        chunk_id: str,
        note: str,
    ) -> BrainResponse:
        if not run_id.strip():
            raise ValueError("A research run ID cannot be empty.")
        if not chunk_id.strip():
            raise ValueError("A research chunk ID cannot be empty.")
        if not note.strip():
            raise ValueError("A research evidence note cannot be empty.")
        self.evidence_calls.append((run_id, chunk_id, note))
        return self.evidence_response

    def list_research_evidence(self, run_id: str) -> BrainResponse:
        if not run_id.strip():
            raise ValueError("A research run ID cannot be empty.")
        self.evidence_list_calls.append(run_id)
        return self.evidence_list_response

    def preview_research_source_assessment(
        self,
        run_id: str,
        document_id: str,
    ) -> BrainResponse:
        if not run_id.strip():
            raise ValueError("A research run ID cannot be empty.")
        if not document_id.strip():
            raise ValueError("A research source document ID cannot be empty.")
        self.assessment_previews.append((run_id, document_id))
        return self.assessment_preview_response

    def preview_research_run_status(
        self,
        run_id: str,
        target_status: str,
    ) -> BrainResponse:
        self.status_previews.append((run_id, target_status))
        return self.status_preview_response

    def update_research_run_status(
        self,
        run_id: str,
        target_status: str,
    ) -> BrainResponse:
        self.status_updates.append((run_id, target_status))
        return self.status_update_response

    def preview_research_source_candidate_acceptance(
        self, run_id: str, discovery_id: str, candidate_url: str
    ) -> BrainResponse:
        self.candidate_previews.append((run_id, discovery_id, candidate_url))
        return self.candidate_preview_response

    def accept_research_source_candidate(
        self, run_id: str, discovery_id: str, candidate_url: str
    ) -> BrainResponse:
        self.candidate_accepts.append((run_id, discovery_id, candidate_url))
        return self.candidate_accept_response


class RecordingInput:
    def __init__(self, value: str) -> None:
        self._value = value

    def get(self) -> str:
        return self._value


class RecordingVariable(RecordingInput):
    @property
    def value(self) -> str:
        return self._value

    def set(self, value: str) -> None:
        self._value = value


class RecordingCandidateSelector:
    def __init__(self, selected_index: int = -1) -> None:
        self.selected_index = selected_index
        self.values: tuple[str, ...] = ()

    def configure(self, *, values: tuple[str, ...]) -> None:
        self.values = values

    def current(self, selected_index: int | None = None) -> int:
        if selected_index is not None:
            self.selected_index = selected_index
        return self.selected_index


class RecordingStatus:
    def __init__(self) -> None:
        self.values: list[str] = []

    def set(self, value: str) -> None:
        self.values.append(value)


class RelationConfirmationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.preview = BrainResponse(
            message="Changes: ready",
            request_id="preview",
            intent="knowledge_relation_preview",
            memory_count=0,
        )
        self.application = BrainResponse(
            message="Graph state: updated",
            request_id="apply",
            intent="knowledge_relation_apply",
            memory_count=0,
        )
        self.controller = RecordingRelationController(self.preview, self.application)

    def test_applies_only_after_a_successful_preview_is_confirmed(self) -> None:
        preview, application = _preview_and_confirm_knowledge_relation(
            self.controller,
            "source",
            "target",
            lambda response: response is self.preview,
        )

        self.assertIs(preview, self.preview)
        self.assertIs(application, self.application)
        self.assertEqual(
            self.controller.calls,
            [("preview", "source", "target"), ("apply", "source", "target")],
        )

    def test_does_not_apply_when_the_user_declines_the_preview(self) -> None:
        preview, application = _preview_and_confirm_knowledge_relation(
            self.controller,
            "source",
            "target",
            lambda _response: False,
        )

        self.assertIs(preview, self.preview)
        self.assertIsNone(application)
        self.assertEqual(self.controller.calls, [("preview", "source", "target")])

    def test_does_not_offer_or_apply_a_failed_preview(self) -> None:
        failed_preview = BrainResponse(
            message="The relation is invalid.",
            request_id="failed-preview",
            intent="knowledge_relation_preview",
            memory_count=0,
            success=False,
        )
        controller = RecordingRelationController(failed_preview, self.application)
        confirmations: list[BrainResponse] = []

        def confirm(response: BrainResponse) -> bool:
            confirmations.append(response)
            return True

        preview, application = _preview_and_confirm_knowledge_relation(
            controller,
            "source",
            "target",
            confirm,
        )

        self.assertIs(preview, failed_preview)
        self.assertIsNone(application)
        self.assertEqual(confirmations, [])
        self.assertEqual(controller.calls, [("preview", "source", "target")])


class RecordingRelationController:
    def __init__(self, preview: BrainResponse, application: BrainResponse) -> None:
        self.calls: list[tuple[str, str, str]] = []
        self._preview = preview
        self._application = application

    def preview_knowledge_relation(
        self,
        source_document_id: str,
        target_document_id: str,
    ) -> BrainResponse:
        self.calls.append(("preview", source_document_id, target_document_id))
        return self._preview

    def apply_knowledge_relation(
        self,
        source_document_id: str,
        target_document_id: str,
    ) -> BrainResponse:
        self.calls.append(("apply", source_document_id, target_document_id))
        return self._application


class RelationRemovalConfirmationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.preview = BrainResponse(
            message="Changes: ready to remove",
            request_id="removal-preview",
            intent="knowledge_relation_removal_preview",
            memory_count=0,
        )
        self.removal = BrainResponse(
            message="Graph state: updated",
            request_id="remove",
            intent="knowledge_relation_remove",
            memory_count=0,
        )
        self.controller = RecordingRelationRemovalController(
            self.preview,
            self.removal,
        )

    def test_removes_only_after_a_successful_preview_is_confirmed(self) -> None:
        preview, removal = _preview_and_confirm_knowledge_relation_removal(
            self.controller,
            "source",
            "target",
            lambda response: response is self.preview,
        )

        self.assertIs(preview, self.preview)
        self.assertIs(removal, self.removal)
        self.assertEqual(
            self.controller.calls,
            [("preview", "source", "target"), ("remove", "source", "target")],
        )

    def test_does_not_remove_when_the_user_declines_the_preview(self) -> None:
        preview, removal = _preview_and_confirm_knowledge_relation_removal(
            self.controller,
            "source",
            "target",
            lambda _response: False,
        )

        self.assertIs(preview, self.preview)
        self.assertIsNone(removal)
        self.assertEqual(self.controller.calls, [("preview", "source", "target")])

    def test_does_not_offer_or_remove_a_failed_preview(self) -> None:
        failed_preview = BrainResponse(
            message="The relation is unavailable.",
            request_id="failed-removal-preview",
            intent="knowledge_relation_removal_preview",
            memory_count=0,
            success=False,
        )
        controller = RecordingRelationRemovalController(failed_preview, self.removal)
        confirmations: list[BrainResponse] = []

        def confirm(response: BrainResponse) -> bool:
            confirmations.append(response)
            return True

        preview, removal = _preview_and_confirm_knowledge_relation_removal(
            controller,
            "source",
            "target",
            confirm,
        )

        self.assertIs(preview, failed_preview)
        self.assertIsNone(removal)
        self.assertEqual(confirmations, [])
        self.assertEqual(controller.calls, [("preview", "source", "target")])


class RecordingRelationRemovalController:
    def __init__(self, preview: BrainResponse, removal: BrainResponse) -> None:
        self.calls: list[tuple[str, str, str]] = []
        self._preview = preview
        self._removal = removal

    def preview_knowledge_relation_removal(
        self,
        source_document_id: str,
        target_document_id: str,
    ) -> BrainResponse:
        self.calls.append(("preview", source_document_id, target_document_id))
        return self._preview

    def remove_knowledge_relation(
        self,
        source_document_id: str,
        target_document_id: str,
    ) -> BrainResponse:
        self.calls.append(("remove", source_document_id, target_document_id))
        return self._removal


class SessionRenameConfirmationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.preview = BrainResponse(
            message="Changes: ready",
            request_id="rename-preview",
            intent="session_rename_preview",
            memory_count=2,
        )
        self.renamed = BrainResponse(
            message="Status: committed",
            request_id="rename",
            intent="session_rename",
            memory_count=2,
        )
        self.controller = RecordingSessionRenameController(self.preview, self.renamed)

    def test_renames_only_after_a_successful_preview_is_confirmed(self) -> None:
        preview, renamed = _preview_and_confirm_session_rename(
            self.controller,
            "work",
            "archive",
            lambda response: response is self.preview,
        )

        self.assertIs(preview, self.preview)
        self.assertIs(renamed, self.renamed)
        self.assertEqual(
            self.controller.calls,
            [("preview", "work", "archive"), ("rename", "work", "archive")],
        )

    def test_does_not_rename_when_the_user_declines_or_preview_fails(self) -> None:
        preview, renamed = _preview_and_confirm_session_rename(
            self.controller,
            "work",
            "archive",
            lambda _response: False,
        )

        self.assertIs(preview, self.preview)
        self.assertIsNone(renamed)
        self.assertEqual(self.controller.calls, [("preview", "work", "archive")])

        failed = BrainResponse(
            message="Session already exists.",
            request_id="failed-preview",
            intent="session_rename_preview",
            memory_count=0,
            success=False,
        )
        failed_controller = RecordingSessionRenameController(failed, self.renamed)
        preview, renamed = _preview_and_confirm_session_rename(
            failed_controller,
            "work",
            "archive",
            lambda _response: True,
        )

        self.assertIs(preview, failed)
        self.assertIsNone(renamed)
        self.assertEqual(failed_controller.calls, [("preview", "work", "archive")])


class RecordingSessionRenameController:
    def __init__(self, preview: BrainResponse, renamed: BrainResponse) -> None:
        self.calls: list[tuple[str, str, str]] = []
        self._preview = preview
        self._renamed = renamed

    def preview_session_rename(
        self,
        source_session_id: str,
        target_session_id: str,
    ) -> BrainResponse:
        self.calls.append(("preview", source_session_id, target_session_id))
        return self._preview

    def rename_session(
        self,
        source_session_id: str,
        target_session_id: str,
    ) -> BrainResponse:
        self.calls.append(("rename", source_session_id, target_session_id))
        return self._renamed
