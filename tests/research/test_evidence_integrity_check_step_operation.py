from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from research.EvidenceIntegrityCheckStepOperation import (
    EvidenceIntegrityCheckStepOperation,
)
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchEvidenceIntegrityAuditor import (
    ResearchEvidenceIntegrityAuditor,
)
from research.ResearchEvidenceIntegrityStatus import (
    ResearchEvidenceIntegrityStatus,
)
from research.ResearchPlanExecutionContext import ResearchPlanExecutionContext
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSource import ResearchSource

TRUTH_BOUNDARY = "does not establish truth"


class StubAuditor:
    """Return a caller-supplied status and record every audited run."""

    def __init__(self, status: ResearchEvidenceIntegrityStatus) -> None:
        self.status = status
        self.audited: list[list[str]] = []

    def audit(self, runs) -> ResearchEvidenceIntegrityStatus:  # type: ignore[no-untyped-def]
        self.audited.append([run.run_id for run in runs])
        return self.status


class EvidenceIntegrityCheckStepOperationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        document = root / "knowledge.md"
        document.write_text("Saturn\n\nSaturn has rings.", encoding="utf-8")
        self.event_bus = EventBus()
        self.knowledge_engine = KnowledgeEngine()
        self.knowledge_engine.load(document)
        self.manager = ResearchRunManager(JsonFileResearchRunStore(root / "runs.json"))
        self.auditor = ResearchEvidenceIntegrityAuditor(self.knowledge_engine)
        self.operation = EvidenceIntegrityCheckStepOperation(
            self.auditor,
            self.manager,
        )
        self.step = ResearchPlanStep(step_id="step-1", instruction="Check evidence")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _run_id(self) -> str:
        return self.manager.create("What evidence supports the claim?").run_id

    def test_operation_name_is_stable(self) -> None:
        self.assertEqual(self.operation.operation_name, "evidence_integrity_check")

    def test_zero_evidence_records_still_complete_the_audit(self) -> None:
        run_id = self._run_id()

        result = self.operation.run(
            self.step,
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        self.assertTrue(result.performed)
        self.assertIn("Evidence integrity audit ran", result.detail)
        self.assertIn("No evidence records were available to inspect", result.detail)
        self.assertIn(TRUTH_BOUNDARY, result.detail)

    def test_recorded_evidence_reports_reconciliation_counts(self) -> None:
        run_id = self._run_id()
        chunk = self.knowledge_engine.chunks()[0]
        self.manager.add_source(
            run_id,
            ResearchSource(
                url="https://example.test/a",
                title="A source",
                content="Saturn has rings.",
                content_type="text/html",
                fetched_at=datetime(2026, 8, 23, tzinfo=UTC),
            ),
            chunk.document_id,
        )
        self.manager.add_evidence(run_id, chunk, "Supports the ring claim.")

        result = self.operation.run(
            self.step,
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        self.assertTrue(result.performed)
        self.assertIn("1 record(s)", result.detail)
        self.assertIn("matched", result.detail)
        self.assertIn("missing", result.detail)
        self.assertIn("changed", result.detail)
        self.assertIn(TRUTH_BOUNDARY, result.detail)

    def test_audits_only_the_bound_run(self) -> None:
        first = self._run_id()
        self._run_id()
        auditor = StubAuditor(ResearchEvidenceIntegrityStatus(True, 0, 0, 0, 0))
        operation = EvidenceIntegrityCheckStepOperation(auditor, self.manager)

        operation.run(
            self.step,
            ResearchPlanExecutionContext(research_run_id=first),
        )

        self.assertEqual(auditor.audited, [[first]])

    def test_unavailable_audit_is_reported_without_counts(self) -> None:
        run_id = self._run_id()
        auditor = StubAuditor(ResearchEvidenceIntegrityStatus.unavailable())
        operation = EvidenceIntegrityCheckStepOperation(auditor, self.manager)

        result = operation.run(
            self.step,
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        self.assertTrue(result.performed)
        self.assertIn("reported state 'unavailable'", result.detail)
        self.assertIn("no counts could be produced", result.detail)
        self.assertIn(TRUTH_BOUNDARY, result.detail)

    def test_unknown_run_fails_safely(self) -> None:
        with self.assertRaises(ResearchError):
            self.operation.run(
                self.step,
                ResearchPlanExecutionContext(research_run_id="missing-run"),
            )

    def test_missing_run_binding_fails_safely(self) -> None:
        with self.assertRaises(ResearchError):
            self.operation.run(self.step, ResearchPlanExecutionContext())

    def test_check_performs_no_mutation(self) -> None:
        run_id = self._run_id()
        before = self.manager.get(run_id)
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))

        self.operation.run(
            self.step,
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        self.assertEqual(events, [])
        self.assertEqual(self.manager.get(run_id), before)

    def test_detail_stays_bounded(self) -> None:
        run_id = self._run_id()

        result = self.operation.run(
            self.step,
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        self.assertLessEqual(len(result.detail), 500)

    def test_result_is_deterministic_across_repeated_runs(self) -> None:
        run_id = self._run_id()
        context = ResearchPlanExecutionContext(research_run_id=run_id)

        first = self.operation.run(self.step, context)
        second = self.operation.run(self.step, context)

        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
