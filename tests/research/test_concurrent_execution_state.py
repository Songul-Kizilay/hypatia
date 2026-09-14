"""An attempt that finishes late must not undo what happened while it ran.

`process_advance` reads an execution, commits the attempt, and only then reaches
the provider. The provider is the slow part, and anything can happen during it —
most importantly a person cancelling. Until now the outcome was written from the
snapshot taken before the call, so a cancellation that landed mid-flight was
silently overwritten and the run carried on. The operator was told they had
cancelled; three more steps ran anyway, spending budget, and the durable record
ended up saying completed.

The fix is to commit conditionally. Execution states are immutable values, so
the attempt can simply ask whether the execution is still the one it started
from, and stand down if it is not. No revision counter is needed for that, and
no lock is held anywhere near the provider — only around the compare-and-set
itself, which is where the danger actually is.

A newer state always wins, because it was written by somebody who knew more at a
later moment. What does not change is the attempt's accounting: the charge was
made for reaching out, reaching out happened, and nothing here gives it back.
The operation's having returned is still reported, as an event that names the
status which actually stands rather than one this attempt wished into place.

Every race below is driven by an Event, never by timing.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from threading import Event, Thread

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from brain.BrainRequest import BrainRequest
from core.Exceptions import ResearchError
from research.ResearchContinuationStopReason import ResearchContinuationStopReason
from research.ResearchPlanExecutionStatus import ResearchPlanExecutionStatus
from research.ResearchPlanStepOperationResult import ResearchPlanStepOperationResult
from research.ResearchPlanStepStatus import ResearchPlanStepStatus
from tests.research.test_bounded_continuation import ContinuationFixture

SERVICE_SOURCE = (
    SRC_DIR / "cognition" / "ResearchPlanExecutionApplicationService.py"
).read_text(encoding="utf-8")


class GatedOperation:
    """Holds one step open until the test lets it finish."""

    operation_name = "gated_discovery"

    def __init__(self, *, gate_on: str = "step-1", fails: bool = False) -> None:
        self.calls: list[str] = []
        self.entered = Event()
        self.release = Event()
        self._gate_on = gate_on
        self._fails = fails

    def run(self, step, context) -> ResearchPlanStepOperationResult:
        self.calls.append(step.step_id)
        if step.step_id == self._gate_on:
            self.entered.set()
            self.release.wait(timeout=5)
        if self._fails:
            raise ResearchError("The provider refused this discovery.")
        return ResearchPlanStepOperationResult(
            performed=True, detail="Candidates recorded.", succeeded=True
        )


class ConcurrencyFixture(ContinuationFixture):
    """A live multi-step execution with one attempt held open mid-flight."""

    def _held(self, *, fails: bool = False, count: int = 3):
        """Start a continuation and wait until the provider is inside step-1."""
        self.gated = GatedOperation(fails=fails)
        service = self._multi_step(count=count, operation=self.gated)
        self.service_under_test = service
        self.spent_before = service.allowance("plan-many").remaining_network_operations
        self.outcome: dict[str, object] = {}
        self.worker = Thread(
            target=lambda: self.outcome.update(
                response=self._continue(service, "plan-many", count)
            )
        )
        self.worker.start()
        self.assertTrue(self.gated.entered.wait(timeout=5))
        return service

    def _cancel(self, service):
        return service.process_cancel(
            BrainRequest(
                message="Cancel",
                metadata={
                    "intent": "research_plan_execution_cancel",
                    "research_plan_id": "plan-many",
                },
            )
        )

    def _finish(self) -> None:
        self.gated.release.set()
        self.worker.join(timeout=10)
        self.assertFalse(self.worker.is_alive())

    def _durable(self):
        [snapshot] = [
            entry
            for entry in self.execution_store.load()
            if entry.plan_id == "plan-many"
        ]
        return snapshot

    def tearDown(self) -> None:
        gated = getattr(self, "gated", None)
        if gated is not None:
            gated.release.set()
        worker = getattr(self, "worker", None)
        if worker is not None:
            worker.join(timeout=10)
        super().tearDown()


class CancelDuringAnAttemptSurvivesTests(ConcurrencyFixture):
    """The race that was reproduced before this existed."""

    def test_cancelling_succeeds_while_the_provider_is_in_flight(self) -> None:
        service = self._held()

        cancelled = self._cancel(service)

        self.assertTrue(cancelled.success)
        self._finish()

    def test_the_cancellation_is_durable_before_the_provider_returns(self) -> None:
        service = self._held()

        self._cancel(service)

        self.assertIs(self._durable().status, ResearchPlanExecutionStatus.CANCELLED)
        self._finish()

    def test_a_returning_provider_cannot_overwrite_the_cancellation(self) -> None:
        service = self._held()
        self._cancel(service)

        self._finish()

        self.assertIs(
            service.live_execution("plan-many").status,
            ResearchPlanExecutionStatus.CANCELLED,
        )

    def test_the_durable_record_stays_cancelled_too(self) -> None:
        """Memory and disk must not disagree about what happened."""
        service = self._held()
        self._cancel(service)

        self._finish()

        self.assertIs(self._durable().status, ResearchPlanExecutionStatus.CANCELLED)

    def test_a_failing_provider_cannot_overwrite_it_either(self) -> None:
        """Protection on the success path alone would be no protection."""
        service = self._held(fails=True)
        self._cancel(service)

        self._finish()

        self.assertIs(
            service.live_execution("plan-many").status,
            ResearchPlanExecutionStatus.CANCELLED,
        )
        self.assertIs(self._durable().status, ResearchPlanExecutionStatus.CANCELLED)

    def test_no_later_step_starts(self) -> None:
        service = self._held()
        self._cancel(service)

        self._finish()

        self.assertEqual(self.gated.calls, ["step-1"])

    def test_the_continuation_stops_for_the_canonical_reason(self) -> None:
        service = self._held()
        self._cancel(service)

        self._finish()

        result = self.outcome["response"].research_execution_continuation
        self.assertIs(result.stop_reason, ResearchContinuationStopReason.CANCELLED)

    def test_nothing_is_retried(self) -> None:
        service = self._held(fails=True)
        self._cancel(service)

        self._finish()

        self.assertEqual(self.gated.calls.count("step-1"), 1)


class TheAttemptStaysPaidForTests(ConcurrencyFixture):
    def test_the_in_flight_attempt_remains_charged(self) -> None:
        """It reached out. A later decision elsewhere does not refund that."""
        service = self._held()
        self._cancel(service)

        self._finish()

        spent = (
            self.spent_before
            - service.allowance("plan-many").remaining_network_operations
        )
        self.assertEqual(spent, 1)

    def test_the_allowance_is_not_reset(self) -> None:
        service = self._held()
        self._cancel(service)

        self._finish()

        self.assertLess(
            service.allowance("plan-many").remaining_network_operations,
            self.spent_before,
        )

    def test_the_interrupted_step_is_not_reported_as_completed(self) -> None:
        service = self._held()
        self._cancel(service)

        self._finish()

        [step] = [
            entry
            for entry in service.live_execution("plan-many").steps
            if entry.step_id == "step-1"
        ]
        self.assertIsNot(step.status, ResearchPlanStepStatus.COMPLETED)


class NothingElseAboutTheExecutionMovedTests(ConcurrencyFixture):
    def test_the_plan_is_unchanged(self) -> None:
        service = self._held()
        before = service.live_plan("plan-many")
        self._cancel(service)

        self._finish()

        self.assertEqual(service.live_plan("plan-many"), before)

    def test_no_authorization_was_created(self) -> None:
        service = self._held()
        before = len(list(self.authorization_service.authorizations()))
        self._cancel(service)

        self._finish()

        self.assertEqual(len(list(self.authorization_service.authorizations())), before)


class TheUncontendedPathIsUnchangedTests(ConcurrencyFixture):
    """The common case must be exactly as it was."""

    def test_an_ordinary_advance_still_completes_its_step(self) -> None:
        service = self._held()

        self._finish()

        [step] = [
            entry
            for entry in service.live_execution("plan-many").steps
            if entry.step_id == "step-1"
        ]
        self.assertIs(step.status, ResearchPlanStepStatus.COMPLETED)

    def test_an_ordinary_provider_failure_is_still_recorded(self) -> None:
        service = self._held(fails=True)

        self._finish()

        [step] = [
            entry
            for entry in service.live_execution("plan-many").steps
            if entry.step_id == "step-1"
        ]
        self.assertIs(step.status, ResearchPlanStepStatus.FAILED)

    def test_an_uncontended_run_reaches_every_step(self) -> None:
        service = self._held(count=2)

        self._finish()

        self.assertEqual(self.gated.calls, ["step-1", "step-2"])
        self.assertIs(
            service.live_execution("plan-many").status,
            ResearchPlanExecutionStatus.COMPLETED,
        )

    def test_sequential_cancelling_still_behaves_as_before(self) -> None:
        """No in-flight attempt involved; the ordinary path is untouched."""
        service = self._multi_step(count=3)

        self._cancel(service)

        self.assertIs(
            service.live_execution("plan-many").status,
            ResearchPlanExecutionStatus.CANCELLED,
        )


class TheAttemptNeverStartsOnACancelledExecutionTests(ConcurrencyFixture):
    """The other side of the window: cancelling before the attempt commits."""

    def test_a_cancel_landing_first_stops_the_provider_being_reached(self) -> None:
        """Ordering A: the attempt stands down rather than starting anyway."""
        gated = GatedOperation()
        service = self._multi_step(count=3, operation=gated)
        original = service._commit_outcome
        cancelled_first: list[bool] = []

        def cancel_then_commit(plan_id, expected, successor):
            if not cancelled_first:
                cancelled_first.append(True)
                service.process_cancel(
                    BrainRequest(
                        message="Cancel",
                        metadata={
                            "intent": "research_plan_execution_cancel",
                            "research_plan_id": "plan-many",
                        },
                    )
                )
            return original(plan_id, expected, successor)

        service._commit_outcome = cancel_then_commit

        self._continue(service, "plan-many", 3)

        self.assertEqual(gated.calls, [])
        self.assertIs(
            service.live_execution("plan-many").status,
            ResearchPlanExecutionStatus.CANCELLED,
        )

    def test_a_cancel_landing_first_charges_nothing(self) -> None:
        gated = GatedOperation()
        service = self._multi_step(count=3, operation=gated)
        before = service.allowance("plan-many").remaining_network_operations
        original = service._commit_outcome
        once: list[bool] = []

        def cancel_then_commit(plan_id, expected, successor):
            if not once:
                once.append(True)
                service.process_cancel(
                    BrainRequest(
                        message="Cancel",
                        metadata={
                            "intent": "research_plan_execution_cancel",
                            "research_plan_id": "plan-many",
                        },
                    )
                )
            return original(plan_id, expected, successor)

        service._commit_outcome = cancel_then_commit

        self._continue(service, "plan-many", 3)

        self.assertEqual(
            service.allowance("plan-many").remaining_network_operations, before
        )


class OnlyOneAttemptCanStartTests(ConcurrencyFixture):
    """Two advances racing for the same execution cannot both reach a provider.

    Both threads read the same state, choose the same step and check the same
    budget. Serializing the attempt commit is what decides between them: the
    first commits its running state, the second finds the execution is no longer
    what it planned from and stands down without calling anybody.
    """

    def test_two_concurrent_advances_produce_one_provider_call(self) -> None:
        gated = GatedOperation()
        service = self._multi_step(count=3, operation=gated)
        started = Event()

        def advance():
            started.set()
            service.process_advance(
                BrainRequest(
                    message="Advance",
                    metadata={
                        "intent": "research_plan_execution_advance",
                        "research_plan_id": "plan-many",
                    },
                )
            )

        first = Thread(target=advance)
        second = Thread(target=advance)
        first.start()
        self.assertTrue(started.wait(timeout=5))
        second.start()
        try:
            self.assertTrue(gated.entered.wait(timeout=5))
            gated.release.set()
            first.join(timeout=10)
            second.join(timeout=10)

            self.assertEqual(gated.calls, ["step-1"])
        finally:
            gated.release.set()
            first.join(timeout=10)
            second.join(timeout=10)

    def test_the_step_is_charged_once(self) -> None:
        gated = GatedOperation()
        service = self._multi_step(count=3, operation=gated)
        before = service.allowance("plan-many").remaining_network_operations
        gated.release.set()

        threads = [
            Thread(
                target=lambda: service.process_advance(
                    BrainRequest(
                        message="Advance",
                        metadata={
                            "intent": "research_plan_execution_advance",
                            "research_plan_id": "plan-many",
                        },
                    )
                )
            )
            for _ in range(2)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        spent = before - service.allowance("plan-many").remaining_network_operations
        self.assertEqual(spent, len(gated.calls))


class TheDisciplineIsNarrowTests(unittest.TestCase):
    """How the fix is written matters as much as that it works."""

    def _advance_body(self) -> str:
        start = SERVICE_SOURCE.index("    def process_advance(")
        end = SERVICE_SOURCE.index("\n    def ", start + 1)
        return SERVICE_SOURCE[start:end]

    def test_no_lock_is_held_across_the_provider_call(self) -> None:
        body = self._advance_body()

        self.assertIn("operation.run(", body)
        self.assertNotIn("with self._commit_lock", body)

    def test_the_lock_guards_only_the_commit(self) -> None:
        start = SERVICE_SOURCE.index("    def _commit_outcome(")
        end = SERVICE_SOURCE.index("\n    def ", start + 1)
        body = SERVICE_SOURCE[start:end]

        self.assertIn("with self._commit_lock", body)
        self.assertNotIn("operation", body)

    def test_no_generic_field_wise_merge_exists(self) -> None:
        for forbidden in ("__dict__", "asdict(", "latest_non_null", "merge_state"):
            with self.subTest(name=forbidden):
                self.assertNotIn(forbidden, SERVICE_SOURCE)

    def test_every_post_provider_write_is_conditional(self) -> None:
        """A branch that still assigned directly would be an unguarded hole."""
        body = self._advance_body()
        after_provider = body[body.index("result = operation.run(") :]

        self.assertNotIn("self._executions[plan_id] =", after_provider)
        self.assertEqual(after_provider.count("_commit_outcome("), 3)

    def test_blocking_is_conditional_too(self) -> None:
        start = SERVICE_SOURCE.index("    def _blocked(")
        end = SERVICE_SOURCE.index("\n    def ", start + 1)
        body = SERVICE_SOURCE[start:end]

        self.assertIn("_commit_outcome(", body)
        self.assertNotIn("self._executions[plan_id] = blocked", body)

    def test_a_superseded_outcome_reports_the_state_that_stands(self) -> None:
        start = SERVICE_SOURCE.index("    def _superseded(")
        end = SERVICE_SOURCE.index("\n    def ", start + 1)
        body = SERVICE_SOURCE[start:end]

        self.assertIn("outcome_superseded", body)
        self.assertIn("self._persist(plan_id)", body)


if __name__ == "__main__":
    unittest.main()
