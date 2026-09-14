"""Pressing a button N times, without any of the ways that could go wrong.

Bounded continuation is the first thing in this chain that runs more than one
step from one gesture, so nearly every test here is a way of checking it is
still the same one step underneath. It calls the ordinary advance and nothing
else: the same budget check before each attempt, the same durable checkpoint
before each provider call, the same refusals. Nothing is pre-charged, nothing is
reserved, and no capability is widened because the operator asked for three
steps instead of one.

The other half is stopping. A bound is a maximum and never a target, and every
condition that would end a single advance ends the run: completion, failure,
blocking, interruption, cancellation, an unaffordable next step. It never steps
over a problem to find a step it likes better, and it never quietly repairs one
— resolving an interrupted attempt or abandoning a blocked one stays a human
decision made afterwards, as it was before this existed.

Two kinds of plan appear below, and the difference matters. Most tests here
build multi-step plans directly against the canonical execution model, because
they need shapes a real proposal does not produce — five steps, a capability
withdrawn mid-run, a crash at step two. The last group uses the genuine
Curiosity path instead: a real gap, a real accepted question, a real authorized
proposal, which today authors a local knowledge search followed by one source
discovery. That group is the one that proves the loop is reachable from the
work Hypatia actually proposes for itself, rather than only from plans a test
wrote for it.
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
from cognition.CuriosityApplicationService import (
    CURIOSITY_PREPARE_PROPOSAL_INTENT,
)
from cognition.ResearchPlanExecutionApplicationService import (
    RESEARCH_PLAN_EXECUTION_CONTINUE_INTENT,
)
from core.Exceptions import ResearchError
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchCapabilityCost import cost_for
from research.ResearchContinuationStopReason import ResearchContinuationStopReason
from research.ResearchExecutionAllowance import ResearchExecutionAllowance
from research.ResearchExecutionContinuation import MAX_FOREGROUND_CONTINUATION_STEPS
from research.ResearchPlan import ResearchPlan
from research.ResearchPlanAuthorization import capabilities_of
from research.ResearchPlanExecutionSnapshot import ResearchPlanExecutionSnapshot
from research.ResearchPlanExecutionState import ResearchPlanExecutionState
from research.ResearchPlanExecutionStatus import ResearchPlanExecutionStatus
from research.ResearchPlanOperationRegistry import ResearchPlanOperationRegistry
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchPlanStepOperationResult import ResearchPlanStepOperationResult
from research.ResearchPlanStepState import ResearchPlanStepState
from research.ResearchPlanStepStatus import ResearchPlanStepStatus
from tests.research.test_curiosity_execution_advance import NOW, QUESTION
from tests.research.test_execution_attempt_durability import (
    AttemptDurabilityFixture,
    Crash,
)

DISCOVERY = ResearchPlanStepCapability.SOURCE_DISCOVERY
STOP = ResearchContinuationStopReason


class CountingOperation:
    """A provider that records every call and can be told how to behave."""

    operation_name = "counting_source_discovery"

    def __init__(self, store=None, *, fail_on: str = "", crash_on: str = "") -> None:
        self._store = store
        self._fail_on = fail_on
        self._crash_on = crash_on
        self.calls: list[str] = []
        self.seen_status: list[str] = []

    def run(self, step, context) -> ResearchPlanStepOperationResult:
        self.calls.append(step.step_id)
        if self._store is not None:
            for snapshot in self._store.load():
                for recorded in snapshot.steps:
                    if recorded.step_id == step.step_id:
                        self.seen_status.append(recorded.status.value)
        if step.step_id == self._crash_on:
            raise Crash("The process ended during the attempt.")
        if step.step_id == self._fail_on:
            raise ResearchError("The provider refused this discovery.")
        return ResearchPlanStepOperationResult(
            performed=True, detail="Candidates recorded.", succeeded=True
        )


class ContinuationFixture(AttemptDurabilityFixture):
    """A canonical multi-step execution, built without touching proposals."""

    def _multi_step(
        self,
        count: int = 3,
        *,
        operation: CountingOperation | None = None,
        capabilities: tuple[ResearchPlanStepCapability, ...] = (),
        allowance: ResearchExecutionAllowance | None = None,
    ):
        """Persist and rebind a RUNNING execution with `count` pending steps."""
        kinds = capabilities or tuple(DISCOVERY for _ in range(count))
        plan = ResearchPlan(
            plan_id="plan-many",
            question=QUESTION,
            steps=tuple(
                ResearchPlanStep(
                    step_id=f"step-{index}",
                    instruction=f"Discover candidate sources, pass {index}.",
                    capability=kind,
                )
                for index, kind in enumerate(kinds, start=1)
            ),
            created_at=NOW,
        )
        state = ResearchPlanExecutionState(
            plan_id="plan-many",
            status=ResearchPlanExecutionStatus.RUNNING,
            steps=tuple(
                ResearchPlanStepState(step_id=f"step-{index}")
                for index in range(1, len(kinds) + 1)
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
                    allowance=allowance
                    or ResearchExecutionAllowance(budget=ResearchAutonomyBudget()),
                )
            ]
        )
        self._restart(operation=operation or CountingOperation(self.execution_store))
        for kind in set(kinds) - {DISCOVERY}:
            # Registered so recovery can accept the execution at all: it
            # rightly refuses one this process could not perform. A test that
            # wants the provider gone withdraws it after recovery.
            self.reopened_execution._operation_registry.register(
                kind, self.reopened_operation
            )
        self.reopened_execution.rebind_restored(plan, self.run_id, "plan-many")
        return self.reopened_execution

    def _continue(self, service, execution_id: str, max_steps):
        return service.process_continue(
            BrainRequest(
                message="Continue",
                metadata={
                    "intent": RESEARCH_PLAN_EXECUTION_CONTINUE_INTENT,
                    "research_plan_id": execution_id,
                    "max_steps": max_steps,
                },
            )
        )

    def _result(self, service, execution_id: str, max_steps):
        return self._continue(
            service, execution_id, max_steps
        ).research_execution_continuation


class TheBoundIsExplicitTests(ContinuationFixture):
    def test_a_missing_bound_is_refused_rather_than_unlimited(self) -> None:
        service = self._multi_step()

        response = service.process_continue(
            BrainRequest(
                message="Continue",
                metadata={
                    "intent": RESEARCH_PLAN_EXECUTION_CONTINUE_INTENT,
                    "research_plan_id": "plan-many",
                },
            )
        )

        self.assertFalse(response.success)
        self.assertEqual(self.reopened_operation.calls, [])

    def test_zero_is_refused(self) -> None:
        service = self._multi_step()

        self._continue(service, "plan-many", 0)

        self.assertEqual(self.reopened_operation.calls, [])

    def test_a_negative_bound_is_refused(self) -> None:
        service = self._multi_step()

        self._continue(service, "plan-many", -3)

        self.assertEqual(self.reopened_operation.calls, [])

    def test_a_malformed_bound_is_refused(self) -> None:
        service = self._multi_step()

        self._continue(service, "plan-many", "as many as it takes")

        self.assertEqual(self.reopened_operation.calls, [])

    def test_a_bound_above_the_maximum_is_refused(self) -> None:
        service = self._multi_step()

        self._continue(service, "plan-many", MAX_FOREGROUND_CONTINUATION_STEPS + 1)

        self.assertEqual(self.reopened_operation.calls, [])

    def test_an_unknown_execution_is_refused(self) -> None:
        service = self._multi_step()

        response = self._continue(service, "no-such-execution", 3)

        self.assertFalse(response.success)
        self.assertEqual(self.reopened_operation.calls, [])


class TheBoundIsAMaximumTests(ContinuationFixture):
    def test_one_step_behaves_like_one_ordinary_advance(self) -> None:
        service = self._multi_step()

        result = self._result(service, "plan-many", 1)

        self.assertEqual(self.reopened_operation.calls, ["step-1"])
        self.assertEqual(result.attempted_step_ids, ("step-1",))
        self.assertIs(result.stop_reason, STOP.BOUND_REACHED)

    def test_three_steps_attempt_exactly_three(self) -> None:
        service = self._multi_step(count=5)

        result = self._result(service, "plan-many", 3)

        self.assertEqual(self.reopened_operation.calls, ["step-1", "step-2", "step-3"])
        self.assertEqual(result.attempted_steps, 3)

    def test_it_never_attempts_one_more_than_asked(self) -> None:
        service = self._multi_step(count=5)

        self._continue(service, "plan-many", 2)

        self.assertNotIn("step-3", self.reopened_operation.calls)

    def test_the_result_reports_requested_and_attempted(self) -> None:
        """Two of five, because two is what was asked for."""
        service = self._multi_step(count=5)

        result = self._result(service, "plan-many", 2)

        self.assertEqual(result.requested_max_steps, 2)
        self.assertEqual(result.attempted_steps, 2)
        self.assertEqual(result.next_step_id, "step-3")

    def test_a_finished_plan_stops_at_completion(self) -> None:
        service = self._multi_step(count=2)

        result = self._result(service, "plan-many", 5)

        self.assertEqual(self.reopened_operation.calls, ["step-1", "step-2"])
        self.assertIs(result.stop_reason, STOP.COMPLETED)
        self.assertIs(result.final_status, ResearchPlanExecutionStatus.COMPLETED)


class ItStopsAtTheFirstProblemTests(ContinuationFixture):
    def test_a_provider_failure_stops_the_run(self) -> None:
        service = self._multi_step(
            count=4,
            operation=CountingOperation(self.execution_store, fail_on="step-2"),
        )

        result = self._result(service, "plan-many", 4)

        self.assertEqual(self.reopened_operation.calls, ["step-1", "step-2"])
        self.assertIs(result.stop_reason, STOP.FAILED)

    def test_a_provider_failure_is_never_retried(self) -> None:
        service = self._multi_step(
            count=4,
            operation=CountingOperation(self.execution_store, fail_on="step-1"),
        )

        self._continue(service, "plan-many", 4)

        self.assertEqual(self.reopened_operation.calls, ["step-1"])

    def test_a_failure_does_not_skip_to_a_later_step(self) -> None:
        service = self._multi_step(
            count=4,
            operation=CountingOperation(self.execution_store, fail_on="step-2"),
        )

        self._continue(service, "plan-many", 4)

        self.assertNotIn("step-3", self.reopened_operation.calls)

    def test_an_unavailable_capability_blocks_and_stops(self) -> None:
        """The second step's capability has no operation in this process.

        Registered while the execution is recovered, because recovery rightly
        refuses an execution it could not perform, then withdrawn — which is
        what a process that lacks the provider actually looks like once the
        run is under way.
        """
        listing = ResearchPlanStepCapability.ACCEPTED_SOURCE_LISTING
        service = self._multi_step(capabilities=(DISCOVERY, listing))
        registry = ResearchPlanOperationRegistry()
        registry.register(DISCOVERY, self.reopened_operation)
        service._operation_registry = registry

        result = self._result(service, "plan-many", 3)

        self.assertEqual(self.reopened_operation.calls, ["step-1"])
        self.assertIs(result.stop_reason, STOP.BLOCKED)

    def test_a_cancelled_execution_attempts_nothing(self) -> None:
        service = self._multi_step()
        self._cancel_on(service, "plan-many")

        result = self._result(service, "plan-many", 3)

        self.assertEqual(self.reopened_operation.calls, [])
        self.assertIs(result.stop_reason, STOP.CANCELLED)

    def test_an_interrupted_execution_attempts_nothing(self) -> None:
        service = self._interrupted_multi_step()

        result = self._result(service, "plan-many", 3)

        self.assertEqual(self.reopened_operation.calls, [])
        self.assertIs(result.stop_reason, STOP.INTERRUPTED)

    def test_an_interrupted_step_is_not_resolved_automatically(self) -> None:
        service = self._interrupted_multi_step()

        self._result(service, "plan-many", 3)

        [step] = [
            entry
            for entry in service.live_execution("plan-many").steps
            if entry.step_id == "step-1"
        ]
        self.assertIs(step.status, ResearchPlanStepStatus.INTERRUPTED)
        self.assertIsNone(step.recovery)

    def _cancel_on(self, service, execution_id: str):
        return service.process_cancel(
            BrainRequest(
                message="Cancel",
                metadata={
                    "intent": "research_plan_execution_cancel",
                    "research_plan_id": execution_id,
                },
            )
        )

    def _interrupted_multi_step(self):
        """A run whose first step died mid-attempt, exactly as v0.3.242 leaves it."""
        service = self._multi_step(
            count=3,
            operation=CountingOperation(self.execution_store, crash_on="step-1"),
        )
        with self.assertRaises(Crash):
            self._advance_on(service, "plan-many")
        plan = service.live_plan("plan-many")
        reopened = self._restart(operation=CountingOperation(self.execution_store))[1]
        reopened.rebind_restored(plan, self.run_id, "plan-many")
        return reopened


class EveryStepPaysTheOrdinaryPriceTests(ContinuationFixture):
    def test_each_attempted_step_is_charged(self) -> None:
        service = self._multi_step(count=4)
        before = service.allowance("plan-many")

        self._continue(service, "plan-many", 3)

        after = service.allowance("plan-many")
        self.assertEqual(
            before.remaining_network_operations - after.remaining_network_operations,
            3 * cost_for(DISCOVERY).network_operations,
        )

    def test_nothing_is_charged_before_the_steps_run(self) -> None:
        """A refused bound spends nothing, so no aggregate was reserved."""
        service = self._multi_step(count=4)
        before = service.allowance("plan-many")

        self._continue(service, "plan-many", 0)

        self.assertEqual(service.allowance("plan-many"), before)

    def test_an_unaffordable_step_stops_before_the_provider(self) -> None:
        """The bound allows five; the approved budget allows three."""
        affordable = self._affordable_steps()
        service = self._multi_step(count=affordable + 2)

        result = self._result(service, "plan-many", affordable + 2)

        self.assertEqual(len(self.reopened_operation.calls), affordable)
        self.assertIs(result.stop_reason, STOP.BUDGET_EXHAUSTED)
        self.assertEqual(result.next_step_id, f"step-{affordable + 1}")

    @staticmethod
    def _affordable_steps() -> int:
        """How many discovery steps the approved budget actually covers."""
        allowance = ResearchExecutionAllowance(budget=ResearchAutonomyBudget())
        cost = cost_for(DISCOVERY)
        count = 0
        while allowance.affords(cost):
            allowance = allowance.charged(cost)
            count += 1
        return count

    def test_an_already_spent_allowance_reaches_no_provider(self) -> None:
        allowance = ResearchExecutionAllowance(budget=ResearchAutonomyBudget())
        cost = cost_for(DISCOVERY)
        while allowance.affords(cost):
            allowance = allowance.charged(cost)
        service = self._multi_step(count=3, allowance=allowance)

        result = self._result(service, "plan-many", 3)

        self.assertEqual(self.reopened_operation.calls, [])
        self.assertIs(result.stop_reason, STOP.BUDGET_EXHAUSTED)

    def test_an_exhausted_run_refunds_nothing(self) -> None:
        allowance = ResearchExecutionAllowance(budget=ResearchAutonomyBudget())
        cost = cost_for(DISCOVERY)
        while allowance.affords(cost):
            allowance = allowance.charged(cost)
        service = self._multi_step(count=3, allowance=allowance)

        self._continue(service, "plan-many", 3)

        self.assertEqual(service.allowance("plan-many"), allowance)


class EachStepKeepsItsOwnGuaranteesTests(ContinuationFixture):
    def test_every_step_is_durable_before_its_provider_runs(self) -> None:
        """The v0.3.242 checkpoint still happens, once per step, not once a run."""
        service = self._multi_step(count=3)

        self._continue(service, "plan-many", 3)

        self.assertEqual(self.reopened_operation.seen_status, ["running"] * 3)

    def test_a_crash_mid_run_leaves_the_ordinary_durable_state(self) -> None:
        service = self._multi_step(
            count=3,
            operation=CountingOperation(self.execution_store, crash_on="step-2"),
        )

        with self.assertRaises(Crash):
            self._continue(service, "plan-many", 3)

        [snapshot] = self.execution_store.load()
        statuses = {step.step_id: step.status for step in snapshot.steps}
        self.assertIs(statuses["step-1"], ResearchPlanStepStatus.COMPLETED)
        self.assertIs(statuses["step-2"], ResearchPlanStepStatus.RUNNING)
        self.assertIs(statuses["step-3"], ResearchPlanStepStatus.PENDING)

    def test_a_crash_mid_run_keeps_both_charges(self) -> None:
        service = self._multi_step(
            count=3,
            operation=CountingOperation(self.execution_store, crash_on="step-2"),
        )
        fresh = service.allowance("plan-many")

        with self.assertRaises(Crash):
            self._continue(service, "plan-many", 3)

        [snapshot] = self.execution_store.load()
        self.assertEqual(
            fresh.remaining_network_operations
            - snapshot.allowance.remaining_network_operations,
            2 * cost_for(DISCOVERY).network_operations,
        )

    def test_one_ordinary_advance_still_works_unchanged(self) -> None:
        service = self._multi_step(count=3)

        self._advance_on(service, "plan-many")

        self.assertEqual(self.reopened_operation.calls, ["step-1"])


class RealCuriosityJourneyTests(ContinuationFixture):
    """The whole chain, from a gap Hypatia found to steps it actually ran.

    Nothing synthetic: the plan is the one a real accepted question produces,
    approved by its own digest and started through the ordinary path. What is
    being checked is that bounded continuation needs no special plan to be
    useful — the proposal Hypatia authors for itself is already multi-step, and
    the loop runs it in authored order without widening anything.
    """

    def _prepared(self):
        """Accept the question and return the proposal, having run nothing."""
        self.service.process_question_accept(
            self._request(
                "curiosity_question_accept",
                curiosity_question_id=self.question.question_id,
            )
        )
        return self.service.process_prepare_proposal(
            self._request(
                CURIOSITY_PREPARE_PROPOSAL_INTENT,
                curiosity_question_id=self.question.question_id,
            )
        ).curiosity_proposal

    def test_a_real_proposal_authors_two_ordered_steps(self) -> None:
        proposal = self._prepared()

        self.assertEqual(
            tuple(step.capability for step in proposal.plan.steps),
            (
                ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH,
                ResearchPlanStepCapability.SOURCE_DISCOVERY,
            ),
        )

    def test_the_same_state_produces_the_same_digest(self) -> None:
        first = self._prepared()

        second = self.service.process_prepare_proposal(
            self._request(
                CURIOSITY_PREPARE_PROPOSAL_INTENT,
                curiosity_question_id=self.question.question_id,
            )
        ).curiosity_proposal

        self.assertEqual(first.digest, second.digest)

    def test_preparing_a_proposal_performs_no_operation(self) -> None:
        self._prepared()

        self.assertEqual(self.operation.calls, [])

    def test_starting_performs_no_step(self) -> None:
        started = self._started()

        self.assertEqual(self.operation.calls, [])
        self.assertEqual(started.completed_steps, 0)
        self.assertIs(started.status, ResearchPlanExecutionStatus.RUNNING)

    def test_the_approval_names_exactly_the_authored_capabilities(self) -> None:
        started = self._started()
        [authorization] = list(self.authorization_service.authorizations())

        plan = self.execution_service.live_plan(started.plan_id)

        self.assertEqual(authorization.capabilities, capabilities_of(plan))
        self.assertEqual(
            authorization.capabilities,
            frozenset(
                {
                    ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH,
                    ResearchPlanStepCapability.SOURCE_DISCOVERY,
                }
            ),
        )

    def test_a_bound_of_one_runs_only_the_local_search(self) -> None:
        """The outward step is next, and stays next until asked for again."""
        started = self._started()

        result = self._result(self.execution_service, started.plan_id, 1)

        self.assertEqual(self.operation.calls, ["step-1"])
        self.assertEqual(result.attempted_step_ids, ("step-1",))
        self.assertEqual(result.next_step_id, "step-2")
        self.assertIs(result.stop_reason, STOP.BOUND_REACHED)

    def test_a_bound_of_one_charges_nothing_for_the_local_step(self) -> None:
        started = self._started()
        before = self.execution_service.allowance(started.plan_id)

        self._continue(self.execution_service, started.plan_id, 1)

        self.assertEqual(
            self.execution_service.allowance(
                started.plan_id
            ).remaining_network_operations,
            before.remaining_network_operations,
        )

    def test_a_bound_of_two_runs_both_authored_steps_in_order(self) -> None:
        started = self._started()

        result = self._result(self.execution_service, started.plan_id, 2)

        self.assertEqual(self.operation.calls, ["step-1", "step-2"])
        self.assertEqual(result.attempted_step_ids, ("step-1", "step-2"))
        self.assertIs(result.final_status, ResearchPlanExecutionStatus.COMPLETED)
        self.assertIs(result.stop_reason, STOP.COMPLETED)

    def test_the_discovery_step_costs_exactly_its_canonical_price(self) -> None:
        started = self._started()
        before = self.execution_service.allowance(started.plan_id)

        self._continue(self.execution_service, started.plan_id, 2)

        after = self.execution_service.allowance(started.plan_id)
        self.assertEqual(
            before.remaining_network_operations - after.remaining_network_operations,
            cost_for(ResearchPlanStepCapability.SOURCE_DISCOVERY).network_operations,
        )

    def test_a_larger_bound_never_reaches_a_third_step(self) -> None:
        """The plan holds two steps; a bound of five does not invent a third."""
        started = self._started()

        result = self._result(self.execution_service, started.plan_id, 5)

        self.assertEqual(self.operation.calls, ["step-1", "step-2"])
        self.assertEqual(result.attempted_steps, 2)


class RealCuriosityDiscoveryFailureTests(ContinuationFixture):
    """The local step succeeds and the provider refuses, which stops the run.

    The fake refuses only the outward step, so this is a provider failing rather
    than everything failing — the difference between proving a run stops at a
    real refusal and proving nothing works.
    """

    fails = True

    def test_the_local_step_runs_and_the_discovery_is_attempted_once(self) -> None:
        started = self._started()

        self._continue(self.execution_service, started.plan_id, 2)

        self.assertEqual(self.operation.calls, ["step-1", "step-2"])

    def test_the_failure_stops_the_run_with_a_structured_reason(self) -> None:
        started = self._started()

        result = self._result(self.execution_service, started.plan_id, 2)

        self.assertIs(result.stop_reason, STOP.FAILED)
        self.assertIs(result.final_status, ResearchPlanExecutionStatus.FAILED)

    def test_the_failed_discovery_is_not_retried(self) -> None:
        started = self._started()

        self._continue(self.execution_service, started.plan_id, 5)

        self.assertEqual(self.operation.calls.count("step-2"), 1)

    def test_the_failed_step_is_recorded_as_failed(self) -> None:
        started = self._started()

        self._continue(self.execution_service, started.plan_id, 2)

        [step] = [
            entry
            for entry in self.execution_service.live_execution(started.plan_id).steps
            if entry.step_id == "step-2"
        ]
        self.assertIs(step.status, ResearchPlanStepStatus.FAILED)

    def test_the_failed_attempt_is_not_refunded(self) -> None:
        """It reached the provider, so it is paid for whatever came back."""
        started = self._started()
        before = self.execution_service.allowance(started.plan_id)

        self._continue(self.execution_service, started.plan_id, 2)

        self.assertLess(
            self.execution_service.allowance(
                started.plan_id
            ).remaining_network_operations,
            before.remaining_network_operations,
        )


if __name__ == "__main__":
    unittest.main()
