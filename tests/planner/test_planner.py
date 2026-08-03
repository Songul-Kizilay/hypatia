"""Unit tests for the deterministic Planner."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

# unittest imports this module as ``planner.test_planner`` because the test
# directory is a package. Extend that package's search path so imports below
# resolve implementation modules at ``src/planner`` as well.
loaded_planner = sys.modules.get("planner")
if loaded_planner is not None:
    source_planner_dir = str(SRC_DIR / "planner")
    if source_planner_dir not in loaded_planner.__path__:
        loaded_planner.__path__.append(source_planner_dir)

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
