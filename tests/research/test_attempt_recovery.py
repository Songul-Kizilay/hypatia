"""What a person may add afterwards, and what it is never allowed to become.

A step blocked as performed-with-unknown-result is a dead end by design: the
operation may have run, nobody saw what came back, and Hypatia will not guess.
This is where an operator gets to act on it — either by going and looking, and
reporting what they found, or by deciding the step is not worth pursuing.

The whole difficulty is the first one. Text a person types is not a provider
response, however accurate it happens to be, and the moment those two are stored
alike everything downstream loses the ability to tell them apart. So the record
keeps saying whose it is: a human author, a claimed operation carried only as
that person's account, and no promotion to COMPLETED — because completion in
this system means Hypatia ran something and saw the answer, which no amount of
later testimony makes true.

Abandoning is the other half, and it is deliberately narrow. It stops the step
without claiming it failed or succeeded, keeps the evidence that an attempt may
have happened, and keeps the charge. It lets the steps after it become
reachable, because they were always authorised and need nothing invented.

Neither decision runs anything, spends anything, grants anything, or advances
anything on its own.
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
from cognition.ResearchPlanExecutionApplicationService import (
    RESEARCH_PLAN_EXECUTION_RECOVER_INTENT,
    RESEARCH_PLAN_EXECUTION_STATUS_INTENT,
)
from research.ResearchAttemptRecoveryDecision import ResearchAttemptRecoveryDecision
from research.ResearchAttemptResolution import ResearchAttemptResolution
from research.ResearchAuthorizer import ResearchAuthorizer
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchCapabilityCost import cost_for
from research.ResearchExecutionAllowance import ResearchExecutionAllowance
from research.ResearchPlan import ResearchPlan
from research.ResearchPlanExecutionSnapshot import ResearchPlanExecutionSnapshot
from research.ResearchPlanExecutionState import ResearchPlanExecutionState
from research.ResearchPlanExecutionStatus import ResearchPlanExecutionStatus
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchPlanStepState import ResearchPlanStepState
from research.ResearchPlanStepStatus import ResearchPlanStepStatus
from tests.research.test_curiosity_execution_advance import NOW, QUESTION
from tests.research.test_interrupted_attempt_resolution import (
    PERFORMED,
    ResolutionFixture,
)

SUPPLIED = ResearchAttemptRecoveryDecision.OPERATOR_SUPPLIED_RESULT
ABANDONED = ResearchAttemptRecoveryDecision.ABANDONED
ACCOUNT = "I checked the provider console by hand; three candidates were listed."


class RecoveryFixture(ResolutionFixture):
    """An attempt ruled performed-but-unseen, waiting for somebody to act."""

    def _blocked(self):
        """Crash, resume, rule it performed. Returns (execution_id, service)."""
        execution_id, service = self._interrupted()
        self._resolve(service, execution_id, PERFORMED)
        return execution_id, service

    def _recover(
        self,
        service,
        execution_id: str,
        decision,
        step_id: str = "step-1",
        summary: str = ACCOUNT,
        claimed_operation: str = "observing_source_discovery",
    ):
        return service.process_recover(
            BrainRequest(
                message="Recover",
                metadata={
                    "intent": RESEARCH_PLAN_EXECUTION_RECOVER_INTENT,
                    "research_plan_id": execution_id,
                    "step_id": step_id,
                    "decision": (
                        decision.value
                        if isinstance(decision, ResearchAttemptRecoveryDecision)
                        else decision
                    ),
                    "summary": summary,
                    "claimed_operation": claimed_operation,
                },
            )
        )

    def _status(self, service, execution_id: str):
        return service.process_status(
            BrainRequest(
                message="Status",
                metadata={
                    "intent": RESEARCH_PLAN_EXECUTION_STATUS_INTENT,
                    "research_plan_id": execution_id,
                },
            )
        )


class OnlyTheRightStepIsEligibleTests(RecoveryFixture):
    def test_a_performed_unknown_step_is_eligible(self) -> None:
        execution_id, service = self._blocked()

        self._recover(service, execution_id, SUPPLIED)

        self.assertIsNotNone(self._step_of(service, execution_id).recovery)

    def test_an_interrupted_step_is_not_yet_eligible(self) -> None:
        """It must be ruled on first; there is nothing to recover from yet."""
        execution_id, service = self._interrupted()

        response = self._recover(service, execution_id, SUPPLIED)

        self.assertIsNone(self._step_of(service, execution_id).recovery)
        self.assertFalse(response.success)

    def test_a_running_execution_is_not_eligible(self) -> None:
        started = self._started()

        response = self._recover(self.execution_service, started.plan_id, SUPPLIED)

        self.assertFalse(response.success)

    def test_an_unknown_execution_is_refused(self) -> None:
        execution_id, service = self._blocked()

        self._recover(service, "no-such-execution", SUPPLIED)

        self.assertIsNone(self._step_of(service, execution_id).recovery)

    def test_a_missing_step_identity_is_refused(self) -> None:
        execution_id, service = self._blocked()

        response = self._recover(service, execution_id, SUPPLIED, step_id="  ")

        self.assertIn("exact step", response.message)

    def test_an_unknown_step_identity_is_refused(self) -> None:
        execution_id, service = self._blocked()

        response = self._recover(service, execution_id, SUPPLIED, step_id="step-9")

        self.assertFalse(response.success)
        self.assertIsNone(self._step_of(service, execution_id).recovery)

    def test_an_unrecognised_decision_is_refused(self) -> None:
        execution_id, service = self._blocked()

        response = self._recover(service, execution_id, "just_assume_it_worked")

        self.assertIn("not a recovery decision", response.message)

    def test_supplying_nothing_is_refused(self) -> None:
        """A supplied result with no account of it supplies nothing."""
        execution_id, service = self._blocked()

        response = self._recover(service, execution_id, SUPPLIED, summary="   ")

        self.assertFalse(response.success)
        self.assertIsNone(self._step_of(service, execution_id).recovery)


class HumanInformationStaysHumanTests(RecoveryFixture):
    def test_the_record_names_a_human_author(self) -> None:
        execution_id, service = self._blocked()

        self._recover(service, execution_id, SUPPLIED)

        recovery = self._step_of(service, execution_id).recovery
        self.assertIs(recovery.recorded_by, ResearchAuthorizer.HUMAN)
        self.assertTrue(recovery.human_supplied)

    def test_a_claimed_provider_is_kept_apart_from_the_content(self) -> None:
        """The operator's claim about origin is a separate, weaker field."""
        execution_id, service = self._blocked()

        self._recover(service, execution_id, SUPPLIED)

        recovery = self._step_of(service, execution_id).recovery
        self.assertEqual(recovery.claimed_operation, "observing_source_discovery")
        self.assertNotIn("observing_source_discovery", recovery.summary)

    def test_the_step_operation_is_not_overwritten_by_the_claim(self) -> None:
        execution_id, service = self._blocked()

        self._recover(
            service, execution_id, SUPPLIED, claimed_operation="some_other_provider"
        )

        step = self._step_of(service, execution_id)
        self.assertEqual(step.operation, "observing_source_discovery")

    def test_supplied_information_does_not_complete_the_step(self) -> None:
        execution_id, service = self._blocked()

        self._recover(service, execution_id, SUPPLIED)

        step = self._step_of(service, execution_id)
        self.assertIs(step.status, ResearchPlanStepStatus.BLOCKED)
        self.assertIsNot(step.status, ResearchPlanStepStatus.COMPLETED)

    def test_the_report_says_the_information_is_not_a_provider_result(self) -> None:
        execution_id, service = self._blocked()
        self._recover(service, execution_id, SUPPLIED)

        message = self._status(service, execution_id).message

        self.assertIn("NOT observed by Hypatia", message)
        self.assertIn("not a provider result", message)
        self.assertIn("their account, unverified", message)


