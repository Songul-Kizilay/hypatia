"""The two boundaries that must refuse a plan contradicting itself.

The real SSRF case, twice. A step that discovers literature through Crossref,
and a constraint saying not to touch external sources. Left advisory, that is a
note to the author and the plan is approvable exactly as before. Typed as a
restriction, the same plan is refused — not trimmed, not redirected to a local
search, not quietly given a different provider. Refused, and handed back saying
which step and which capability clash.

Approval is where it matters most, because a recorded approval is authority
that outlives the moment. Execution start asks the same question again, from
the same function, so a stale or internal path that somehow arrives with a
contradictory plan still stops before a provider is touched. Two copies of the
rule would be the actual danger, so there is one.

Deterministic fakes. No network, no model, no writes.
"""

from __future__ import annotations

import sys
import unittest
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
from research.ResearchPlanRestriction import ResearchPlanRestriction
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from response.ResponseComposer import ResponseComposer
from tests.research.test_plan_constraints import SSRF_CONSTRAINT, SSRF_QUESTION

AUTHORIZATION_SOURCE = (
    SRC_DIR / "cognition" / "ResearchPlanAuthorizationApplicationService.py"
).read_text(encoding="utf-8")
EXECUTION_SOURCE = (
    SRC_DIR / "cognition" / "ResearchPlanExecutionApplicationService.py"
).read_text(encoding="utf-8")
WINDOW_SOURCE = (SRC_DIR / "desktop" / "TkinterDesktopWindow.py").read_text(
    encoding="utf-8"
)

NO_EXTERNAL = ResearchPlanRestriction.NO_EXTERNAL_SOURCE_ACCESS

CROSSREF_STEP = (
    "Discover supporting literature through Crossref.",
    (),
    ResearchPlanStepCapability.SOURCE_DISCOVERY.value,
)
LOCAL_STEP = (
    "Search accepted local knowledge for SSRF defenses.",
    (),
    ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH.value,
)


def preview(step, restriction):
    """Render one real draft preview through the real composer."""
    service = ResearchPlanPreviewApplicationService(ResponseComposer())
    return service.process_draft_preview(
        BrainRequest(
            message="draft",
            metadata={
                "intent": "research_plan_draft_preview",
                "research_plan_question": SSRF_QUESTION,
                "research_plan_steps": (step,),
                "research_plan_constraints": (SSRF_CONSTRAINT,),
                "research_plan_restriction": restriction,
            },
        )
    )


class ThePreviewSaysWhichConstraintsBiteTests(unittest.TestCase):
    def test_an_advisory_constraint_says_so(self) -> None:
        message = preview(CROSSREF_STEP, None).message

        self.assertIn("Enforcement: advisory only", message)

    def test_a_typed_restriction_is_named(self) -> None:
        message = preview(CROSSREF_STEP, NO_EXTERNAL).message

        self.assertIn("Enforcement: no_external_source_access", message)

    def test_the_preview_says_advisory_text_blocks_nothing(self) -> None:
        message = preview(CROSSREF_STEP, None).message

        self.assertIn("advisory text blocks nothing on its own", message)

    def test_the_preview_still_writes_and_executes_nothing(self) -> None:
        message = preview(CROSSREF_STEP, NO_EXTERNAL).message

        self.assertIn("Persistent writes: not used", message)
        self.assertIn("Execution: not started", message)


