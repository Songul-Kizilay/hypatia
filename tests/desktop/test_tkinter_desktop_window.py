"""Headless unit coverage for desktop-only presentation helpers."""

from __future__ import annotations

import sys
import unittest
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
from knowledge.KnowledgeCitation import KnowledgeCitation


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
