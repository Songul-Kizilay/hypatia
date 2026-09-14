"""A constraint is approved, displayed, and never executed.

Binding a constraint into the plan's identity is only half the point. The other
half is that it must stay out of everything that does work: the execution model
must not see it, no budget may be spent on it, no provider may be reached
through it, and the v0.3.284 failure-lesson trace must keep pointing at real
steps rather than treating a constraint as one more numbered instruction.

The preview also has to show it. A constraint the operator approves but cannot
read back is a hidden term, so it is rendered in its own section with its own
numbering — never as "step 11".

Real execution service, real preview composition, deterministic fakes. No
network, no model, no writes.
"""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from brain.BrainRequest import BrainRequest
from cognition.ResearchPlanPreviewApplicationService import (
    ResearchPlanPreviewApplicationService,
)
from research.FailureLessonKind import FailureLessonKind
from research.ResearchFailureLesson import ResearchFailureLesson
from research.ResearchPlanFailureLessonTrace import ResearchPlanFailureLessonTracer
from response.ResponseComposer import ResponseComposer
from tests.research.test_plan_constraints import (
    SSRF_CONSTRAINT,
    SSRF_QUESTION,
    SSRF_STEPS,
    plan,
)

WINDOW_SOURCE = (SRC_DIR / "desktop" / "TkinterDesktopWindow.py").read_text(
    encoding="utf-8"
)
CONTROLLER_SOURCE = (SRC_DIR / "desktop" / "DesktopController.py").read_text(
    encoding="utf-8"
)
DRAFT_SOURCE = (SRC_DIR / "research" / "ResearchPlanDraftService.py").read_text(
    encoding="utf-8"
)
TRACE_SOURCE = (SRC_DIR / "research" / "ResearchPlanFailureLessonTrace.py").read_text(
    encoding="utf-8"
)

MOMENT = datetime(2026, 1, 1, tzinfo=UTC)


def preview_message(constraints: tuple[str, ...]) -> str:
    """Render one real preview through the real composer."""
    service = ResearchPlanPreviewApplicationService(ResponseComposer())
    request = BrainRequest(
        message="draft",
        metadata={
            "intent": "research_plan_draft_preview",
            "research_plan_question": SSRF_QUESTION,
            "research_plan_steps": tuple(
                (instruction, ()) for instruction in SSRF_STEPS
            ),
            "research_plan_constraints": constraints,
        },
    )
    return service.process_draft_preview(request).message


class ExecutionNeverSeesAConstraintTests(unittest.TestCase):
    """The execution model reads steps. Constraints are not in that list."""

    def test_execution_iterates_only_steps(self) -> None:
        constrained = plan("Review.", constraints=("Do not fetch.", "Use NVD only."))

        self.assertEqual(len(constrained.steps), 1)
        self.assertEqual(len(constrained.constraints), 2)

    def test_no_constraint_appears_among_step_instructions(self) -> None:
        constrained = plan(*SSRF_STEPS, constraints=(SSRF_CONSTRAINT,))

        self.assertNotIn(
            SSRF_CONSTRAINT,
            [step.instruction for step in constrained.steps],
        )

    def test_no_constraint_receives_a_step_identity(self) -> None:
        constrained = plan(*SSRF_STEPS, constraints=(SSRF_CONSTRAINT,))
        step_ids = {step.step_id for step in constrained.steps}

        self.assertEqual(len(step_ids), 10)
        self.assertNotIn("step-11", step_ids)

    def test_a_constrained_plan_starts_the_same_execution_as_a_bare_one(
        self,
    ) -> None:
        """Same steps in, same executable work out."""
        bare = plan(*SSRF_STEPS)
        constrained = plan(*SSRF_STEPS, constraints=(SSRF_CONSTRAINT,))

        self.assertEqual(
            [(step.step_id, step.instruction, step.capability) for step in bare.steps],
            [
                (step.step_id, step.instruction, step.capability)
                for step in constrained.steps
            ],
        )