class AbandonmentClaimsNothingTests(RecoveryFixture):
    def test_abandoning_does_not_fabricate_success(self) -> None:
        execution_id, service = self._blocked()

        self._recover(service, execution_id, ABANDONED, summary="")

        step = self._step_of(service, execution_id)
        self.assertIsNot(step.status, ResearchPlanStepStatus.COMPLETED)

    def test_abandoning_does_not_fabricate_failure(self) -> None:
        execution_id, service = self._blocked()

        self._recover(service, execution_id, ABANDONED, summary="")

        step = self._step_of(service, execution_id)
        self.assertIsNot(step.status, ResearchPlanStepStatus.FAILED)
        self.assertIs(step.status, ResearchPlanStepStatus.CANCELLED)

    def test_abandoning_keeps_the_evidence_an_attempt_may_have_happened(self) -> None:
        execution_id, service = self._blocked()

        self._recover(service, execution_id, ABANDONED, summary="")

        step = self._step_of(service, execution_id)
        self.assertTrue(step.work_performed)
        self.assertEqual(step.operation, "observing_source_discovery")
        self.assertIs(step.resolution, PERFORMED)

    def test_abandoning_does_not_retry_the_provider(self) -> None:
        execution_id, service = self._blocked()

        self._recover(service, execution_id, ABANDONED, summary="")

        self.assertEqual(self.reopened_operation.calls, [])


