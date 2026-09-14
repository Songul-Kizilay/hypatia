"""A grant can be sufficient at approval and run out later, and both are right.

Approval asks one question: does this budget cover one clean attempt at every
authored step? A grant that does not is refused. It was fair to wonder, after
that rule reached every approval path, whether the executor's own budget refusal
had become unreachable — whether running out was now something only a forged
approval could produce.

It has not, and this proves it from a grant the real boundary accepted. The
trick is that "one clean attempt each" is a floor, and an operator may grant
exactly that floor. Then anything that costs a second attempt at any step —
which is to say, an attempt that was charged and did not finish — leaves nothing
for it. That is not a flaw in either rule. Approval promises enough authority to
try everything once; it never promised the work would succeed on the first try,
and the executor is what holds the line when it does not.

The path here is entirely canonical: a minimum-sufficient grant, a crash inside
an attempt that was already paid for, a restart, and a human ruling that the
operation never ran. The step becomes pending again — correctly, because nothing
happened — but the budget it would need is gone, so the next advance is refused
before any provider is reached. Nobody is refunded for the attempt that failed
to report back, and nobody retries on their own.

Elapsed time gets the same treatment, through the clock the service already
takes rather than by sleeping.
"""

from __future__ import annotations

import sys
import unittest
from datetime import timedelta
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from brain.BrainRequest import BrainRequest
from cognition.CuriosityApplicationService import (
    CURIOSITY_AUTHORIZE_PROPOSAL_INTENT,
    CURIOSITY_PREPARE_PROPOSAL_INTENT,
    CURIOSITY_START_AUTHORIZED_PROPOSAL_INTENT,
)
from cognition.ResearchPlanExecutionApplicationService import (
    RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT,
    RESEARCH_PLAN_EXECUTION_CONTINUE_INTENT,
    RESEARCH_PLAN_EXECUTION_RESOLVE_INTENT,
)
from research.ResearchAttemptResolution import ResearchAttemptResolution
from research.ResearchCapabilityCost import cost_for
from research.ResearchContinuationStopReason import ResearchContinuationStopReason
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchPlanStepOperationResult import ResearchPlanStepOperationResult
from research.ResearchPlanStepStatus import ResearchPlanStepStatus
from tests.research.test_curiosity_execution_advance import NOW
from tests.research.test_curiosity_execution_resume import ResumeFixture

DISCOVERY = ResearchPlanStepCapability.SOURCE_DISCOVERY
#: Exactly what today's real proposal needs: a local search then one discovery.
TIGHT = {"max_step_advances": "2", "max_network_operations": "1"}


class Crash(BaseException):
    """A process ending mid-attempt, which no `except ResearchError` catches."""


class CrashingDiscoveryOperation:
    """Succeeds locally, dies on the outward step, and counts every call."""

    operation_name = "counting_discovery"

    def __init__(self, *, crash: bool = True) -> None:
        self.calls: list[str] = []
        self._crash = crash

    def run(self, step, context) -> ResearchPlanStepOperationResult:
        self.calls.append(step.step_id)
        if self._crash and step.capability is DISCOVERY:
            raise Crash("The process ended during the attempt.")
        return ResearchPlanStepOperationResult(
            performed=True, detail="Candidates recorded.", succeeded=True
        )


class ExhaustionFixture(ResumeFixture):
    """The real chain, granted exactly what one clean pass would cost."""

    def _request(self, intent: str, **metadata: str) -> BrainRequest:
        return BrainRequest(message="x", metadata={"intent": intent, **metadata})

    def _granted(self, **budget: str):
        """Approve and start through the real boundary. Returns the execution."""
        question_id = self.question.question_id
        self.service.process_question_accept(
            self._request(
                "curiosity_question_accept", curiosity_question_id=question_id
            )
        )
        digest = self.service.process_prepare_proposal(
            self._request(
                CURIOSITY_PREPARE_PROPOSAL_INTENT,
                curiosity_question_id=question_id,
            )
        ).curiosity_proposal.digest
        self.authorization = self.service.process_authorize_proposal(
            self._request(
                CURIOSITY_AUTHORIZE_PROPOSAL_INTENT,
                curiosity_question_id=question_id,
                expected_plan_digest=digest,
                **(budget or TIGHT),
            )
        ).research_plan_authorization
        assert self.authorization is not None, "the tight grant must be accepted"
        self.digest = digest
        return self.service.process_start_authorized_proposal(
            self._request(
                CURIOSITY_START_AUTHORIZED_PROPOSAL_INTENT,
                curiosity_question_id=question_id,
                expected_plan_digest=digest,
                authorization_id=self.authorization.authorization_id,
            )
        ).research_plan_execution

    def _crashing(self, **budget: str):
        """Grant tightly, run the local step, then die inside the discovery."""
        self.operation = CrashingDiscoveryOperation()
        self.execution_service._operation_registry = self._registry(self.operation)
        started = self._granted(**budget)
        self._advance(started.plan_id)
        with self.assertRaises(Crash):
            self._advance(started.plan_id)
        return started.plan_id

    def _recovered(self, execution_id: str):
        """Restart, resume, and rule that the interrupted operation never ran."""
        curiosity, execution = self._restart(
            operation=CrashingDiscoveryOperation(crash=False)
        )
        self._resume(curiosity, execution_id)
        execution.process_resolve(
            self._request(
                RESEARCH_PLAN_EXECUTION_RESOLVE_INTENT,
                research_plan_id=execution_id,
                step_id="step-2",
                resolution=ResearchAttemptResolution.NOT_PERFORMED.value,
            )
        )
        return execution

    def _advance_on(self, service, execution_id: str):
        return service.process_advance(
            self._request(
                RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT,
                research_plan_id=execution_id,
            )
        )


