from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError
from research.ResearchPlanStepState import ResearchPlanStepState
from research.ResearchPlanStepStatus import ResearchPlanStepStatus


class ResearchPlanStepStateTests(unittest.TestCase):
    def test_defaults_to_pending_without_detail(self) -> None:
        state = ResearchPlanStepState(step_id="  step-1  ")

        self.assertEqual(state.step_id, "step-1")
        self.assertIs(state.status, ResearchPlanStepStatus.PENDING)
        self.assertEqual(state.detail, "")

    def test_with_status_returns_a_new_value(self) -> None:
        state = ResearchPlanStepState(step_id="step-1")

        updated = state.with_status(ResearchPlanStepStatus.RUNNING, "  working  ")

        self.assertIs(state.status, ResearchPlanStepStatus.PENDING)
        self.assertIs(updated.status, ResearchPlanStepStatus.RUNNING)
        self.assertEqual(updated.detail, "working")
        self.assertEqual(updated.step_id, "step-1")

    def test_rejects_invalid_values(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchPlanStepState(step_id="   ")
        with self.assertRaises(ResearchError):
            ResearchPlanStepState(step_id="step-1", status="running")  # type: ignore[arg-type]
        with self.assertRaises(ResearchError):
            ResearchPlanStepState(step_id="step-1", detail=1)  # type: ignore[arg-type]
        with self.assertRaises(ResearchError):
            ResearchPlanStepState(step_id="step-1", detail="x" * 501)


if __name__ == "__main__":
    unittest.main()
