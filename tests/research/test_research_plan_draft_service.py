"""No-write application contracts for explicit Research plan drafts."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from core.Exceptions import ResearchError
from research.ResearchPlan import MAX_RESEARCH_PLAN_STEPS, ResearchPlan
from research.ResearchPlanDraftPreview import (
    MAX_RESEARCH_PLAN_DRAFT_REASON_CHARACTERS,
    ResearchPlanDraftPreview,
)
from research.ResearchPlanDraftService import ResearchPlanDraftService
from research.ResearchPlanStep import (
    MAX_RESEARCH_PLAN_STEP_INSTRUCTION_CHARACTERS,
    MAX_RESEARCH_PLAN_STEP_SELECTED_SOURCES,
    ResearchPlanStep,
)


class ResearchPlanDraftServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 22, 17, 0, tzinfo=UTC)
        self.service = ResearchPlanDraftService(
            clock=lambda: self.now,
            id_factory=lambda: " plan-1 ",
        )

    def test_preview_builds_one_inert_normalized_plan_in_explicit_order(self) -> None:
        drafts = (
            (
                "  Review the accepted sources.  ",
                (" document-2 ", "document-1"),
            ),
            ("Record evidence gaps.", ()),
        )

        preview = self.service.preview("  Compare the findings.  ", drafts)

        self.assertTrue(preview.allowed)
        self.assertEqual(
            preview.reason,
            "Research plan draft is ready for explicit confirmation.",
        )
        self.assertIsInstance(preview.plan, ResearchPlan)
        assert preview.plan is not None
        self.assertEqual(preview.plan.plan_id, "plan-1")
        self.assertEqual(preview.plan.question, "Compare the findings.")
        self.assertEqual(preview.plan.created_at, self.now)
        self.assertEqual(
            tuple(step.step_id for step in preview.plan.steps),
            ("step-1", "step-2"),
        )
        self.assertEqual(
            tuple(step.instruction for step in preview.plan.steps),
            ("Review the accepted sources.", "Record evidence gaps."),
        )
        self.assertEqual(
            preview.plan.steps[0].selected_source_document_ids,
            ("document-2", "document-1"),
        )
        self.assertEqual(preview.plan.steps[1].selected_source_document_ids, ())
        self.assertEqual(
            preview.plan.selected_source_document_ids,
            ("document-2", "document-1"),
        )
        self.assertEqual(
            drafts,
            (
                (
                    "  Review the accepted sources.  ",
                    (" document-2 ", "document-1"),
                ),
                ("Record evidence gaps.", ()),
            ),
        )

    def test_preview_returns_bounded_question_failures_without_partial_plan(
        self,
    ) -> None:
        invalid_questions: tuple[object, ...] = (
            None,
            7,
            "",
            "   ",
            "x" * 2_001,
        )
        for question in invalid_questions:
            with self.subTest(question_type=type(question).__name__):
                preview = self.service.preview(
                    question,  # type: ignore[arg-type]
                    (("Review.", ()),),
                )

                self.assertFalse(preview.allowed)
                self.assertIsNone(preview.plan)
                self.assertTrue(preview.reason.startswith("Research plan question"))

    def test_preview_returns_bounded_structural_step_failures(self) -> None:
        invalid_drafts: tuple[object, ...] = (
            [],
            (),
            ("Review.",),
            (("Review.",),),
            (("Review.", (), "extra"),),
        )
        for drafts in invalid_drafts:
            with self.subTest(drafts=drafts):
                preview = self.service.preview(
                    "Question?",
                    drafts,  # type: ignore[arg-type]
                )

                self.assertFalse(preview.allowed)
                self.assertIsNone(preview.plan)
                self.assertTrue(preview.reason)

    def test_preview_returns_bounded_step_domain_failures(self) -> None:
        invalid_drafts: tuple[object, ...] = (
            (("", ()),),
            ((7, ()),),
            (("x" * (MAX_RESEARCH_PLAN_STEP_INSTRUCTION_CHARACTERS + 1), ()),),
            (("Review.", ["document-1"]),),
            (("Review.", ("document-1", " document-1 ")),),
            (
                (
                    "Review.",
                    tuple(
                        f"document-{index}"
                        for index in range(MAX_RESEARCH_PLAN_STEP_SELECTED_SOURCES + 1)
                    ),
                ),
            ),
            tuple(
                (f"Step {index}.", ()) for index in range(MAX_RESEARCH_PLAN_STEPS + 1)
            ),
        )
        for drafts in invalid_drafts:
            with self.subTest(drafts=type(drafts).__name__):
                preview = self.service.preview(
                    "Question?",
                    drafts,  # type: ignore[arg-type]
                )

                self.assertFalse(preview.allowed)
                self.assertIsNone(preview.plan)
                self.assertTrue(preview.reason)

    def test_preview_rejects_invalid_generated_identity_or_time(self) -> None:
        services = (
            ResearchPlanDraftService(
                clock=lambda: self.now,
                id_factory=lambda: "",
            ),
            ResearchPlanDraftService(
                clock=lambda: datetime(2026, 8, 22, 17, 0),
                id_factory=lambda: "plan-1",
            ),
        )
        for service in services:
            with self.subTest(service=service):
                preview = service.preview("Question?", (("Review.", ()),))

                self.assertFalse(preview.allowed)
                self.assertIsNone(preview.plan)
                self.assertTrue(preview.reason)


class ResearchPlanDraftPreviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = ResearchPlan(
            "plan-1",
            "Question?",
            (ResearchPlanStep("step-1", "Review."),),
            datetime(2026, 8, 22, 17, 0, tzinfo=UTC),
        )

    def test_ready_and_rejected_factories_preserve_exclusive_results(self) -> None:
        ready = ResearchPlanDraftPreview.ready(self.plan)
        rejected = ResearchPlanDraftPreview.rejected("  Invalid draft.  ")

        self.assertTrue(ready.allowed)
        self.assertIs(ready.plan, self.plan)
        self.assertFalse(rejected.allowed)
        self.assertIsNone(rejected.plan)
        self.assertEqual(rejected.reason, "Invalid draft.")

    def test_preview_rejects_inconsistent_decision_and_plan_pairs(self) -> None:
        invalid_values = (
            (True, "Ready.", None),
            (False, "Rejected.", self.plan),
            ("yes", "Ready.", self.plan),
        )
        for allowed, reason, plan in invalid_values:
            with self.subTest(allowed=allowed):
                with self.assertRaises(ResearchError):
                    ResearchPlanDraftPreview(
                        allowed,  # type: ignore[arg-type]
                        reason,
                        plan,
                    )

    def test_preview_requires_one_bounded_reason(self) -> None:
        for reason in (None, 7, "", "   "):
            with self.subTest(reason=reason):
                with self.assertRaisesRegex(ResearchError, "reason cannot be empty"):
                    ResearchPlanDraftPreview(
                        False,
                        reason,  # type: ignore[arg-type]
                        None,
                    )
        with self.assertRaisesRegex(ResearchError, "reason is too long"):
            ResearchPlanDraftPreview.rejected(
                "x" * (MAX_RESEARCH_PLAN_DRAFT_REASON_CHARACTERS + 1)
            )


if __name__ == "__main__":
    unittest.main()
