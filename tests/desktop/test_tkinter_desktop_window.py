"""Headless unit coverage for desktop-only presentation helpers."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainResponse import BrainResponse
from desktop.TkinterDesktopWindow import (
    _format_citations,
    _preview_and_confirm_knowledge_relation,
    _preview_and_confirm_knowledge_relation_removal,
)
from knowledge.KnowledgeCitation import KnowledgeCitation


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
