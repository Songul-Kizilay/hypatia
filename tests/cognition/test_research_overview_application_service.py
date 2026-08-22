"""Focused contracts for the read-only Research overview service."""

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
from cognition.ResearchOverviewApplicationService import (
    ResearchOverviewApplicationService,
)
from core.Exceptions import ResearchError
from research.ResearchEvidenceIntegrityAuditor import (
    ResearchEvidenceIntegrityAuditor,
)
from research.ResearchEvidenceIntegrityStatus import ResearchEvidenceIntegrityStatus
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSourceContentRestorationStatus import (
    ResearchSourceContentRestorationStatus,
)
from response.ResponseComposer import ResponseComposer


class ResearchOverviewApplicationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.composer = Mock(spec=ResponseComposer)
        self.manager = Mock(spec=ResearchRunManager)
        self.auditor = Mock(spec=ResearchEvidenceIntegrityAuditor)
        self.service = ResearchOverviewApplicationService(
            self.composer,
            self.manager,
            None,
            self.auditor,
        )
        self.response = BrainResponse(
            message="ok",
            request_id="request-1",
            intent="test",
            memory_count=0,
        )

    def test_recognizers_preserve_structured_and_plain_command_contracts(self) -> None:
        run_list = BrainRequest(
            "ignored",
            metadata={"intent": "research_run_list"},
        )
        evidence_list = BrainRequest(
            "ignored",
            metadata={"intent": "research_evidence_list"},
        )
        restoration = BrainRequest("  ReSeArCh CoNtEnT StAtUs  ")
        integrity = BrainRequest("  ReSeArCh EvIdEnCe StAtUs  ")

        self.assertTrue(self.service.is_run_list_request(run_list))
        self.assertTrue(self.service.is_evidence_list_request(evidence_list))
        self.assertTrue(
            self.service.is_source_content_restoration_status_request(restoration)
        )
        self.assertTrue(self.service.is_evidence_integrity_status_request(integrity))
        self.assertFalse(
            self.service.is_run_list_request(BrainRequest("research run list"))
        )
        self.assertFalse(
            self.service.is_evidence_list_request(
                BrainRequest("research evidence list")
            )
        )
        self.assertFalse(
            self.service.is_source_content_restoration_status_request(
                BrainRequest("research content status now")
            )
        )
        self.assertFalse(
            self.service.is_evidence_integrity_status_request(
                BrainRequest("research evidence status now")
            )
        )

    def test_run_list_reports_unavailable_persistence(self) -> None:
        service = ResearchOverviewApplicationService(
            self.composer,
            None,
            None,
            None,
        )
        request = BrainRequest("list", request_id="request-1")
        self.composer.research_run_failure.return_value = self.response

        result = service.process_run_list(request)

        self.assertIs(result, self.response)
        self.composer.research_run_failure.assert_called_once_with(
            request,
            "Research run persistence is unavailable.",
            intent="research_run_list",
        )

    def test_run_list_composes_the_exact_manager_snapshot(self) -> None:
        request = BrainRequest("list", request_id="request-1")
        runs = [Mock()]
        self.manager.list.return_value = runs
        self.composer.research_run_list_success.return_value = self.response

        result = self.service.process_run_list(request)

        self.assertIs(result, self.response)
        self.composer.research_run_list_success.assert_called_once_with(request, runs)

    def test_evidence_list_rejects_invalid_run_identifiers(self) -> None:
        for run_id in (None, 7, "", "   "):
            with self.subTest(run_id=run_id):
                self.composer.reset_mock()
                self.composer.research_evidence_list_failure.return_value = (
                    self.response
                )
                request = BrainRequest(
                    "list evidence",
                    metadata={"research_run_id": run_id},
                )

                result = self.service.process_evidence_list(request)

                self.assertIs(result, self.response)
                self.composer.research_evidence_list_failure.assert_called_once_with(
                    request,
                    "A research run ID is required.",
                )
        self.manager.get.assert_not_called()

    def test_evidence_list_reports_unavailable_persistence(self) -> None:
        service = ResearchOverviewApplicationService(
            self.composer,
            None,
            None,
            None,
        )
        request = BrainRequest(
            "list evidence",
            metadata={"research_run_id": "run-1"},
        )
        self.composer.research_evidence_list_failure.return_value = self.response

        result = service.process_evidence_list(request)

        self.assertIs(result, self.response)
        self.composer.research_evidence_list_failure.assert_called_once_with(
            request,
            "Research run persistence is unavailable.",
        )

    def test_evidence_list_reports_missing_run(self) -> None:
        request = BrainRequest(
            "list evidence",
            metadata={"research_run_id": "run-1"},
        )
        self.manager.get.side_effect = ResearchError("missing")
        self.composer.research_evidence_list_failure.return_value = self.response

        result = self.service.process_evidence_list(request)

        self.assertIs(result, self.response)
        self.manager.get.assert_called_once_with("run-1")
        self.composer.research_evidence_list_failure.assert_called_once_with(
            request,
            "Research run was not found.",
        )

    def test_evidence_list_composes_the_exact_run(self) -> None:
        request = BrainRequest(
            "list evidence",
            metadata={"research_run_id": "  run-1  "},
        )
        run = Mock()
        self.manager.get.return_value = run
        self.composer.research_evidence_list_success.return_value = self.response

        result = self.service.process_evidence_list(request)

        self.assertIs(result, self.response)
        self.manager.get.assert_called_once_with("  run-1  ")
        self.composer.research_evidence_list_success.assert_called_once_with(
            request, run
        )

    def test_restoration_status_uses_captured_status_or_safe_unavailable(self) -> None:
        request = BrainRequest("status")
        status = ResearchSourceContentRestorationStatus(True, 2, 7)
        service = ResearchOverviewApplicationService(
            self.composer,
            self.manager,
            status,
            self.auditor,
        )
        self.composer.research_source_content_restoration_status.return_value = (
            self.response
        )

        result = service.process_source_content_restoration_status(request)

        self.assertIs(result, self.response)
        self.composer.research_source_content_restoration_status.assert_called_once_with(
            request,
            status,
        )
        self.manager.assert_not_called()
        self.auditor.assert_not_called()

        self.composer.reset_mock()
        unavailable_service = ResearchOverviewApplicationService(
            self.composer,
            self.manager,
            None,
            self.auditor,
        )
        unavailable_service.process_source_content_restoration_status(request)
        supplied = (
            self.composer.research_source_content_restoration_status.call_args.args[1]
        )
        self.assertEqual(supplied, ResearchSourceContentRestorationStatus.unavailable())

    def test_integrity_status_audits_the_exact_manager_snapshot(self) -> None:
        request = BrainRequest("status")
        runs = [Mock()]
        status = ResearchEvidenceIntegrityStatus(True, 1, 1, 0, 0)
        self.manager.list.return_value = runs
        self.auditor.audit.return_value = status
        self.composer.research_evidence_integrity_status.return_value = self.response

        result = self.service.process_evidence_integrity_status(request)

        self.assertIs(result, self.response)
        self.auditor.audit.assert_called_once_with(runs)
        self.composer.research_evidence_integrity_status.assert_called_once_with(
            request,
            status,
        )

    def test_integrity_status_degrades_to_unavailable_on_missing_dependencies(
        self,
    ) -> None:
        request = BrainRequest("status")
        service = ResearchOverviewApplicationService(
            self.composer,
            None,
            None,
            None,
        )
        self.composer.research_evidence_integrity_status.return_value = self.response

        result = service.process_evidence_integrity_status(request)

        self.assertIs(result, self.response)
        supplied = self.composer.research_evidence_integrity_status.call_args.args[1]
        self.assertEqual(supplied, ResearchEvidenceIntegrityStatus.unavailable())

    def test_integrity_status_degrades_to_unavailable_on_research_errors(self) -> None:
        request = BrainRequest("status")
        self.composer.research_evidence_integrity_status.return_value = self.response
        for failure_source in ("manager", "auditor"):
            with self.subTest(failure_source=failure_source):
                self.manager.reset_mock()
                self.auditor.reset_mock()
                self.composer.reset_mock()
                self.composer.research_evidence_integrity_status.return_value = (
                    self.response
                )
                self.manager.list.side_effect = None
                self.auditor.audit.side_effect = None
                self.manager.list.return_value = []
                if failure_source == "manager":
                    self.manager.list.side_effect = ResearchError("unavailable")
                else:
                    self.auditor.audit.side_effect = ResearchError("unavailable")

                result = self.service.process_evidence_integrity_status(request)

                self.assertIs(result, self.response)
                supplied = (
                    self.composer.research_evidence_integrity_status.call_args.args[1]
                )
                self.assertEqual(
                    supplied,
                    ResearchEvidenceIntegrityStatus.unavailable(),
                )


if __name__ == "__main__":
    unittest.main()