class TheAuthorizationBoundaryRefusesTests(unittest.TestCase):
    """Case A stays approvable; case B is refused before anything is recorded."""

    def test_the_advisory_case_produces_a_valid_plan(self) -> None:
        from research.ResearchPlanRestrictionConflict import (
            plan_restriction_conflicts,
        )

        response = preview(CROSSREF_STEP, None)
        plan = response.research_plan_draft_preview.plan

        assert plan is not None
        self.assertEqual(plan_restriction_conflicts(plan), ())

    def test_the_typed_case_is_contradictory(self) -> None:
        from research.ResearchPlanRestrictionConflict import (
            plan_restriction_conflicts,
        )

        response = preview(CROSSREF_STEP, NO_EXTERNAL)
        plan = response.research_plan_draft_preview.plan

        assert plan is not None
        [conflict] = plan_restriction_conflicts(plan)
        self.assertEqual(conflict.step_id, "step-1")
        self.assertIs(conflict.capability, ResearchPlanStepCapability.SOURCE_DISCOVERY)

    def test_the_contradictory_plan_keeps_its_step(self) -> None:
        """No deletion, no downgrade, no substitute provider."""
        response = preview(CROSSREF_STEP, NO_EXTERNAL)
        plan = response.research_plan_draft_preview.plan

        assert plan is not None
        self.assertEqual(len(plan.steps), 1)
        self.assertIs(
            plan.steps[0].capability, ResearchPlanStepCapability.SOURCE_DISCOVERY
        )
        self.assertEqual(
            plan.steps[0].instruction,
            "Discover supporting literature through Crossref.",
        )

    def test_approval_refuses_before_recording(self) -> None:
        start = AUTHORIZATION_SOURCE.index("    def process_confirm(")
        body = AUTHORIZATION_SOURCE[
            start : AUTHORIZATION_SOURCE.index("\n    def ", start + 1)
        ]

        self.assertIn("_restriction_refusal(plan)", body)
        self.assertIn("contradictory_plan", body)

    def test_the_preview_boundary_refuses_too(self) -> None:
        start = AUTHORIZATION_SOURCE.index("    def process_preview(")
        body = AUTHORIZATION_SOURCE[
            start : AUTHORIZATION_SOURCE.index("\n    def ", start + 1)
        ]

        self.assertIn("_restriction_refusal(plan)", body)

    def test_the_refusal_names_the_step_and_capability(self) -> None:
        self.assertIn("conflict.summary()", AUTHORIZATION_SOURCE)


class ExecutionAsksTheSameQuestionTests(unittest.TestCase):
    def test_start_runs_the_canonical_validator(self) -> None:
        start = EXECUTION_SOURCE.index("    def process_start(")
        body = EXECUTION_SOURCE[start : EXECUTION_SOURCE.index("\n    def ", start + 1)]

        self.assertIn("plan_restriction_conflicts(plan)", body)

    def test_start_refuses_before_reaching_the_registry(self) -> None:
        start = EXECUTION_SOURCE.index("    def process_start(")
        body = EXECUTION_SOURCE[start : EXECUTION_SOURCE.index("\n    def ", start + 1)]
        refusal = body.index("plan_restriction_conflicts(plan)")

        for later in ("_executions[", "operation", "_allowances["):
            with self.subTest(name=later):
                position = body.find(later)
                if position != -1:
                    self.assertLess(refusal, position)

    def test_there_is_exactly_one_rule_table(self) -> None:
        """Both boundaries call the shared function and neither decides itself.

        Not a ban on the capability cost table: execution legitimately reads it
        to check what the allowance affords, which is the budget question, not
        the restriction one. What neither may do is ask a restriction directly
        what it forbids — that answer belongs to the shared validator.
        """
        for name, source in (
            ("authorization", AUTHORIZATION_SOURCE),
            ("execution", EXECUTION_SOURCE),
        ):
            with self.subTest(name=name):
                self.assertIn("plan_restriction_conflicts", source)
                self.assertNotIn(".forbids(", source)


class TheDesktopEnforcesNothingItselfTests(unittest.TestCase):
    def test_the_window_runs_no_validator(self) -> None:
        """It offers the choice and shows the answer. It decides nothing.

        "network operations" appears in the window as a budget field label,
        which is a different concept and not evidence of enforcement here.
        """
        for forbidden in ("plan_restriction_conflicts", ".forbids(", "cost_for("):
            with self.subTest(name=forbidden):
                self.assertNotIn(forbidden, WINDOW_SOURCE)

    def test_the_window_only_offers_the_two_choices(self) -> None:
        self.assertIn("ADVISORY_RESTRICTION_LABEL", WINDOW_SOURCE)
        self.assertIn(
            "ResearchPlanRestriction.NO_EXTERNAL_SOURCE_ACCESS.value", WINDOW_SOURCE
        )

    def test_the_note_explains_that_wording_is_never_read(self) -> None:
        from desktop.TkinterDesktopWindow import _PLAN_CONSTRAINT_NOTE

        note = _PLAN_CONSTRAINT_NOTE.casefold()

        self.assertIn("never read to decide what is enforced", note)
        self.assertIn("only ever refuses", note)


