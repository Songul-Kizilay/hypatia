"""Pure contracts for explainable failure-lesson links in authored plans."""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from research.FailureLessonKind import FailureLessonKind
from research.ResearchFailureLesson import ResearchFailureLesson
from research.ResearchPlan import ResearchPlan
from research.ResearchPlanFailureLessonTrace import (
    ResearchPlanFailureLessonTracer,
)
from research.ResearchPlanStep import ResearchPlanStep

RECORDED = datetime(2026, 8, 21, 18, 0, tzinfo=UTC)


def lesson(
    lesson_id: str,
    statement: str,
    context: str,
) -> ResearchFailureLesson:
    return ResearchFailureLesson(
        lesson_id=lesson_id,
        kind=FailureLessonKind.FAILED_HYPOTHESIS,
        run_id="run-old",
        subject_id=lesson_id,
        statement=statement,
        provenance=("hypothesis-1", "evidence-4"),
        context=context,
        recorded_at=RECORDED,
    )


class ResearchPlanFailureLessonTracerTests(unittest.TestCase):
    def test_function_words_do_not_forge_a_step_reference(self) -> None:
        plan = ResearchPlan(
            "plan-1",
            "Compiler optimization",
            (ResearchPlanStep("step-1", "Which compiler does optimize Rust?"),),
            datetime(2026, 8, 22, 18, 0, tzinfo=UTC),
        )
        remembered = lesson(
            "lesson-1", "Saturn rings failed.", "Which observation does help?"
        )

        trace = ResearchPlanFailureLessonTracer().trace(plan, (remembered,))

        self.assertEqual(trace.references, ())
        self.assertEqual(trace.unreferenced_lesson_ids, ("lesson-1",))

    def test_reports_exact_shared_terms_in_lesson_and_step_order(self) -> None:
        plan = ResearchPlan(
            "plan-1",
            "Which observation would settle the ring-age debate?",
            (
                ResearchPlanStep(
                    "step-1",
                    "Review opposing ring-age evidence.",
                ),
                ResearchPlanStep(
                    "step-2",
                    "Compare ring-age observations with the hypothesis.",
                ),
            ),
            datetime(2026, 8, 22, 18, 0, tzinfo=UTC),
        )
        first = lesson(
            "lesson-1",
            "The ring-age hypothesis lacked opposing evidence.",
            "Which observation would change the ring-age hypothesis?",
        )
        second = lesson(
            "lesson-2",
            "A provider operation failed before candidate review.",
            "Find CVE records.",
        )

        trace = ResearchPlanFailureLessonTracer().trace(plan, (first, second))

        self.assertEqual(trace.plan_id, "plan-1")
        self.assertEqual(trace.lesson_ids, ("lesson-1", "lesson-2"))
        self.assertEqual(
            tuple(
                (reference.lesson_id, reference.step_id, reference.shared_terms)
                for reference in trace.references
            ),
            (
                ("lesson-1", "step-1", ("evidence", "opposing", "ring-age")),
                (
                    "lesson-1",
                    "step-2",
                    ("hypothesis", "ring-age"),
                ),
            ),
        )
        self.assertEqual(trace.unreferenced_lesson_ids, ("lesson-2",))

    def test_one_generic_shared_word_is_not_presented_as_a_reference(self) -> None:
        plan = ResearchPlan(
            "plan-1",
            "Question mentioning evidence.",
            (ResearchPlanStep("step-1", "Review evidence quality."),),
            datetime(2026, 8, 22, 18, 0, tzinfo=UTC),
        )
        remembered = lesson(
            "lesson-1",
            "Opposing evidence was missing.",
            "Saturn ring-age hypothesis.",
        )

        trace = ResearchPlanFailureLessonTracer().trace(plan, (remembered,))

        self.assertEqual(trace.references, ())
        self.assertEqual(trace.unreferenced_lesson_ids, ("lesson-1",))

    def test_matching_question_alone_does_not_forge_a_step_reference(self) -> None:
        plan = ResearchPlan(
            "plan-1",
            "Which observation would change the ring-age hypothesis?",
            (ResearchPlanStep("step-1", "Review the available material."),),
            datetime(2026, 8, 22, 18, 0, tzinfo=UTC),
        )
        remembered = lesson(
            "lesson-1",
            "The ring-age hypothesis lacked opposing evidence.",
            "Which observation would change the ring-age hypothesis?",
        )

        trace = ResearchPlanFailureLessonTracer().trace(plan, (remembered,))

        self.assertEqual(trace.references, ())
        self.assertEqual(trace.unreferenced_lesson_ids, ("lesson-1",))


if __name__ == "__main__":
    unittest.main()