class NeitherPathTakesAnythingTests(RecoveryFixture):
    def test_recovery_refunds_nothing(self) -> None:
        execution_id, service = self._blocked()
        charged = service.allowance(execution_id)

        self._recover(service, execution_id, SUPPLIED)

        self.assertEqual(service.allowance(execution_id), charged)

    def test_abandonment_refunds_nothing(self) -> None:
        execution_id, service = self._blocked()
        charged = service.allowance(execution_id)

        self._recover(service, execution_id, ABANDONED, summary="")

        self.assertEqual(service.allowance(execution_id), charged)

    def test_neither_path_charges_anything(self) -> None:
        execution_id, service = self._blocked()
        before = service.allowance(execution_id)

        self._recover(service, execution_id, SUPPLIED)
        self._recover(service, execution_id, ABANDONED, summary="")

        self.assertEqual(service.allowance(execution_id), before)

    def test_neither_path_calls_a_provider(self) -> None:
        execution_id, service = self._blocked()

        self._recover(service, execution_id, SUPPLIED)
        self._recover(service, execution_id, ABANDONED, summary="")

        self.assertEqual(self.reopened_operation.calls, [])

    def test_recovery_creates_no_authorization(self) -> None:
        execution_id, service = self._blocked()
        before = len(self._authorizations())

        self._recover(service, execution_id, SUPPLIED)

        self.assertEqual(len(self._authorizations()), before)

    def test_the_consumed_authorization_stays_consumed(self) -> None:
        execution_id, service = self._blocked()

        self._recover(service, execution_id, SUPPLIED)

        [authorization] = self._authorizations()
        self.assertIsNotNone(authorization.consumption)

    def test_recovery_cannot_grant_a_capability_or_budget(self) -> None:
        """Extra metadata is not a way in; only the named fields are read."""
        execution_id, service = self._blocked()
        before = service.allowance(execution_id)

        service.process_recover(
            BrainRequest(
                message="Recover",
                metadata={
                    "intent": RESEARCH_PLAN_EXECUTION_RECOVER_INTENT,
                    "research_plan_id": execution_id,
                    "step_id": "step-1",
                    "decision": SUPPLIED.value,
                    "summary": ACCOUNT,
                    "capability": "source_discovery",
                    "authorization_id": "smuggled",
                    "budget": "999",
                },
            )
        )

        self.assertEqual(service.allowance(execution_id), before)
        self.assertEqual(len(self._authorizations()), 1)

    def test_neither_path_advances(self) -> None:
        execution_id, service = self._blocked()

        self._recover(service, execution_id, ABANDONED, summary="")

        self.assertEqual(self.reopened_operation.calls, [])
        self.assertEqual(service.live_execution(execution_id).completed_steps, 0)


class ContinuationFollowsTheStateTests(RecoveryFixture):
    def test_supplied_information_leaves_the_execution_blocked(self) -> None:
        execution_id, service = self._blocked()

        self._recover(service, execution_id, SUPPLIED)

        self.assertIs(
            service.live_execution(execution_id).status,
            ResearchPlanExecutionStatus.BLOCKED,
        )

    def test_abandonment_returns_the_execution_to_running(self) -> None:
        execution_id, service = self._blocked()

        self._recover(service, execution_id, ABANDONED, summary="")

        self.assertIs(
            service.live_execution(execution_id).status,
            ResearchPlanExecutionStatus.RUNNING,
        )

    def test_an_abandoned_step_is_not_advanced_into(self) -> None:
        """The plan holds one step, so there is nothing left to advance to."""
        execution_id, service = self._blocked()
        self._recover(service, execution_id, ABANDONED, summary="")

        self._advance_on(service, execution_id)

        self.assertEqual(self.reopened_operation.calls, [])