class LocalOnlyWorkStillRunsTests(unittest.TestCase):
    """The restriction must not become a switch that blocks all research."""

    def test_a_local_plan_under_the_restriction_is_valid(self) -> None:
        from research.ResearchPlanRestrictionConflict import (
            plan_restriction_conflicts,
        )

        response = preview(LOCAL_STEP, NO_EXTERNAL)
        plan = response.research_plan_draft_preview.plan

        assert plan is not None
        self.assertEqual(plan_restriction_conflicts(plan), ())

    def test_the_local_plan_keeps_its_capability(self) -> None:
        response = preview(LOCAL_STEP, NO_EXTERNAL)
        plan = response.research_plan_draft_preview.plan

        assert plan is not None
        self.assertIs(
            plan.steps[0].capability,
            ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH,
        )


class NothingElseChangedTests(unittest.TestCase):
    def test_the_failure_trace_still_reads_steps_only(self) -> None:
        source = (SRC_DIR / "research" / "ResearchPlanFailureLessonTrace.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("for step in plan.steps:", source)
        self.assertNotIn("restriction", source.casefold())

    def test_the_scheduler_knows_nothing_of_restrictions(self) -> None:
        """The scheduler still decides nothing about them.

        Deferred grants left this list in v0.3.288, when they began recording
        the restrictions they were granted under. That is their own milestone;
        the scheduler was and remains uninvolved.
        """
        for name in ("cognition/BackgroundResearchSchedulerApplicationService.py",):
            with self.subTest(name=name):
                source = (SRC_DIR / name).read_text(encoding="utf-8")

                self.assertNotIn("restriction", source.casefold())


class TheBoundariesActuallyRefuseTests(unittest.TestCase):
    """Behaviour, not source text.

    An earlier version of these checks read the services' source for the call
    to the validator. That passes even if the call is guarded by something
    permanently false, which is exactly the regression worth catching, so these
    drive the real services and look at what comes back.
    """

    def _request(self, intent: str, step, restriction, **extra):
        return BrainRequest(
            message="plan",
            metadata={
                "intent": intent,
                "research_plan_question": SSRF_QUESTION,
                "research_plan_steps": (step,),
                "research_plan_constraints": (SSRF_CONSTRAINT,),
                "research_plan_restriction": restriction,
                **extra,
            },
        )

    def _execution_service(self):
        from datetime import UTC, datetime

        from cognition.ResearchPlanExecutionApplicationService import (
            ResearchPlanExecutionApplicationService,
        )
        from research.ResearchPlanDraftService import ResearchPlanDraftService

        return ResearchPlanExecutionApplicationService(
            ResponseComposer(),
            ResearchPlanDraftService(
                clock=lambda: datetime(2026, 9, 2, tzinfo=UTC),
                id_factory=lambda: "plan-1",
            ),
        )

    def test_execution_start_refuses_the_contradictory_plan(self) -> None:
        service = self._execution_service()

        response = service.process_start(
            self._request("research_plan_execution_start", CROSSREF_STEP, NO_EXTERNAL)
        )

        self.assertFalse(response.success)
        self.assertIn("contradicts itself", response.message)

    def test_the_refusal_names_the_step_and_capability(self) -> None:
        service = self._execution_service()

        response = service.process_start(
            self._request("research_plan_execution_start", CROSSREF_STEP, NO_EXTERNAL)
        )

        self.assertIn("step-1", response.message)
        self.assertIn("source_discovery", response.message)

    def test_no_execution_state_is_created_for_a_refused_plan(self) -> None:
        service = self._execution_service()

        service.process_start(
            self._request("research_plan_execution_start", CROSSREF_STEP, NO_EXTERNAL)
        )

        self.assertIsNone(service.live_execution("plan-1"))
        self.assertIsNone(service.live_plan("plan-1"))

    def test_the_same_plan_left_advisory_is_not_refused_for_that_reason(
        self,
    ) -> None:
        """Case A must not be blocked by the mere presence of the text."""
        service = self._execution_service()

        response = service.process_start(
            self._request("research_plan_execution_start", CROSSREF_STEP, None)
        )

        self.assertNotIn("contradicts itself", response.message)

    def test_a_local_plan_under_the_restriction_is_not_refused(self) -> None:
        service = self._execution_service()

        response = service.process_start(
            self._request("research_plan_execution_start", LOCAL_STEP, NO_EXTERNAL)
        )

        self.assertNotIn("contradicts itself", response.message)

    def test_authorization_refuses_the_contradictory_plan(self) -> None:
        from datetime import UTC, datetime

        from cognition.ResearchPlanAuthorizationApplicationService import (
            ResearchPlanAuthorizationApplicationService,
        )
        from research.ResearchPlan import ResearchPlan
        from research.ResearchPlanConstraint import ResearchPlanConstraint
        from research.ResearchPlanStep import ResearchPlanStep

        contradictory = ResearchPlan(
            plan_id="plan-1",
            question=SSRF_QUESTION,
            steps=(
                ResearchPlanStep(
                    step_id="step-1",
                    instruction="Discover supporting literature through Crossref.",
                    capability=ResearchPlanStepCapability.SOURCE_DISCOVERY,
                ),
            ),
            created_at=datetime(2026, 9, 2, tzinfo=UTC),
            constraints=(
                ResearchPlanConstraint(text=SSRF_CONSTRAINT, restriction=NO_EXTERNAL),
            ),
        )

        refusal = ResearchPlanAuthorizationApplicationService._restriction_refusal(
            contradictory
        )

        assert refusal is not None
        self.assertIn("cannot be approved", refusal)
        self.assertIn("step-1", refusal)
        self.assertIn("source_discovery", refusal)

    def test_authorization_permits_a_plan_with_no_contradiction(self) -> None:
        from cognition.ResearchPlanAuthorizationApplicationService import (
            ResearchPlanAuthorizationApplicationService,
        )
        from tests.research.test_plan_constraints import plan

        self.assertIsNone(
            ResearchPlanAuthorizationApplicationService._restriction_refusal(
                plan("Review.")
            )
        )


class AdvisoryTextStaysAdvisoryThroughTheDraftServiceTests(unittest.TestCase):
    """The classifier hazard lives here, so the check lives here too."""

    def _plan(self, text: str, restriction):
        from datetime import UTC, datetime

        from research.ResearchPlanDraftService import ResearchPlanDraftService

        service = ResearchPlanDraftService(
            clock=lambda: datetime(2026, 9, 2, tzinfo=UTC),
            id_factory=lambda: "plan-1",
        )
        preview = service.preview(SSRF_QUESTION, (CROSSREF_STEP,), (text,), restriction)
        assert preview.plan is not None
        return preview.plan

    def test_forbidding_wording_alone_creates_no_restriction(self) -> None:
        built = self._plan("Do not access external sources at all.", None)

        self.assertIsNone(built.constraints[0].restriction)

    def test_forbidding_wording_alone_creates_no_conflict(self) -> None:
        from research.ResearchPlanRestrictionConflict import (
            plan_restriction_conflicts,
        )

        built = self._plan("Do not access external sources at all.", None)

        self.assertEqual(plan_restriction_conflicts(built), ())

    def test_the_selected_restriction_is_applied_verbatim(self) -> None:
        built = self._plan("Anything at all.", NO_EXTERNAL)

        self.assertIs(built.constraints[0].restriction, NO_EXTERNAL)


class TheConstrainedSchemaIsItsOwnVersionTests(unittest.TestCase):
    def test_the_constrained_schema_moved_when_its_encoding_changed(self) -> None:
        """A v3 digest described constraints that could only be advisory."""
        from research.ResearchPlanDigest import CANONICAL_SCHEMA_WITH_CONSTRAINTS

        self.assertEqual(
            CANONICAL_SCHEMA_WITH_CONSTRAINTS, "hypatia:research-plan-digest:v4"
        )


class TheApprovalBoundaryRefusesInPracticeTests(unittest.TestCase):
    """Driven through the real service, so a disabled guard is visible.

    Checking the static helper alone would not notice a guard that is never
    reached, which is exactly the shape a regression takes here.
    """

    def setUp(self) -> None:
        from tempfile import TemporaryDirectory

        from cognition.ResearchPlanAuthorizationApplicationService import (
            ResearchPlanAuthorizationApplicationService,
        )
        from research.JsonFileResearchRunStore import JsonFileResearchRunStore
        from research.ResearchRunManager import ResearchRunManager

        self._directory = TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        root = Path(self._directory.name)
        self.runs = ResearchRunManager(JsonFileResearchRunStore(root / "runs.json"))
        self.runs.load()
        self.run = self.runs.create(SSRF_QUESTION)
        self.service = ResearchPlanAuthorizationApplicationService(
            self.runs, ResponseComposer()
        )

    def _preview(self, step, restriction):
        return self.service.process_preview(
            BrainRequest(
                message="approve",
                metadata={
                    "intent": "research_plan_authorization_preview",
                    "research_run_id": self.run.run_id,
                    "research_plan_question": SSRF_QUESTION,
                    "research_plan_steps": (step,),
                    "research_plan_constraints": (SSRF_CONSTRAINT,),
                    "research_plan_restriction": restriction,
                },
            )
        )

    def test_a_contradictory_plan_is_refused_at_preview(self) -> None:
        response = self._preview(CROSSREF_STEP, NO_EXTERNAL)

        self.assertIn("contradicts itself", response.message)

    def test_the_refusal_names_the_step_and_capability(self) -> None:
        response = self._preview(CROSSREF_STEP, NO_EXTERNAL)

        self.assertIn("step-1", response.message)
        self.assertIn("source_discovery", response.message)

    def test_no_approval_is_recorded_for_a_refused_plan(self) -> None:
        self._preview(CROSSREF_STEP, NO_EXTERNAL)

        self.assertEqual(list(self.service.authorizations()), [])

    def test_the_same_plan_left_advisory_is_previewable(self) -> None:
        response = self._preview(CROSSREF_STEP, None)

        self.assertNotIn("contradicts itself", response.message)

    def test_a_local_plan_under_the_restriction_is_previewable(self) -> None:
        response = self._preview(LOCAL_STEP, NO_EXTERNAL)

        self.assertNotIn("contradicts itself", response.message)

    def _confirm(self, step, restriction, authorization_id):
        return self.service.process_confirm(
            BrainRequest(
                message="confirm",
                metadata={
                    "intent": "research_plan_authorization_confirm",
                    "authorization_id": authorization_id,
                    "research_run_id": self.run.run_id,
                    "research_plan_question": SSRF_QUESTION,
                    "research_plan_steps": (step,),
                    "research_plan_constraints": (SSRF_CONSTRAINT,),
                    "research_plan_restriction": restriction,
                },
            )
        )

    def test_confirming_a_contradictory_plan_is_refused(self) -> None:
        """Confirm is the boundary that records, so it is checked directly.

        Previewing a plan and then confirming it with the restriction typed is
        the path that would otherwise write authority for a plan nobody could
        carry out.
        """
        previewed = self._preview(CROSSREF_STEP, None)
        authorization = previewed.research_plan_authorization

        response = self._confirm(
            CROSSREF_STEP,
            NO_EXTERNAL,
            getattr(authorization, "authorization_id", "authorization-1"),
        )

        self.assertIn("contradicts itself", response.message)

    def test_confirming_a_contradictory_plan_records_no_approval(self) -> None:
        previewed = self._preview(CROSSREF_STEP, None)
        authorization = previewed.research_plan_authorization

        self._confirm(
            CROSSREF_STEP,
            NO_EXTERNAL,
            getattr(authorization, "authorization_id", "authorization-1"),
        )

        self.assertEqual(list(self.service.authorizations()), [])


if __name__ == "__main__":
    unittest.main()