class ThePreviewShowsThemSeparatelyTests(unittest.TestCase):
    def test_the_ssrf_case_reports_ten_steps_and_one_constraint(self) -> None:
        message = preview_message((SSRF_CONSTRAINT,))

        self.assertIn("Steps: 10", message)
        self.assertIn("Constraints: 1", message)

    def test_the_ssrf_case_no_longer_reports_eleven_steps(self) -> None:
        """The exact defect this milestone exists to remove."""
        message = preview_message((SSRF_CONSTRAINT,))

        self.assertNotIn("Steps: 11", message)

    def test_the_constraint_is_rendered_in_its_own_section(self) -> None:
        message = preview_message((SSRF_CONSTRAINT,))

        self.assertIn("Plan constraints:", message)
        self.assertIn(f"C1. {SSRF_CONSTRAINT}", message)

    def test_the_constraint_is_never_numbered_as_a_step(self) -> None:
        message = preview_message((SSRF_CONSTRAINT,))

        self.assertNotIn(f"11. {SSRF_CONSTRAINT}", message)

    def test_the_preview_says_constraints_are_not_executable(self) -> None:
        message = preview_message((SSRF_CONSTRAINT,))

        self.assertIn("not executable steps", message)
        self.assertIn("bound into", message)

    def test_a_step_only_preview_shows_no_constraint_section(self) -> None:
        message = preview_message(())

        self.assertIn("Constraints: 0", message)
        self.assertNotIn("Plan constraints:", message)

    def test_the_preview_still_promises_no_writes_or_execution(self) -> None:
        message = preview_message((SSRF_CONSTRAINT,))

        self.assertIn("Status: ready for explicit confirmation", message)
        self.assertIn("Persistent writes: not used", message)
        self.assertIn("Execution: not started", message)


class TheFailureTraceStillTargetsStepsTests(unittest.TestCase):
    """v0.3.284 behaviour, preserved exactly."""

    def _lesson(self, statement: str) -> ResearchFailureLesson:
        return ResearchFailureLesson(
            lesson_id="lesson-1",
            kind=FailureLessonKind.INVALID_ASSUMPTION,
            run_id="run-1",
            subject_id="subject-1",
            statement=statement,
            provenance=("run-1",),
            context="ssrf",
            recorded_at=MOMENT,
        )

    def test_a_constraint_is_never_traced_as_a_step(self) -> None:
        """A constraint sharing wording with a lesson must not become step-N."""
        lesson = self._lesson("Do not execute research or access external sources.")
        constrained = plan(
            "Compare allowlist approaches.", constraints=(SSRF_CONSTRAINT,)
        )

        trace = ResearchPlanFailureLessonTracer().trace(constrained, (lesson,))

        self.assertEqual(trace.references, ())

    def test_steps_are_still_traced_normally(self) -> None:
        lesson = self._lesson("Compare allowlist and denylist approaches carefully.")
        constrained = plan(
            "Compare allowlist and denylist approaches.",
            constraints=(SSRF_CONSTRAINT,),
        )

        trace = ResearchPlanFailureLessonTracer().trace(constrained, (lesson,))

        self.assertTrue(trace.references)
        self.assertEqual(trace.references[0].step_id, "step-1")

    def test_the_tracer_reads_only_steps(self) -> None:
        self.assertIn("for step in plan.steps:", TRACE_SOURCE)
        self.assertNotIn("constraint", TRACE_SOURCE.casefold())

    def test_the_two_token_threshold_is_unchanged(self) -> None:
        self.assertIn("MIN_STEP_SHARED_TOKENS = 2", TRACE_SOURCE)

    def test_unavailable_and_none_remain_distinct(self) -> None:
        composer = (SRC_DIR / "response" / "ResponseComposer.py").read_text("utf-8")

        self.assertIn("Authored-step wording overlap: unavailable", composer)
        self.assertIn("Authored-step wording overlap: none", composer)


