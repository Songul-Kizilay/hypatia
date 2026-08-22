from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError
from knowledge.KnowledgeEngine import KnowledgeEngine
from research.LocalKnowledgeSearchStepOperation import (
    LocalKnowledgeSearchStepOperation,
)
from research.ResearchPlanExecutionContext import ResearchPlanExecutionContext
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepOperationResult import (
    ResearchPlanStepOperationResult,
)


class LocalKnowledgeSearchStepOperationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        document = root / "saturn.md"
        document.write_text(
            "Saturn rings\n\nSaturn has a prominent ring system.",
            encoding="utf-8",
        )
        self.knowledge_engine = KnowledgeEngine()
        self.knowledge_engine.load(document)
        self.operation = LocalKnowledgeSearchStepOperation(self.knowledge_engine)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_operation_name_is_stable(self) -> None:
        self.assertEqual(self.operation.operation_name, "local_knowledge_search")

    def test_matching_instruction_reports_real_findings(self) -> None:
        result = self.operation.run(
            ResearchPlanStep(step_id="step-1", instruction="Saturn"),
            ResearchPlanExecutionContext(),
        )

        self.assertTrue(result.performed)
        self.assertIn("Local knowledge search matched", result.detail)
        self.assertIn("Documents:", result.detail)

    def test_zero_results_still_report_the_search_honestly(self) -> None:
        result = self.operation.run(
            ResearchPlanStep(
                step_id="step-1",
                instruction="quantum chromodynamics lattice",
            ),
            ResearchPlanExecutionContext(),
        )

        self.assertTrue(result.performed)
        self.assertIn("matched 0 chunk(s)", result.detail)
        self.assertIn("No local knowledge matched this instruction.", result.detail)

    def test_detail_stays_bounded(self) -> None:
        result = self.operation.run(
            ResearchPlanStep(step_id="step-1", instruction="Saturn"),
            ResearchPlanExecutionContext(),
        )

        self.assertLessEqual(len(result.detail), 500)


class ResearchPlanStepOperationResultTests(unittest.TestCase):
    def test_rejects_invalid_values(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchPlanStepOperationResult(performed=True, detail="   ")
        with self.assertRaises(ResearchError):
            ResearchPlanStepOperationResult(performed="yes", detail="ok")  # type: ignore[arg-type]
        with self.assertRaises(ResearchError):
            ResearchPlanStepOperationResult(performed=True, detail="x" * 501)

    def test_normalizes_detail(self) -> None:
        result = ResearchPlanStepOperationResult(performed=False, detail="  none  ")

        self.assertEqual(result.detail, "none")
        self.assertFalse(result.performed)


if __name__ == "__main__":
    unittest.main()