class TheGrantIsGenuinelySufficientTests(ExhaustionFixture):
    """No forged approval is involved; the real boundary accepts this one."""

    def test_the_tight_grant_passes_the_real_adequacy_boundary(self) -> None:
        self._granted()

        self.assertIsNotNone(self.authorization)

    def test_the_grant_is_exactly_the_nominal_requirement(self) -> None:
        started = self._granted()
        plan = self.execution_service.live_plan(started.plan_id)

        fit = self.authorization_service.budget_fit_for(plan, self.authorization.budget)

        self.assertTrue(fit.sufficient)
        self.assertEqual(
            fit.required_advances, self.authorization.budget.max_step_advances
        )
        self.assertEqual(
            fit.required.network_operations,
            self.authorization.budget.max_network_operations,
        )

    def test_starting_still_performs_no_step(self) -> None:
        self.operation = CrashingDiscoveryOperation()
        self.execution_service._operation_registry = self._registry(self.operation)

        started = self._granted()

        self.assertEqual(self.operation.calls, [])
        self.assertEqual(started.completed_steps, 0)

    def test_one_clean_pass_spends_the_whole_grant(self) -> None:
        """Which is what makes a second attempt at anything unaffordable."""
        self.operation = CrashingDiscoveryOperation(crash=False)
        self.execution_service._operation_registry = self._registry(self.operation)
        started = self._granted()

        self._advance(started.plan_id)
        self._advance(started.plan_id)

        allowance = self.execution_service.allowance(started.plan_id)
        self.assertEqual(allowance.remaining_step_advances, 0)
        self.assertEqual(allowance.remaining_network_operations, 0)


class TheChargeSurvivesEverythingTests(ExhaustionFixture):
    def test_the_interrupted_attempt_was_charged(self) -> None:
        execution_id = self._crashing()

        allowance = self.execution_service.allowance(execution_id)

        self.assertEqual(allowance.remaining_network_operations, 0)

    def test_restarting_does_not_restore_the_spent_allowance(self) -> None:
        execution_id = self._crashing()

        _curiosity, execution = self._restart(
            operation=CrashingDiscoveryOperation(crash=False)
        )
        self._resume(_curiosity, execution_id)

        allowance = execution.allowance(execution_id)
        self.assertEqual(allowance.remaining_step_advances, 0)
        self.assertEqual(allowance.remaining_network_operations, 0)

    def test_ruling_it_never_ran_refunds_nothing(self) -> None:
        """The attempt was paid for reaching out, which did happen."""
        execution_id = self._crashing()

        execution = self._recovered(execution_id)

        allowance = execution.allowance(execution_id)
        self.assertEqual(allowance.remaining_network_operations, 0)

    def test_the_step_becomes_pending_again(self) -> None:
        execution_id = self._crashing()

        execution = self._recovered(execution_id)

        [step] = [
            entry
            for entry in execution.live_execution(execution_id).steps
            if entry.step_id == "step-2"
        ]
        self.assertIs(step.status, ResearchPlanStepStatus.PENDING)