class NothingClassifiesTheTextTests(unittest.TestCase):
    """The human decides which box a line goes in."""

    def test_the_draft_service_inspects_no_wording(self) -> None:
        start = DRAFT_SOURCE.index("    def _build_constraints(")
        body = DRAFT_SOURCE[
            start : DRAFT_SOURCE.index("\n    @staticmethod", start + 1)
        ]

        for forbidden in ("startswith", "lower()", "casefold", "in text", "keyword"):
            with self.subTest(name=forbidden):
                self.assertNotIn(forbidden, body)

    def test_no_model_is_consulted_anywhere_in_the_authoring_path(self) -> None:
        """Read the code that shapes constraints, not the prose around it.

        Two unrelated controller docstrings promise their work happens
        "without an LLM call", so a scan of whole files finds the word inside
        the very sentence ruling it out.
        """
        start = CONTROLLER_SOURCE.index("def _plan_constraint_drafts(")
        helper = CONTROLLER_SOURCE[start : CONTROLLER_SOURCE.index("\ndef ", start + 1)]
        start = DRAFT_SOURCE.index("    def _build_constraints(")
        builder = DRAFT_SOURCE[
            start : DRAFT_SOURCE.index("\n    @staticmethod", start + 1)
        ]

        for body in (helper, builder):
            for forbidden in ("ollama", "llm", "classify", "model"):
                with self.subTest(name=forbidden):
                    self.assertNotIn(forbidden, body.casefold())

    def test_the_desktop_sends_two_separate_fields(self) -> None:
        start = CONTROLLER_SOURCE.index("    def preview_research_plan_draft(")
        body = CONTROLLER_SOURCE[
            start : CONTROLLER_SOURCE.index("\n    def ", start + 1)
        ]

        self.assertIn('"research_plan_steps"', body)
        self.assertIn('"research_plan_constraints"', body)

    def test_the_window_offers_a_separate_constraints_box(self) -> None:
        self.assertIn("self._research_plan_constraints", WINDOW_SOURCE)
        self.assertIn("Plan constraints", WINDOW_SOURCE)

    def test_the_note_tells_the_operator_it_is_their_choice(self) -> None:
        from desktop.TkinterDesktopWindow import _PLAN_CONSTRAINT_NOTE

        note = _PLAN_CONSTRAINT_NOTE.casefold()

        self.assertIn("your choice", note)
        self.assertIn("never executed", note)
        self.assertIn("digest", note)


class NoUnrelatedSubsystemChangedTests(unittest.TestCase):
    def test_the_scheduler_and_deferred_grants_were_not_touched(self) -> None:
        for name in (
            "cognition/BackgroundResearchSchedulerApplicationService.py",
            "research/DeferredExecutionGrant.py",
            "research/DeferredExecutionEligibility.py",
        ):
            with self.subTest(name=name):
                source = (SRC_DIR / name).read_text(encoding="utf-8")

                self.assertNotIn("constraint", source.casefold())


