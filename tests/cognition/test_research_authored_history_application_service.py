"""Focused contracts for the read-only Research authored-history service."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from cognition.ResearchAuthoredHistoryApplicationService import (
    ResearchAuthoredHistoryApplicationService,
)
from core.Exceptions import ResearchError
from research.ResearchRunManager import ResearchRunManager
from response.ResponseComposer import ResponseComposer


class ResearchAuthoredHistoryApplicationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.composer = Mock(spec=ResponseComposer)
        self.manager = Mock(spec=ResearchRunManager)
        self.service = ResearchAuthoredHistoryApplicationService(
            self.composer,
            self.manager,
        )
        self.response = BrainResponse(
            message="ok",
            request_id="request-1",
            intent="test",
            memory_count=0,
        )

    def test_recognizers_accept_only_their_exact_structured_intents(self) -> None:
        recognizers = (
            (
                self.service.is_claim_preview_request,
                "research_claim_preview",
            ),
            (
                self.service.is_source_comparison_preview_request,
                "research_source_comparison_preview",
            ),
            (
                self.service.is_source_assessment_preview_request,
                "research_source_assessment_preview",
            ),
        )
        for recognizer, intent in recognizers:
            with self.subTest(intent=intent):
                self.assertTrue(
                    recognizer(BrainRequest("ignored", metadata={"intent": intent}))
                )
                self.assertFalse(recognizer(BrainRequest(intent)))
                self.assertFalse(
                    recognizer(
                        BrainRequest("ignored", metadata={"intent": f"{intent}_now"})
                    )
                )

    def test_claim_preview_rejects_invalid_run_identifiers(self) -> None:
        for run_id in (None, 7, "", "   "):
            with self.subTest(run_id=run_id):
                self.composer.reset_mock()
                self.composer.research_claim_preview_failure.return_value = (
                    self.response
                )
                request = BrainRequest(
                    "claims",
                    metadata={"research_run_id": run_id},
                )

                result = self.service.process_claim_preview(request)

                self.assertIs(result, self.response)
                self.composer.research_claim_preview_failure.assert_called_once_with(
                    request,
                    "A research run ID is required.",
                )
        self.manager.preview_claims.assert_not_called()

    def test_claim_preview_preserves_dependency_and_result_contracts(self) -> None:
        request = BrainRequest(
            "claims",
            metadata={"research_run_id": "  run-1  "},
        )
        unavailable = ResearchAuthoredHistoryApplicationService(self.composer, None)
        self.composer.research_claim_preview_failure.return_value = self.response
        self.assertIs(unavailable.process_claim_preview(request), self.response)
        self.composer.research_claim_preview_failure.assert_called_once_with(
            request,
            "Research run persistence is unavailable.",
        )

        self.composer.reset_mock()
        self.manager.preview_claims.side_effect = ResearchError("missing")
        self.composer.research_claim_preview_failure.return_value = self.response
        self.assertIs(self.service.process_claim_preview(request), self.response)
        self.composer.research_claim_preview_failure.assert_called_once_with(
            request,
            "Research run was not found.",
        )

        self.composer.reset_mock()
        preview = Mock()
        self.manager.preview_claims.side_effect = None
        self.manager.preview_claims.return_value = preview
        self.composer.research_claim_preview_success.return_value = self.response
        self.assertIs(self.service.process_claim_preview(request), self.response)
        self.manager.preview_claims.assert_called_with("  run-1  ")
        self.composer.research_claim_preview_success.assert_called_once_with(
            request,
            preview,
        )

    def test_comparison_preview_rejects_invalid_run_identifiers(self) -> None:
        for run_id in (None, 7, "", "   "):
            with self.subTest(run_id=run_id):
                self.composer.reset_mock()
                failure = self.composer.research_source_comparison_preview_failure
                failure.return_value = self.response
                request = BrainRequest(
                    "compare",
                    metadata={
                        "research_run_id": run_id,
                        "research_source_document_ids": ["document-1", "document-2"],
                    },
                )

                result = self.service.process_source_comparison_preview(request)

                self.assertIs(result, self.response)
                failure.assert_called_once_with(
                    request,
                    "A research run ID is required.",
                )
        self.manager.preview_source_comparison.assert_not_called()

    def test_comparison_preview_rejects_invalid_document_catalogs(self) -> None:
        invalid_catalogs: tuple[object, ...] = (
            None,
            "document-1",
            [],
            ["document-1"],
            ["1", "2", "3", "4", "5", "6"],
            ["document-1", ""],
            ["document-1", 7],
            [" document-1 ", "document-1"],
        )
        for document_ids in invalid_catalogs:
            with self.subTest(document_ids=document_ids):
                self.composer.reset_mock()
                failure = self.composer.research_source_comparison_preview_failure
                failure.return_value = self.response
                request = BrainRequest(
                    "compare",
                    metadata={
                        "research_run_id": "run-1",
                        "research_source_document_ids": document_ids,
                    },
                )

                result = self.service.process_source_comparison_preview(request)

                self.assertIs(result, self.response)
                failure.assert_called_once_with(
                    request,
                    "Two to five unique research source document IDs are required.",
                )
        self.manager.preview_source_comparison.assert_not_called()

    def test_comparison_preview_preserves_dependency_and_result_contracts(self) -> None:
        document_ids = [" document-1 ", "document-2"]
        request = BrainRequest(
            "compare",
            metadata={
                "research_run_id": " run-1 ",
                "research_source_document_ids": document_ids,
            },
        )
        unavailable = ResearchAuthoredHistoryApplicationService(self.composer, None)
        failure = self.composer.research_source_comparison_preview_failure
        failure.return_value = self.response
        self.assertIs(
            unavailable.process_source_comparison_preview(request),
            self.response,
        )
        failure.assert_called_once_with(
            request,
            "Research run persistence is unavailable.",
        )

        self.composer.reset_mock()
        self.manager.preview_source_comparison.side_effect = ResearchError("missing")
        failure.return_value = self.response
        self.assertIs(
            self.service.process_source_comparison_preview(request),
            self.response,
        )
        failure.assert_called_once_with(
            request,
            "Every comparison source must be accepted in the selected run.",
        )

        self.composer.reset_mock()
        preview = Mock()
        self.manager.preview_source_comparison.side_effect = None
        self.manager.preview_source_comparison.return_value = preview
        success = self.composer.research_source_comparison_preview_success
        success.return_value = self.response
        self.assertIs(
            self.service.process_source_comparison_preview(request),
            self.response,
        )
        self.manager.preview_source_comparison.assert_called_with(
            " run-1 ",
            document_ids,
        )
        success.assert_called_once_with(request, preview)

    def test_assessment_preview_rejects_invalid_identifiers(self) -> None:
        invalid_pairs = (
            (None, "document-1", "A research run ID is required."),
            ("", "document-1", "A research run ID is required."),
            ("run-1", None, "A research source document ID is required."),
            ("run-1", 7, "A research source document ID is required."),
            ("run-1", "   ", "A research source document ID is required."),
        )
        for run_id, document_id, message in invalid_pairs:
            with self.subTest(run_id=run_id, document_id=document_id):
                self.composer.reset_mock()
                failure = self.composer.research_source_assessment_preview_failure
                failure.return_value = self.response
                request = BrainRequest(
                    "assess",
                    metadata={
                        "research_run_id": run_id,
                        "research_source_document_id": document_id,
                    },
                )

                result = self.service.process_source_assessment_preview(request)

                self.assertIs(result, self.response)
                failure.assert_called_once_with(request, message)
        self.manager.preview_source_assessment.assert_not_called()

    def test_assessment_preview_preserves_dependency_and_result_contracts(self) -> None:
        request = BrainRequest(
            "assess",
            metadata={
                "research_run_id": " run-1 ",
                "research_source_document_id": " document-1 ",
            },
        )
        unavailable = ResearchAuthoredHistoryApplicationService(self.composer, None)
        failure = self.composer.research_source_assessment_preview_failure
        failure.return_value = self.response
        self.assertIs(
            unavailable.process_source_assessment_preview(request),
            self.response,
        )
        failure.assert_called_once_with(
            request,
            "Research run persistence is unavailable.",
        )

        self.composer.reset_mock()
        self.manager.preview_source_assessment.side_effect = ResearchError("missing")
        failure.return_value = self.response
        self.assertIs(
            self.service.process_source_assessment_preview(request),
            self.response,
        )
        failure.assert_called_once_with(
            request,
            "Research source was not found among this run's accepted sources.",
        )

        self.composer.reset_mock()
        preview = Mock()
        self.manager.preview_source_assessment.side_effect = None
        self.manager.preview_source_assessment.return_value = preview
        success = self.composer.research_source_assessment_preview_success
        success.return_value = self.response
        self.assertIs(
            self.service.process_source_assessment_preview(request),
            self.response,
        )
        self.manager.preview_source_assessment.assert_called_with(
            " run-1 ",
            " document-1 ",
        )
        success.assert_called_once_with(request, preview)


if __name__ == "__main__":
    unittest.main()
