"""Letting a person say what happened, without the system guessing for them.

An interrupted attempt is the one situation where Hypatia genuinely cannot know
what it did. The provider was called and the process died; whether anything
reached the other side is a fact that exists only outside this program. Every
tempting way to clear that up is a lie — calling it completed, calling it
failed, calling it never-attempted — and each would be believed by everything
downstream.

So the resolution is a human one, and these tests are mostly about how little it
is allowed to do. It records what the operator says and stops: no provider is
called, no budget moves, no approval is created, and nothing advances afterwards.
The rulings map only to what follows if they are true. "It ran" does not become
completed, because nobody has the result; it becomes blocked with the work
acknowledged. "It never ran" returns the step to pending, so a later, explicit
advance is an ordinary new attempt paying the ordinary price. "I still don't
know" changes nothing at all, which is the entire reason for offering it.

The charge for the interrupted attempt is untouchable throughout. It was paid
for reaching out, and reaching out is the part that definitely happened.
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
    RESEARCH_PLAN_EXECUTION_RESOLVE_INTENT,
)
from research.ResearchAttemptResolution import ResearchAttemptResolution
from research.ResearchAuthorizer import ResearchAuthorizer
from research.ResearchPlanExecutionStatus import ResearchPlanExecutionStatus
from research.ResearchPlanStepStatus import ResearchPlanStepStatus
from tests.research.test_execution_attempt_durability import AttemptDurabilityFixture

PERFORMED = ResearchAttemptResolution.PERFORMED_RESULT_UNKNOWN
NOT_PERFORMED = ResearchAttemptResolution.NOT_PERFORMED
UNKNOWN = ResearchAttemptResolution.REMAINS_UNKNOWN


class ResolutionFixture(AttemptDurabilityFixture):
    """A crashed attempt, recovered, waiting for somebody to say what happened."""

    def _interrupted(self):
        """Crash, restart, resume. Returns (execution_id, live service)."""
        started = self._crashed()
        curiosity, execution = self._restart()
        self._resume(curiosity, started.plan_id)
        self.live = execution
        return started.plan_id, execution

    def _resolve(
        self,
        service,
        execution_id: str,
        resolution: ResearchAttemptResolution,
        step_id: str = "step-1",
    ):
        return service.process_resolve(
            BrainRequest(
                message="Resolve",
                metadata={
                    "intent": RESEARCH_PLAN_EXECUTION_RESOLVE_INTENT,
                    "research_plan_id": execution_id,
                    "step_id": step_id,
                    "resolution": (
                        resolution.value
                        if isinstance(resolution, ResearchAttemptResolution)
                        else resolution
                    ),
                },
            )
        )

    def _step_of(self, service, execution_id: str, step_id: str = "step-1"):
        [step] = [
            entry
            for entry in service.live_execution(execution_id).steps
            if entry.step_id == step_id
        ]
        return step


class NothingResolvesItselfTests(ResolutionFixture):
    def test_an_interrupted_step_does_not_resolve_on_its_own(self) -> None:
        execution_id, service = self._interrupted()

        step = self._step_of(service, execution_id)

        self.assertIs(step.status, ResearchPlanStepStatus.INTERRUPTED)
        self.assertIs(step.resolution, ResearchAttemptResolution.NONE)

    def test_restarting_again_does_not_resolve_it(self) -> None:
        execution_id, _service = self._interrupted()

        _curiosity, reopened = self._restart()

        snapshot = reopened.restored_execution(execution_id)
        [step] = snapshot.steps
        self.assertIs(step.resolution, ResearchAttemptResolution.NONE)

    def test_an_empty_ruling_is_refused(self) -> None:
        execution_id, service = self._interrupted()

        self._resolve(service, execution_id, ResearchAttemptResolution.NONE)

        self.assertIs(
            self._step_of(service, execution_id).resolution,
            ResearchAttemptResolution.NONE,
        )

    def test_an_unrecognised_ruling_is_refused(self) -> None:
        execution_id, service = self._interrupted()

        response = self._resolve(service, execution_id, "probably_fine")

        self.assertIn("not a ruling", response.message)


class TheRulingNamesExactlyWhatItRulesOnTests(ResolutionFixture):
    def test_an_unknown_execution_is_refused(self) -> None:
        execution_id, service = self._interrupted()

        self._resolve(service, "no-such-execution", PERFORMED)

        self.assertIs(
            self._step_of(service, execution_id).resolution,
            ResearchAttemptResolution.NONE,
        )

    def test_a_missing_step_identity_is_refused(self) -> None:
        execution_id, service = self._interrupted()

        response = self._resolve(service, execution_id, PERFORMED, step_id="  ")

        self.assertIn("exact step", response.message)

    def test_a_step_that_was_not_interrupted_is_refused(self) -> None:
        execution_id, service = self._interrupted()

        response = self._resolve(
            service, execution_id, PERFORMED, step_id="step-does-not-exist"
        )

        self.assertIs(
            self._step_of(service, execution_id).status,
            ResearchPlanStepStatus.INTERRUPTED,
        )
        self.assertFalse(response.success)

    def test_a_running_execution_cannot_be_resolved(self) -> None:
        """Nothing was interrupted, so there is nothing to rule on."""
        started = self._started()

        response = self._resolve(self.execution_service, started.plan_id, PERFORMED)

        self.assertFalse(response.success)


class PerformedDoesNotMeanSucceededTests(ResolutionFixture):
    def test_a_performed_ruling_does_not_complete_the_step(self) -> None:
        execution_id, service = self._interrupted()

        self._resolve(service, execution_id, PERFORMED)

        step = self._step_of(service, execution_id)
        self.assertIsNot(step.status, ResearchPlanStepStatus.COMPLETED)
        self.assertIs(step.status, ResearchPlanStepStatus.BLOCKED)

    def test_a_performed_ruling_does_not_fabricate_a_provider_result(self) -> None:
        execution_id, service = self._interrupted()

        self._resolve(service, execution_id, PERFORMED)

        step = self._step_of(service, execution_id)
        self.assertIsNot(step.status, ResearchPlanStepStatus.FAILED)
        self.assertNotIn("succe", step.detail.casefold())

    def test_a_performed_ruling_acknowledges_the_work(self) -> None:
        """The call happened, and the record says so without saying more."""
        execution_id, service = self._interrupted()

        self._resolve(service, execution_id, PERFORMED)

        step = self._step_of(service, execution_id)
        self.assertTrue(step.work_performed)
        self.assertEqual(step.operation, "observing_source_discovery")

    def test_a_performed_ruling_blocks_the_execution(self) -> None:
        execution_id, service = self._interrupted()

        self._resolve(service, execution_id, PERFORMED)

        self.assertIs(
            service.live_execution(execution_id).status,
            ResearchPlanExecutionStatus.BLOCKED,
        )


class NotPerformedTests(ResolutionFixture):
    def test_a_not_performed_ruling_returns_the_step_to_pending(self) -> None:
        execution_id, service = self._interrupted()

        self._resolve(service, execution_id, NOT_PERFORMED)

        step = self._step_of(service, execution_id)
        self.assertIs(step.status, ResearchPlanStepStatus.PENDING)
        self.assertFalse(step.work_performed)

    def test_a_not_performed_ruling_refunds_nothing(self) -> None:
        execution_id, service = self._interrupted()
        charged = service.allowance(execution_id)

        self._resolve(service, execution_id, NOT_PERFORMED)

        self.assertEqual(service.allowance(execution_id), charged)

    def test_a_not_performed_ruling_does_not_retry_the_provider(self) -> None:
        execution_id, service = self._interrupted()

        self._resolve(service, execution_id, NOT_PERFORMED)

        self.assertEqual(self.reopened_operation.calls, [])

    def test_a_later_advance_is_a_new_attempt_charged_again(self) -> None:
        """Explicit, operator-pressed, and priced like any other attempt."""
        execution_id, service = self._interrupted()
        self._resolve(service, execution_id, NOT_PERFORMED)
        before = service.allowance(execution_id)

        self._advance_on(service, execution_id)

        self.assertEqual(self.reopened_operation.calls, ["step-1"])
        self.assertLess(
            service.allowance(execution_id).remaining_network_operations,
            before.remaining_network_operations,
        )


class UnknownStaysUnknownTests(ResolutionFixture):
    def test_an_unknown_ruling_leaves_the_step_interrupted(self) -> None:
        execution_id, service = self._interrupted()

        self._resolve(service, execution_id, UNKNOWN)

        self.assertIs(
            self._step_of(service, execution_id).status,
            ResearchPlanStepStatus.INTERRUPTED,
        )

    def test_an_unknown_ruling_is_still_recorded(self) -> None:
        execution_id, service = self._interrupted()

        self._resolve(service, execution_id, UNKNOWN)

        self.assertIs(self._step_of(service, execution_id).resolution, UNKNOWN)

    def test_an_unknown_ruling_keeps_advance_blocked(self) -> None:
        execution_id, service = self._interrupted()
        self._resolve(service, execution_id, UNKNOWN)

        response = self._advance_on(service, execution_id)

        self.assertEqual(self.reopened_operation.calls, [])
        self.assertIn("interrupted", response.message.casefold())


class ResolutionCostsAndCreatesNothingTests(ResolutionFixture):
    def test_resolving_charges_no_budget(self) -> None:
        execution_id, service = self._interrupted()
        before = service.allowance(execution_id)

        for ruling in (UNKNOWN, PERFORMED):
            self._resolve(service, execution_id, ruling)

        self.assertEqual(service.allowance(execution_id), before)

    def test_resolving_calls_no_provider(self) -> None:
        execution_id, service = self._interrupted()

        for ruling in (UNKNOWN, PERFORMED):
            self._resolve(service, execution_id, ruling)

        self.assertEqual(self.reopened_operation.calls, [])

    def test_resolving_creates_no_authorization(self) -> None:
        execution_id, service = self._interrupted()
        before = len(self._authorizations())

        self._resolve(service, execution_id, PERFORMED)

        self.assertEqual(len(self._authorizations()), before)

    def test_the_consumed_authorization_stays_consumed(self) -> None:
        execution_id, service = self._interrupted()

        self._resolve(service, execution_id, PERFORMED)

        [authorization] = self._authorizations()
        self.assertIsNotNone(authorization.consumption)

    def test_resolving_does_not_advance(self) -> None:
        execution_id, service = self._interrupted()

        self._resolve(service, execution_id, NOT_PERFORMED)

        self.assertEqual(self.reopened_operation.calls, [])
        self.assertEqual(service.live_execution(execution_id).completed_steps, 0)


class TheRulingSurvivesRestartTests(ResolutionFixture):
    def test_a_ruling_is_durable(self) -> None:
        execution_id, service = self._interrupted()
        self._resolve(service, execution_id, PERFORMED)

        _curiosity, reopened = self._restart()

        [step] = reopened.restored_execution(execution_id).steps
        self.assertIs(step.resolution, PERFORMED)

    def test_a_ruling_records_who_and_when(self) -> None:
        execution_id, service = self._interrupted()

        self._resolve(service, execution_id, PERFORMED)

        step = self._step_of(service, execution_id)
        self.assertIs(step.resolved_by, ResearchAuthorizer.HUMAN)
        self.assertIsNotNone(step.resolved_at)

    def test_the_spent_allowance_survives_the_ruling_and_the_restart(self) -> None:
        execution_id, service = self._interrupted()
        charged = service.allowance(execution_id)
        self._resolve(service, execution_id, PERFORMED)

        _curiosity, reopened = self._restart()

        snapshot = reopened.restored_execution(execution_id)
        self.assertEqual(
            snapshot.allowance.remaining_network_operations,
            charged.remaining_network_operations,
        )

    def test_cancelling_a_resolved_execution_still_works(self) -> None:
        execution_id, service = self._interrupted()
        self._resolve(service, execution_id, NOT_PERFORMED)

        service.process_cancel(
            BrainRequest(
                message="Cancel",
                metadata={
                    "intent": "research_plan_execution_cancel",
                    "research_plan_id": execution_id,
                },
            )
        )

        self.assertIs(
            service.live_execution(execution_id).status,
            ResearchPlanExecutionStatus.CANCELLED,
        )


if __name__ == "__main__":
    unittest.main()