class TheApprovalBindsTheConstraintsTests(unittest.TestCase):
    """A plan is approved with its constraints or not at all."""

    def _digest(self, constraints: tuple[str, ...]) -> str:
        from research.ResearchPlanDigest import plan_digest
        from research.ResearchPlanDraftService import ResearchPlanDraftService

        service = ResearchPlanDraftService(
            clock=lambda: MOMENT,
            id_factory=lambda: "plan-1",
        )
        preview = service.preview(
            SSRF_QUESTION,
            tuple((instruction, ()) for instruction in SSRF_STEPS),
            constraints,
        )
        assert preview.plan is not None
        return plan_digest(preview.plan)

    def test_rebuilding_with_the_same_constraints_gives_the_same_digest(self) -> None:
        self.assertEqual(
            self._digest((SSRF_CONSTRAINT,)),
            self._digest((SSRF_CONSTRAINT,)),
        )

    def test_changed_constraints_cannot_reuse_the_old_binding(self) -> None:
        """The stale-approval check does the work; it just needs the field."""
        approved = self._digest((SSRF_CONSTRAINT,))

        self.assertNotEqual(approved, self._digest(("You may access sources.",)))

    def test_dropping_the_constraints_cannot_reuse_the_binding(self) -> None:
        approved = self._digest((SSRF_CONSTRAINT,))

        self.assertNotEqual(approved, self._digest(()))

    def test_every_rebuild_site_reads_the_same_metadata_key(self) -> None:
        """A site that forgot it would approve a different plan than shown."""
        from research.ResearchPlanDraftService import RESEARCH_PLAN_CONSTRAINTS_KEY

        for name in (
            "cognition/ResearchPlanAuthorizationApplicationService.py",
            "cognition/ResearchPlanExecutionApplicationService.py",
        ):
            with self.subTest(name=name):
                source = (SRC_DIR / name).read_text(encoding="utf-8")

                self.assertIn("RESEARCH_PLAN_CONSTRAINTS_KEY", source)
        self.assertEqual(RESEARCH_PLAN_CONSTRAINTS_KEY, "research_plan_constraints")

    def test_the_desktop_sends_constraints_on_every_approval_path(self) -> None:
        for handler in (
            "_preview_plan_authorization",
            "_confirm_plan_authorization",
            "_start_authorized_execution",
        ):
            with self.subTest(name=handler):
                start = WINDOW_SOURCE.index(f"    def {handler}(self")
                body = WINDOW_SOURCE[
                    start : WINDOW_SOURCE.index("\n    def ", start + 1)
                ]

                self.assertIn("self._research_plan_constraints", body)


class TheDesktopShapesTheTwoFieldsSeparatelyTests(unittest.TestCase):
    """Line shaping happens in the controller, so it is checked there too.

    Testing only the draft service would miss the place a constraint line is
    most likely to be folded back into the step list: the surface that turns
    typed text into rows.
    """

    def _sent(self, instructions: str, sources: str, constraints: str) -> dict:
        from brain.BrainResponse import BrainResponse
        from desktop.DesktopController import DesktopController

        sent: list[BrainRequest] = []

        class Recorder:
            def process(self, request: BrainRequest) -> BrainResponse:
                sent.append(request)
                return BrainResponse("ok", "request-1", "test", 0)

        DesktopController(Recorder()).preview_research_plan_draft(
            SSRF_QUESTION, instructions, sources, constraints
        )
        [request] = sent
        return dict(request.metadata)

    def test_constraint_lines_never_become_step_rows(self) -> None:
        metadata = self._sent(
            "Review parsing.\nReview DNS.",
            "document-1\ndocument-2",
            "Do not fetch.\nUse NVD only.",
        )

        self.assertEqual(len(metadata["research_plan_steps"]), 2)

    def test_constraint_lines_are_sent_as_their_own_field(self) -> None:
        metadata = self._sent(
            "Review parsing.", "document-1", "Do not fetch.\nUse NVD only."
        )

        self.assertEqual(
            metadata["research_plan_constraints"], ("Do not fetch.", "Use NVD only.")
        )

    def test_sources_stay_on_their_own_steps_whatever_the_constraints(self) -> None:
        without = self._sent(
            "Review parsing.\nReview DNS.", "document-1\ndocument-2", ""
        )
        with_constraints = self._sent(
            "Review parsing.\nReview DNS.",
            "document-1\ndocument-2",
            "Do not fetch.\nUse NVD only.\nAnd another.",
        )

        self.assertEqual(
            without["research_plan_steps"], with_constraints["research_plan_steps"]
        )

    def test_blank_constraint_lines_are_dropped_not_sent(self) -> None:
        metadata = self._sent("Review.", "", "Do not fetch.\n\n   \nUse NVD only.")

        self.assertEqual(
            metadata["research_plan_constraints"], ("Do not fetch.", "Use NVD only.")
        )


if __name__ == "__main__":
    unittest.main()