class ANewAttemptIsRefusedTests(ExhaustionFixture):
    """The reachability claim itself."""

    def test_the_next_advance_is_refused(self) -> None:
        execution_id = self._crashing()
        execution = self._recovered(execution_id)

        response = self._advance_on(execution, execution_id)

        self.assertFalse(response.success)

    def test_the_refusal_happens_before_any_provider(self) -> None:
        execution_id = self._crashing()
        execution = self._recovered(execution_id)

        self._advance_on(execution, execution_id)

        self.assertEqual(self.reopened_operation.calls, [])

    def test_the_refusal_spends_nothing_further(self) -> None:
        execution_id = self._crashing()
        execution = self._recovered(execution_id)
        before = execution.allowance(execution_id)

        self._advance_on(execution, execution_id)

        self.assertEqual(execution.allowance(execution_id), before)

    def test_nothing_retried_on_its_own(self) -> None:
        execution_id = self._crashing()

        execution = self._recovered(execution_id)

        self.assertEqual(self.reopened_operation.calls, [])
        self.assertIsNotNone(execution.live_execution(execution_id))

    def test_bounded_continuation_halts_on_the_same_exhaustion(self) -> None:
        execution_id = self._crashing()
        execution = self._recovered(execution_id)

        result = execution.process_continue(
            self._request(
                RESEARCH_PLAN_EXECUTION_CONTINUE_INTENT,
                research_plan_id=execution_id,
                max_steps="3",
            )
        ).research_execution_continuation

        self.assertEqual(self.reopened_operation.calls, [])
        self.assertIs(
            result.stop_reason, ResearchContinuationStopReason.BUDGET_EXHAUSTED
        )


class NothingWasWeakenedToGetHereTests(ExhaustionFixture):
    def test_the_nominal_requirement_is_unchanged(self) -> None:
        started = self._granted()
        plan = self.execution_service.live_plan(started.plan_id)

        fit = self.authorization_service.budget_fit_for(plan)

        self.assertEqual(fit.required_advances, 2)
        self.assertEqual(
            fit.required.network_operations,
            cost_for(DISCOVERY).network_operations,
        )

    def test_a_grant_below_the_requirement_is_still_refused(self) -> None:
        """Adequacy was not relaxed to make exhaustion reachable."""
        question_id = self.question.question_id
        self.service.process_question_accept(
            self._request(
                "curiosity_question_accept", curiosity_question_id=question_id
            )
        )
        digest = self.service.process_prepare_proposal(
            self._request(
                CURIOSITY_PREPARE_PROPOSAL_INTENT,
                curiosity_question_id=question_id,
            )
        ).curiosity_proposal.digest

        refused = self.service.process_authorize_proposal(
            self._request(
                CURIOSITY_AUTHORIZE_PROPOSAL_INTENT,
                curiosity_question_id=question_id,
                expected_plan_digest=digest,
                max_network_operations="0",
            )
        )

        self.assertIsNone(refused.research_plan_authorization)

    def test_the_approval_record_is_untouched_by_running_out(self) -> None:
        execution_id = self._crashing()
        granted = self.authorization

        self._recovered(execution_id)

        [recorded] = list(self.authorization_service.authorizations())
        self.assertEqual(recorded.budget, granted.budget)
        self.assertEqual(recorded.plan_digest, granted.plan_digest)
        self.assertEqual(recorded.capabilities, granted.capabilities)

    def test_no_partial_plan_authorization_exists(self) -> None:
        source = (
            SRC_DIR / "cognition" / "ResearchPlanAuthorizationApplicationService.py"
        ).read_text(encoding="utf-8")

        for forbidden in ("partial", "part_of_plan", "subset"):
            with self.subTest(name=forbidden):
                self.assertNotIn(forbidden, source.casefold())


class ElapsedTimeCanExhaustTheGrantTests(ExhaustionFixture):
    """The other reachable route, driven by the clock the service already takes."""

    def _stepping_clock(self, seconds: float):
        """Return a clock that jumps forward once, when the attempt is charged."""
        moments = iter((NOW, NOW + timedelta(seconds=seconds)))
        last = {"value": NOW}

        def clock():
            try:
                last["value"] = next(moments)
            except StopIteration:
                pass
            return last["value"]

        return clock

    def test_time_spent_in_an_attempt_can_leave_nothing_for_the_next(self) -> None:
        self.operation = CrashingDiscoveryOperation(crash=False)
        self.execution_service._operation_registry = self._registry(self.operation)
        started = self._granted(
            max_step_advances="5", max_network_operations="3", max_seconds="60"
        )
        self.execution_service._clock = self._stepping_clock(120.0)

        self._advance(started.plan_id)
        response = self._advance(started.plan_id)

        self.assertEqual(self.operation.calls, ["step-1"])
        self.assertFalse(response.success)
        self.assertLessEqual(
            self.execution_service.allowance(started.plan_id).remaining_seconds, 0
        )

    def test_the_time_refusal_also_precedes_the_provider(self) -> None:
        self.operation = CrashingDiscoveryOperation(crash=False)
        self.execution_service._operation_registry = self._registry(self.operation)
        started = self._granted(
            max_step_advances="5", max_network_operations="3", max_seconds="60"
        )
        self.execution_service._clock = self._stepping_clock(120.0)

        self._advance(started.plan_id)
        self._advance(started.plan_id)

        self.assertNotIn("step-2", self.operation.calls)


if __name__ == "__main__":
    unittest.main()
