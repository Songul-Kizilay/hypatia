"""What survives a restart, and — more importantly — what must not.

An execution that was proposed, approved, started and perhaps advanced is real
work with a real permission attached to it. Closing the process should not throw
that away, so this milestone lets an operator pick the execution up again. The
danger is the mirror image: a restart must not become a way to get anything the
operator never granted.

So almost every test here is about something staying the same. The approval that
was spent stays spent. The budget that was used stays used, and a restart
refunds nothing. A step that finished stays finished and is never performed
twice. The plan is the same plan, proven by its digest rather than by trusting
the file it came from, and the execution is the same execution, named exactly by
the operator rather than guessed at as "the latest".

Nothing resumes by itself and nothing advances by itself. Recovering an
execution and running a step remain two separate human decisions, and after the
restart one advance still means one step.

Where a piece of what was written down cannot be recovered exactly, the answer
is refusal rather than repair — because a resumed execution that had to be
guessed at is not the execution anybody approved.
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

from dataclasses import replace

from brain.BrainRequest import BrainRequest
from cognition.CuriosityApplicationService import (
    CURIOSITY_RESUME_EXECUTION_INTENT,
    CuriosityApplicationService,
)
from cognition.ResearchPlanExecutionApplicationService import (
    RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT,
    ResearchPlanExecutionApplicationService,
)
from core.Exceptions import ResearchError
from research.JsonFileCuriosityQuestionStore import JsonFileCuriosityQuestionStore
from research.JsonFileResearchExecutionStore import JsonFileResearchExecutionStore
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchCapabilityCost import cost_for
from research.ResearchExecutionAllowance import ResearchExecutionAllowance
from research.ResearchPlan import ResearchPlan
from research.ResearchPlanDraftService import ResearchPlanDraftService
from research.ResearchPlanExecutionSnapshot import ResearchPlanExecutionSnapshot
from research.ResearchPlanExecutionState import ResearchPlanExecutionState
from research.ResearchPlanExecutionStatus import ResearchPlanExecutionStatus
from research.ResearchPlanOperationRegistry import ResearchPlanOperationRegistry
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchPlanStepState import ResearchPlanStepState
from research.ResearchPlanStepStatus import ResearchPlanStepStatus
from response.ResponseComposer import ResponseComposer
from tests.research.test_curiosity_execution_advance import (
    CURIOSITY_PLAN_CAPABILITIES,
    NOW,
    QUESTION,
    AdvanceFixture,
    RecordingDiscoveryOperation,
)


class ResumeFixture(AdvanceFixture):
    """The advance chain again, this time with somewhere durable to write.

    The restart is real rather than mimed: a second set of services is built
    over the same files, with a fresh registry and empty memory, exactly as a
    new process would find them.
    """

    def setUp(self) -> None:
        super().setUp()
        self.execution_store = JsonFileResearchExecutionStore(
            self.root / "executions.json"
        )
        self.question_store = JsonFileCuriosityQuestionStore(
            self.root / "questions.json"
        )
        self.execution_service = ResearchPlanExecutionApplicationService(
            ResponseComposer(),
            operation_registry=self._registry(self.operation),
            authorization_consumer=self.authorization_service,
            execution_store=self.execution_store,
            clock=lambda: NOW,
        )
        self.service = self._curiosity(self.execution_service)
        self.question = self._question()

    def _registry(self, operation: object) -> ResearchPlanOperationRegistry:
        registry = ResearchPlanOperationRegistry()
        for capability in CURIOSITY_PLAN_CAPABILITIES:
            registry.register(capability, operation)
        return registry

    def _curiosity(
        self,
        execution_service: ResearchPlanExecutionApplicationService,
        *,
        drafts_differently: bool = False,
    ) -> CuriosityApplicationService:
        draft_service = ResearchPlanDraftService(
            id_factory=lambda: "plan-1", clock=lambda: NOW
        )
        return CuriosityApplicationService(
            self.manager,
            ResponseComposer(),
            hypothesis_store=self.hypothesis_store,
            authorization_service=self.authorization_service,
            execution_starter=execution_service,
            draft_service=(
                _RewordingDraftService(draft_service)
                if drafts_differently
                else draft_service
            ),
            question_store=self.question_store,
            clock=lambda: NOW,
        )

    def _restart(
        self,
        *,
        operation: object | None = None,
        registered: bool = True,
        drafts_differently: bool = False,
    ):
        """Return the services a new process would build over the same files."""
        self.reopened_operation = operation or RecordingDiscoveryOperation()
        registry = (
            self._registry(self.reopened_operation)
            if registered
            else ResearchPlanOperationRegistry()
        )
        self.reopened_execution = ResearchPlanExecutionApplicationService(
            ResponseComposer(),
            operation_registry=registry,
            authorization_consumer=self.authorization_service,
            execution_store=self.execution_store,
            clock=lambda: NOW,
        )
        self.reopened_curiosity = self._curiosity(
            self.reopened_execution,
            drafts_differently=drafts_differently,
        )
        return self.reopened_curiosity, self.reopened_execution

    def _resume(self, service, execution_id: str, question_id: str | None = None):
        return service.process_resume_execution(
            BrainRequest(
                message="Resume",
                metadata={
                    "intent": CURIOSITY_RESUME_EXECUTION_INTENT,
                    "research_plan_id": execution_id,
                    "curiosity_question_id": (
                        question_id
                        if question_id is not None
                        else self.question.question_id
                    ),
                },
            )
        )

    def _advance_on(self, service, execution_id: str):
        return service.process_advance(
            BrainRequest(
                message="Advance",
                metadata={
                    "intent": RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT,
                    "research_plan_id": execution_id,
                },
            )
        )

    def _authorizations(self):
        return list(self.authorization_service.authorizations())


class ResumeRecoversTheSameExecutionTests(ResumeFixture):
    def test_a_started_execution_can_be_resumed_after_restart(self) -> None:
        started = self._started()
        curiosity, execution = self._restart()

        response = self._resume(curiosity, started.plan_id)

        self.assertIsNotNone(response.research_plan_execution)
        self.assertIsNotNone(execution.live_execution(started.plan_id))

    def test_the_resumed_execution_keeps_the_exact_identity(self) -> None:
        started = self._started()
        curiosity, _execution = self._restart()

        resumed = self._resume(curiosity, started.plan_id).research_plan_execution

        self.assertEqual(resumed.plan_id, started.plan_id)

    def test_the_resumed_execution_keeps_the_exact_plan_digest(self) -> None:
        started = self._started()
        [authorization] = self._authorizations()
        curiosity, _execution = self._restart()

        resumed = self._resume(curiosity, started.plan_id)

        self.assertEqual(
            resumed.curiosity_proposal.digest,
            authorization.plan_digest,
        )

    def test_the_resumed_execution_keeps_the_recorded_status(self) -> None:
        started = self._started()
        curiosity, _execution = self._restart()

        resumed = self._resume(curiosity, started.plan_id).research_plan_execution

        self.assertIs(resumed.status, ResearchPlanExecutionStatus.RUNNING)

    def test_resuming_performs_no_research(self) -> None:
        started = self._started()
        curiosity, _execution = self._restart()

        self._resume(curiosity, started.plan_id)

        self.assertEqual(self.reopened_operation.calls, [])

    def test_resuming_twice_refuses_the_second_time(self) -> None:
        """Already live, so there is nothing to recover and nothing changes."""
        started = self._started()
        curiosity, execution = self._restart()
        self._resume(curiosity, started.plan_id)
        before = execution.live_execution(started.plan_id)

        self._resume(curiosity, started.plan_id)

        self.assertIs(execution.live_execution(started.plan_id), before)


class NothingHappensOnItsOwnTests(ResumeFixture):
    def test_a_restart_alone_does_not_resume(self) -> None:
        started = self._started()

        _curiosity, execution = self._restart()

        self.assertIsNone(execution.live_execution(started.plan_id))

    def test_a_restart_alone_does_not_advance(self) -> None:
        self._started()

        self._restart()

        self.assertEqual(self.reopened_operation.calls, [])

    def test_advancing_without_resuming_performs_nothing(self) -> None:
        started = self._started()
        _curiosity, execution = self._restart()

        self._advance_on(execution, started.plan_id)

        self.assertEqual(self.reopened_operation.calls, [])

    def test_resuming_does_not_advance(self) -> None:
        started = self._started()
        curiosity, execution = self._restart()

        self._resume(curiosity, started.plan_id)

        state = execution.live_execution(started.plan_id)
        self.assertEqual(state.completed_steps, 0)

    def test_one_advance_after_resuming_runs_exactly_one_step(self) -> None:
        started = self._started()
        curiosity, execution = self._restart()
        self._resume(curiosity, started.plan_id)

        self._advance_on(execution, started.plan_id)

        self.assertEqual(len(self.reopened_operation.calls), 1)


class AuthorityIsNotCreatedTests(ResumeFixture):
    def test_the_consumed_approval_stays_consumed(self) -> None:
        started = self._started()
        curiosity, _execution = self._restart()

        self._resume(curiosity, started.plan_id)

        [authorization] = self._authorizations()
        self.assertIsNotNone(authorization.consumption)

    def test_resuming_records_no_new_approval(self) -> None:
        started = self._started()
        before = len(self._authorizations())
        curiosity, _execution = self._restart()

        self._resume(curiosity, started.plan_id)

        self.assertEqual(len(self._authorizations()), before)

    def test_an_execution_no_approval_names_is_refused(self) -> None:
        """Nothing was spent on it, so nothing shows it was ever allowed."""
        self._started()
        curiosity, execution = self._restart()

        self._resume(curiosity, "execution-nobody-approved")

        self.assertIsNone(execution.live_execution("execution-nobody-approved"))

    def test_the_capabilities_are_the_approved_ones(self) -> None:
        started = self._started()
        [authorization] = self._authorizations()
        curiosity, execution = self._restart()

        self._resume(curiosity, started.plan_id)

        plan = execution.live_plan(started.plan_id)
        self.assertTrue(
            {step.capability.value for step in plan.steps}.issubset(
                set(authorization.capabilities)
            )
        )


class BudgetSurvivesExactlyTests(ResumeFixture):
    def test_an_untouched_budget_is_restored_unchanged(self) -> None:
        started = self._started()
        before = self.execution_service._allowances[started.plan_id]
        curiosity, execution = self._restart()

        self._resume(curiosity, started.plan_id)

        self.assertEqual(execution._allowances[started.plan_id], before)

    def test_spent_budget_is_not_refunded_by_restarting(self) -> None:
        spent = self._persisted_spend()
        curiosity, execution = self._restart()

        self._resume(curiosity, self.started.plan_id)

        self.assertEqual(execution.allowance(self.started.plan_id), spent)

    def test_a_restarted_budget_is_not_a_fresh_budget(self) -> None:
        fresh = self.execution_service.allowance(self._started_once().plan_id)
        self._persisted_spend()
        curiosity, execution = self._restart()

        self._resume(curiosity, self.started.plan_id)

        self.assertLess(
            execution.allowance(self.started.plan_id).remaining_network_operations,
            fresh.remaining_network_operations,
        )

    def test_an_execution_with_no_recorded_allowance_is_refused(self) -> None:
        """Rather than inventing one, which would be inventing permission."""
        started = self._started()
        self.execution_store.save(
            [
                replace(snapshot, allowance=None)
                for snapshot in self.execution_store.load()
            ]
        )
        curiosity, execution = self._restart()

        self._resume(curiosity, started.plan_id)

        self.assertIsNone(execution.live_execution(started.plan_id))

    def _started_once(self):
        """Start the chain once and remember it, so spend can build on it."""
        if not hasattr(self, "started"):
            self.started = self._started()
        return self.started

    def _persisted_spend(self) -> ResearchExecutionAllowance:
        """Charge the real cost and write it down, without finishing the plan.

        The plan holds one step, so advancing would complete the execution and
        the question asked here would become unreachable. This charges through
        the same allowance API an attempt uses and persists through the same
        call, so what lands on disk is what a partly-spent execution leaves.
        """
        started = self._started_once()
        charged = self.execution_service.allowance(started.plan_id).charged(
            cost_for(ResearchPlanStepCapability.SOURCE_DISCOVERY)
        )
        self.execution_service._allowances[started.plan_id] = charged
        self.execution_service._persist(started.plan_id)
        return charged


class CompletedWorkIsNotRepeatedTests(ResumeFixture):
    def test_a_finished_execution_is_still_finished_after_the_restart(self) -> None:
        """Every authored step ran, so the record stays completed."""
        started = self._started()
        for _step in self.plan_steps(started):
            self._advance(started.plan_id)
        _curiosity, execution = self._restart()

        snapshot = execution.restored_execution(started.plan_id)

        self.assertIs(snapshot.status, ResearchPlanExecutionStatus.COMPLETED)
        self.assertTrue(
            all(
                step.status is ResearchPlanStepStatus.COMPLETED
                for step in snapshot.steps
            )
        )

    def test_a_finished_execution_is_never_resumed_or_rerun(self) -> None:
        """The strongest form of not repeating work: it cannot start again."""
        started = self._started()
        for _step in self.plan_steps(started):
            self._advance(started.plan_id)
        curiosity, execution = self._restart()

        self._resume(curiosity, started.plan_id)
        self._advance_on(execution, started.plan_id)

        self.assertEqual(len(self.operation.calls), len(self.plan_steps(started)))
        self.assertIsNone(execution.live_execution(started.plan_id))
        self.assertEqual(self.reopened_operation.calls, [])

    def test_pending_steps_stay_pending_across_the_restart(self) -> None:
        started = self._started()
        curiosity, execution = self._restart()

        self._resume(curiosity, started.plan_id)

        state = execution.live_execution(started.plan_id)
        self.assertEqual(state.pending_steps, started.pending_steps)


class ClosedExecutionsStayClosedTests(ResumeFixture):
    def test_a_cancelled_execution_is_not_resumable(self) -> None:
        started = self._started()
        self._cancel(started.plan_id)
        curiosity, execution = self._restart()

        self._resume(curiosity, started.plan_id)

        self.assertIsNone(execution.live_execution(started.plan_id))

    def test_a_cancelled_execution_says_so_when_refused(self) -> None:
        started = self._started()
        self._cancel(started.plan_id)
        curiosity, _execution = self._restart()

        response = self._resume(curiosity, started.plan_id)

        self.assertIn("cancelled", response.message.casefold())

    def test_a_cancelled_execution_cannot_be_advanced_after_a_restart(self) -> None:
        started = self._started()
        self._cancel(started.plan_id)
        curiosity, execution = self._restart()
        self._resume(curiosity, started.plan_id)

        self._advance_on(execution, started.plan_id)

        self.assertEqual(self.reopened_operation.calls, [])


class RefusesRatherThanGuessesTests(ResumeFixture):
    def test_an_unknown_execution_identity_is_refused(self) -> None:
        self._started()
        curiosity, execution = self._restart()

        self._resume(curiosity, "no-such-execution")

        self.assertIsNone(execution.live_execution("no-such-execution"))

    def test_a_missing_question_is_refused(self) -> None:
        started = self._started()
        curiosity, execution = self._restart()

        self._resume(curiosity, started.plan_id, question_id="no-such-question")

        self.assertIsNone(execution.live_execution(started.plan_id))

    def test_a_blank_execution_identity_is_refused(self) -> None:
        """Naming nothing resumes nothing; there is no "the latest" here."""
        self._started()
        curiosity, _execution = self._restart()

        with self.assertRaises(ResearchError):
            self._resume(curiosity, "   ")

    def test_a_capability_with_no_operation_here_is_refused(self) -> None:
        """A process that cannot do the work must not claim the execution."""
        started = self._started()
        curiosity, execution = self._restart(registered=False)

        self._resume(curiosity, started.plan_id)

        self.assertIsNone(execution.live_execution(started.plan_id))

    def test_a_digest_mismatch_refuses_and_advances_nothing(self) -> None:
        """The plan must be provably the approved one, not merely plausible."""
        started = self._started()
        curiosity, execution = self._restart()
        curiosity, execution = self._restart(drafts_differently=True)

        self._resume(curiosity, started.plan_id)
        self._advance_on(execution, started.plan_id)

        self.assertIsNone(execution.live_execution(started.plan_id))
        self.assertEqual(self.reopened_operation.calls, [])


class RestorationJudgesNothingNewTests(ResumeFixture):
    def test_a_closed_gap_does_not_revoke_an_approval_already_spent(self) -> None:
        """Freshness gates proposing work, not recovering approved work.

        The gap that produced the question is closed here by recording the very
        evidence it was about. Preparing a new proposal would rightly refuse;
        resuming must not, because the operator already approved and started
        this and only they may end it.
        """
        started = self._started()
        curiosity, execution = self._restart()
        # The gap the question came from no longer exists. Preparing a new
        # proposal would refuse on exactly this; resuming must not.
        curiosity._detector = _NoGapsDetector()

        self._resume(curiosity, started.plan_id)

        self.assertIsNotNone(execution.live_execution(started.plan_id))


class PartlyFinishedExecutionTests(ResumeFixture):
    """Two discovery steps isolate rebinding from Curiosity plan composition.

    Curiosity now has a local step followed by discovery. These tests retain a
    direct two-discovery-step plan so they prove the execution layer restores
    completed work without depending on how Curiosity currently authors plans.
    """

    def _partly_finished(self):
        """Persist an execution whose first step ran and whose second has not."""
        plan = ResearchPlan(
            plan_id="plan-two",
            question=QUESTION,
            steps=(
                ResearchPlanStep(
                    step_id="step-1",
                    instruction="Discover candidate sources.",
                    capability=ResearchPlanStepCapability.SOURCE_DISCOVERY,
                ),
                ResearchPlanStep(
                    step_id="step-2",
                    instruction="Discover further candidate sources.",
                    capability=ResearchPlanStepCapability.SOURCE_DISCOVERY,
                ),
            ),
            created_at=NOW,
        )
        state = ResearchPlanExecutionState(
            plan_id="plan-two",
            status=ResearchPlanExecutionStatus.RUNNING,
            steps=(
                ResearchPlanStepState(
                    step_id="step-1",
                    status=ResearchPlanStepStatus.COMPLETED,
                    detail="Candidates recorded.",
                    operation="fake_source_discovery",
                    work_performed=True,
                ),
                ResearchPlanStepState(
                    step_id="step-2",
                    status=ResearchPlanStepStatus.PENDING,
                ),
            ),
        )
        self.execution_store.save(
            [
                ResearchPlanExecutionSnapshot.capture(
                    state,
                    QUESTION,
                    plan.steps,
                    NOW,
                    research_run_id=self.run_id,
                    allowance=ResearchExecutionAllowance(
                        budget=ResearchAutonomyBudget()
                    ).charged(cost_for(ResearchPlanStepCapability.SOURCE_DISCOVERY)),
                )
            ]
        )
        return plan

    def test_a_step_that_already_ran_is_restored_as_finished(self) -> None:
        plan = self._partly_finished()
        _curiosity, execution = self._restart()

        execution.rebind_restored(plan, self.run_id, "plan-two")

        state = execution.live_execution("plan-two")
        self.assertEqual(state.completed_steps, 1)

    def test_advancing_after_rebinding_never_repeats_the_finished_step(self) -> None:
        plan = self._partly_finished()
        _curiosity, execution = self._restart()
        execution.rebind_restored(plan, self.run_id, "plan-two")

        self._advance_on(execution, "plan-two")

        self.assertEqual(self.reopened_operation.calls, ["step-2"])

    def test_one_advance_after_rebinding_is_still_one_step(self) -> None:
        plan = self._partly_finished()
        _curiosity, execution = self._restart()
        execution.rebind_restored(plan, self.run_id, "plan-two")

        self._advance_on(execution, "plan-two")

        self.assertEqual(len(self.reopened_operation.calls), 1)

    def test_the_spend_from_the_finished_step_is_not_refunded(self) -> None:
        plan = self._partly_finished()
        _curiosity, execution = self._restart()

        execution.rebind_restored(plan, self.run_id, "plan-two")

        self.assertLess(
            execution.allowance("plan-two").remaining_network_operations,
            ResearchExecutionAllowance(
                budget=ResearchAutonomyBudget()
            ).remaining_network_operations,
        )

    def test_a_plan_whose_steps_do_not_match_the_record_is_refused(self) -> None:
        """Same identity, different work: not the execution that was recorded."""
        plan = self._partly_finished()
        _curiosity, execution = self._restart()

        execution.rebind_restored(
            replace(plan, steps=plan.steps[:1]),
            self.run_id,
            "plan-two",
        )

        self.assertIsNone(execution.live_execution("plan-two"))


class _RewordingDraftService:
    """A drafting rule that words one step differently than the approved one.

    Stands in for the software changing between the start and the restart. The
    plan it produces is reasonable and wrong: it is not the plan anybody read
    and approved, and the digest is what notices.
    """

    def __init__(self, delegate: ResearchPlanDraftService) -> None:
        self._delegate = delegate

    def preview(self, question: str, step_drafts):
        return self._delegate.preview(
            question,
            tuple(
                replace(draft, instruction=draft.instruction + " Be thorough.")
                for draft in step_drafts
            ),
        )


class _NoGapsDetector:
    """A detector that finds nothing, standing in for a gap that has closed."""

    def detect(self, run, moment, hypotheses):
        return []


if __name__ == "__main__":
    unittest.main()
