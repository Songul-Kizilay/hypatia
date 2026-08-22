"""Response contracts for inert user-authored Research plan drafts."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from brain.BrainRequest import BrainRequest
from research.ResearchPlan import ResearchPlan
from research.ResearchPlanDraftPreview import ResearchPlanDraftPreview
from research.ResearchPlanStep import ResearchPlanStep
from response.ResponseComposer import ResponseComposer


class ResearchPlanDraftResponseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.composer = ResponseComposer()
        self.request = BrainRequest(
            "Preview my research plan",
            request_id="request-1",
        )

    def test_ready_preview_renders_exact_authored_steps_without_side_effect_claims(
        self,
    ) -> None:
        plan = ResearchPlan(
            "plan-1",
            "Compare the accepted findings.",
            (
                ResearchPlanStep(
                    "step-1",
                    "Review accepted sources.",
                    ("document-2", "document-1"),
                ),
                ResearchPlanStep("step-2", "Record evidence gaps."),
            ),
            datetime(2026, 8, 22, 18, 0, tzinfo=UTC),
        )
        preview = ResearchPlanDraftPreview.ready(plan)

        response = self.composer.research_plan_draft_preview(
            self.request,
            preview,
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "research_plan_draft_preview")
        self.assertEqual(response.request_id, "request-1")
        self.assertEqual(response.memory_count, 0)
        self.assertIs(response.research_plan_draft_preview, preview)
        self.assertEqual(
            response.message,
            "Research plan draft preview:\n"
            "Question: Compare the accepted findings.\n"
            "Steps: 2\n"
            "Selected sources: 2\n"
            "1. Review accepted sources.\n"
            "   Selected sources: document-2, document-1\n"
            "2. Record evidence gaps.\n"
            "   Selected sources: none\n"
            "Plan ID: plan-1\n"
            "Status: ready for explicit confirmation\n"
            "Persistent writes: not used\n"
            "Execution: not started",
        )

    def test_rejected_preview_renders_only_the_bounded_reason(self) -> None:
        preview = ResearchPlanDraftPreview.rejected(
            "Research plan question cannot be empty."
        )

        response = self.composer.research_plan_draft_preview(
            self.request,
            preview,
        )

        self.assertFalse(response.success)
        self.assertEqual(response.intent, "research_plan_draft_preview")
        self.assertIs(response.research_plan_draft_preview, preview)
        self.assertEqual(
            response.message,
            "Research plan draft rejected:\n"
            "Reason: Research plan question cannot be empty.\n"
            "Persistent writes: not used\n"
            "Execution: not started",
        )


if __name__ == "__main__":
    unittest.main()
