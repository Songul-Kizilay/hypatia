"""Contracts for bounded inert user-authored Research plans."""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

from core.Exceptions import ResearchError
from research.ResearchPlan import (
    MAX_RESEARCH_PLAN_ID_CHARACTERS,
    MAX_RESEARCH_PLAN_QUESTION_CHARACTERS,
    MAX_RESEARCH_PLAN_STEPS,
    ResearchPlan,
)
from research.ResearchPlanStep import (
    MAX_RESEARCH_PLAN_SOURCE_DOCUMENT_ID_CHARACTERS,
    MAX_RESEARCH_PLAN_STEP_ID_CHARACTERS,
    MAX_RESEARCH_PLAN_STEP_INSTRUCTION_CHARACTERS,
    MAX_RESEARCH_PLAN_STEP_SELECTED_SOURCES,
    ResearchPlanStep,
)


class ResearchPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 22, 16, 0, tzinfo=UTC)
        self.first_step = ResearchPlanStep(
            " step-1 ",
            "  Review the selected local sources.  ",
            (" document-2 ", "document-1"),
        )
        self.second_step = ResearchPlanStep(
            "step-2",
            "Record evidence gaps.",
            ("document-1", "document-3"),
        )

    def test_step_normalizes_authored_text_and_preserves_source_order(self) -> None:
        self.assertEqual(self.first_step.step_id, "step-1")
        self.assertEqual(
            self.first_step.instruction,
            "Review the selected local sources.",
        )
        self.assertEqual(
            self.first_step.selected_source_document_ids,
            ("document-2", "document-1"),
        )

    def test_step_accepts_explicitly_empty_source_selection(self) -> None:
        step = ResearchPlanStep("step-1", "Refine the question.")

        self.assertEqual(step.selected_source_document_ids, ())

    def test_step_rejects_empty_or_overlong_authored_fields(self) -> None:
        invalid_values: tuple[tuple[object, object, str], ...] = (
            (
                "",
                "Instruction.",
                "step ID cannot be empty",
            ),
            (
                7,
                "Instruction.",
                "step ID cannot be empty",
            ),
            (
                "step-1",
                "   ",
                "step instruction cannot be empty",
            ),
            (
                "x" * (MAX_RESEARCH_PLAN_STEP_ID_CHARACTERS + 1),
                "Instruction.",
                "step ID is too long",
            ),
            (
                "step-1",
                "x" * (MAX_RESEARCH_PLAN_STEP_INSTRUCTION_CHARACTERS + 1),
                "step instruction is too long",
            ),
        )
        for step_id, instruction, message in invalid_values:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ResearchError, message):
                    ResearchPlanStep(
                        step_id,  # type: ignore[arg-type]
                        instruction,  # type: ignore[arg-type]
                    )

    def test_step_requires_bounded_unique_immutable_source_selection(self) -> None:
        invalid_sources: tuple[object, ...] = (
            ["document-1"],
            ("",),
            (7,),
            ("x" * (MAX_RESEARCH_PLAN_SOURCE_DOCUMENT_ID_CHARACTERS + 1),),
            ("document-1", " document-1 "),
            tuple(
                f"document-{index}"
                for index in range(MAX_RESEARCH_PLAN_STEP_SELECTED_SOURCES + 1)
            ),
        )
        for source_ids in invalid_sources:
            with self.subTest(source_ids=source_ids):
                with self.assertRaises(ResearchError):
                    ResearchPlanStep(
                        "step-1",
                        "Instruction.",
                        source_ids,  # type: ignore[arg-type]
                    )

    def test_plan_preserves_step_order_and_first_selected_source_order(self) -> None:
        plan = ResearchPlan(
            " plan-1 ",
            "  Compare the accepted findings.  ",
            (self.first_step, self.second_step),
            self.now,
        )

        self.assertEqual(plan.plan_id, "plan-1")
        self.assertEqual(plan.question, "Compare the accepted findings.")
        self.assertEqual(plan.steps, (self.first_step, self.second_step))
        self.assertEqual(
            plan.selected_source_document_ids,
            ("document-2", "document-1", "document-3"),
        )

    def test_plan_and_steps_are_immutable(self) -> None:
        plan = ResearchPlan(
            "plan-1",
            "Question?",
            (self.first_step,),
            self.now,
        )

        with self.assertRaises(FrozenInstanceError):
            plan.question = "Changed"  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            self.first_step.instruction = "Changed"  # type: ignore[misc]

    def test_plan_rejects_empty_or_overlong_identity_and_question(self) -> None:
        invalid_values: tuple[tuple[object, object, str], ...] = (
            ("", "Question?", "plan ID cannot be empty"),
            (7, "Question?", "plan ID cannot be empty"),
            ("plan-1", "", "plan question cannot be empty"),
            (
                "x" * (MAX_RESEARCH_PLAN_ID_CHARACTERS + 1),
                "Question?",
                "plan ID is too long",
            ),
            (
                "plan-1",
                "x" * (MAX_RESEARCH_PLAN_QUESTION_CHARACTERS + 1),
                "plan question is too long",
            ),
        )
        for plan_id, question, message in invalid_values:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ResearchError, message):
                    ResearchPlan(
                        plan_id,  # type: ignore[arg-type]
                        question,  # type: ignore[arg-type]
                        (self.first_step,),
                        self.now,
                    )

    def test_plan_requires_bounded_valid_unique_immutable_steps(self) -> None:
        too_many_steps = tuple(
            ResearchPlanStep(f"step-{index}", "Instruction.")
            for index in range(MAX_RESEARCH_PLAN_STEPS + 1)
        )
        invalid_steps: tuple[object, ...] = (
            [],
            (),
            ("step-1",),
            (self.first_step, ResearchPlanStep(" step-1 ", "Other.")),
            too_many_steps,
        )
        for steps in invalid_steps:
            with self.subTest(steps=steps):
                with self.assertRaises(ResearchError):
                    ResearchPlan(
                        "plan-1",
                        "Question?",
                        steps,  # type: ignore[arg-type]
                        self.now,
                    )

    def test_plan_requires_timezone_aware_creation_time(self) -> None:
        invalid_times: tuple[object, ...] = (
            "2026-08-22T16:00:00Z",
            datetime(2026, 8, 22, 16, 0),
        )
        for created_at in invalid_times:
            with self.subTest(created_at=created_at):
                with self.assertRaisesRegex(ResearchError, "timezone-aware"):
                    ResearchPlan(
                        "plan-1",
                        "Question?",
                        (self.first_step,),
                        created_at,  # type: ignore[arg-type]
                    )


if __name__ == "__main__":
    unittest.main()
