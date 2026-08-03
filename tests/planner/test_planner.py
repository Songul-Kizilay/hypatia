"""Unit tests for the deterministic Planner."""

from __future__ import annotations

import sys
from pathlib import Path
import unittest


SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from planner.Goal import Goal
from planner.Planner import Planner


class PlannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.planner = Planner()

    def test_goal_is_created_from_description(self) -> None:
        goal = Goal("  Read a PDF and summarize it  ")

        self.assertEqual(goal.description, "Read a PDF and summarize it")

    def test_pdf_summary_goal_creates_five_tasks(self) -> None:
        plan = self.planner.create_plan("Read a PDF and summarize it")

        self.assertEqual(plan.task_count(), 5)
        self.assertEqual(plan.tasks[0].title, "Locate file")
        self.assertEqual(plan.tasks[-1].title, "Return response")


if __name__ == "__main__":
    unittest.main()