class TwoStepContinuationTests(RecoveryFixture):
    """A plan with somewhere left to go, which the curiosity plan never has.

    A curiosity proposal authors one step, so abandoning it leaves nothing to
    advance to and the difference between "did not advance" and "could not"
    is invisible. These build the two-step case directly, where an automatic
    advance would be plainly visible as the next step running by itself.
    """

    def _two_step_blocked(self):
        """An execution whose first step is blocked performed-but-unseen."""
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
            status=ResearchPlanExecutionStatus.INTERRUPTED,
            steps=(
                ResearchPlanStepState(
                    step_id="step-1",
                    status=ResearchPlanStepStatus.INTERRUPTED,
                    operation="observing_source_discovery",
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
        _curiosity, service = self._restart()
        service.rebind_restored(plan, self.run_id, "plan-two")
        self._resolve(service, "plan-two", PERFORMED)
        return service

    def test_recovery_does_not_advance_to_the_next_step(self) -> None:
        service = self._two_step_blocked()

        self._recover(service, "plan-two", ABANDONED, summary="")

        self.assertEqual(self.reopened_operation.calls, [])

    def test_supplying_information_does_not_advance_either(self) -> None:
        service = self._two_step_blocked()

        self._recover(service, "plan-two", SUPPLIED)

        self.assertEqual(self.reopened_operation.calls, [])

    def test_a_later_explicit_advance_reaches_the_next_step(self) -> None:
        """Abandoning unblocks the plan; pressing Advance is still required."""
        service = self._two_step_blocked()
        self._recover(service, "plan-two", ABANDONED, summary="")

        self._advance_on(service, "plan-two")

        self.assertEqual(self.reopened_operation.calls, ["step-2"])

    def test_supplied_information_leaves_later_steps_unreachable(self) -> None:
        """Blocked stays blocked, because no result was ever observed."""
        service = self._two_step_blocked()
        self._recover(service, "plan-two", SUPPLIED)

        self._advance_on(service, "plan-two")

        self.assertEqual(self.reopened_operation.calls, [])


class DecisionsSurviveRestartTests(RecoveryFixture):
    def test_supplied_information_is_durable(self) -> None:
        execution_id, service = self._blocked()
        self._recover(service, execution_id, SUPPLIED)

        _curiosity, reopened = self._restart()

        [step] = reopened.restored_execution(execution_id).steps
        self.assertEqual(step.recovery.summary, ACCOUNT)
        self.assertIs(step.recovery.decision, SUPPLIED)
        self.assertIs(step.recovery.recorded_by, ResearchAuthorizer.HUMAN)

    def test_abandonment_is_durable(self) -> None:
        execution_id, service = self._blocked()
        self._recover(service, execution_id, ABANDONED, summary="")

        _curiosity, reopened = self._restart()

        [step] = reopened.restored_execution(execution_id).steps
        self.assertIs(step.recovery.decision, ABANDONED)
        self.assertIs(step.status, ResearchPlanStepStatus.CANCELLED)

    def test_the_interrupted_history_is_still_observable(self) -> None:
        execution_id, service = self._blocked()
        self._recover(service, execution_id, SUPPLIED)

        _curiosity, reopened = self._restart()

        [step] = reopened.restored_execution(execution_id).steps
        self.assertIs(
            step.resolution,
            ResearchAttemptResolution.PERFORMED_RESULT_UNKNOWN,
        )
        self.assertTrue(step.work_performed)

    def test_the_spent_allowance_survives_the_decision_and_restart(self) -> None:
        execution_id, service = self._blocked()
        charged = service.allowance(execution_id)
        self._recover(service, execution_id, SUPPLIED)

        _curiosity, reopened = self._restart()

        snapshot = reopened.restored_execution(execution_id)
        self.assertEqual(
            snapshot.allowance.remaining_network_operations,
            charged.remaining_network_operations,
        )


if __name__ == "__main__":
    unittest.main()
