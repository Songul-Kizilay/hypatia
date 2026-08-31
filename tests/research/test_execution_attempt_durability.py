"""The moment an attempt stops being reversible, and what must already be true.

Calling a provider is the first thing in this chain that cannot be taken back.
Once the call leaves, something may have happened out there, and no amount of
local bookkeeping afterwards changes whether it did. So the record that the
attempt began — and the charge for it — must be on disk *before* the call, not
after it. A process that dies at the worst possible moment then leaves behind a
record that is merely incomplete, rather than one that is actively false.

The false version is the specific thing being prevented. A step left pending and
unspent after a crash reads as "this never ran", and the next advance would
believe it and run it again. That is why the interesting assertions here are
made from inside the fake provider: at the instant it is called, the durable
store is read and asked what it already says. Ordering claimed by reading code
is not ordering, and a test that checked afterwards could not tell the two
orders apart.

What survives a crash is deliberately not an answer. The step is interrupted and
its outcome unknown — not succeeded, not failed, not untried. Nothing here
retries it, nothing marks it, and an ordinary advance refuses to touch it and
says why. Deciding what actually happened is the operator's, and this milestone
stops at telling them the truth.

Crashes are simulated by raising an exception the service does not catch, which
is what a dying process looks like from inside a call. No network, no model, no
scheduler, nothing in the background.
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

from cognition.ResearchPlanExecutionApplicationService import (
    RESEARCH_PLAN_EXECUTION_STATUS_INTENT,
)
from research.ResearchCapabilityCost import cost_for
from research.ResearchPlanExecutionStatus import ResearchPlanExecutionStatus
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchPlanStepOperationResult import ResearchPlanStepOperationResult
from research.ResearchPlanStepStatus import ResearchPlanStepStatus
from tests.research.test_curiosity_execution_resume import ResumeFixture
from tests.SourceVocabulary import module_vocabulary

SERVICE_SOURCE = (
    SRC_DIR / "cognition" / "ResearchPlanExecutionApplicationService.py"
).read_text(encoding="utf-8")


class Crash(BaseException):
    """A process ending mid-call, which no `except ResearchError` will catch."""


class ObservingOperation:
    """A provider that reads the durable store at the instant it is called.

    The ordering this milestone is about can only be observed from here. Asked
    afterwards, a store that was written before the call and one written after
    it look identical; asked during, they do not.
    """

    operation_name = "observing_source_discovery"

    def __init__(self, store, *, crash: bool = False) -> None:
        self._store = store
        self._crash = crash
        self.calls: list[str] = []
        self.seen_status: list[str] = []
        self.seen_remaining: list[int] = []

    def run(self, step, context) -> ResearchPlanStepOperationResult:
        self.calls.append(step.step_id)
        for snapshot in self._store.load():
            for recorded in snapshot.steps:
                if recorded.step_id == step.step_id:
                    self.seen_status.append(recorded.status.value)
            if snapshot.allowance is not None:
                self.seen_remaining.append(
                    snapshot.allowance.remaining_network_operations
                )
        if self._crash:
            raise Crash("The process ended during the attempt.")
        return ResearchPlanStepOperationResult(
            performed=True, detail="Candidates recorded.", succeeded=True
        )


class AttemptDurabilityFixture(ResumeFixture):
    """The started chain, with a provider that watches the disk beneath it."""

    def _observing(self, *, crash: bool = False) -> ObservingOperation:
        operation = ObservingOperation(self.execution_store, crash=crash)
        self.operation = operation
        self.execution_service._operation_registry = self._registry(operation)
        return operation

    def _durable_step(self, execution_id: str, step_id: str = "step-1"):
        """Read one step back out of the store, as a new process would."""
        [snapshot] = [
            entry
            for entry in self.execution_store.load()
            if entry.plan_id == execution_id
        ]
        [step] = [entry for entry in snapshot.steps if entry.step_id == step_id]
        return snapshot, step

    def _status_request(self, execution_id: str):
        from brain.BrainRequest import BrainRequest

        return BrainRequest(
            message="Status",
            metadata={
                "intent": RESEARCH_PLAN_EXECUTION_STATUS_INTENT,
                "research_plan_id": execution_id,
            },
        )

    def _crashed(self):
        """Start, then die inside the provider. Returns the execution."""
        started = self._started()
        operation = self._observing(crash=True)
        with self.assertRaises(Crash):
            self._advance(started.plan_id)
        self.crashed_operation = operation
        return started


class AttemptIsDurableBeforeTheProviderTests(AttemptDurabilityFixture):
    def test_the_step_is_already_running_on_disk_when_the_provider_runs(self) -> None:
        started = self._started()
        operation = self._observing()

        self._advance(started.plan_id)

        self.assertEqual(operation.seen_status, ["running"])

    def test_the_attempt_is_already_charged_on_disk_when_the_provider_runs(
        self,
    ) -> None:
        started = self._started()
        fresh = self.execution_service.allowance(started.plan_id)
        operation = self._observing()

        self._advance(started.plan_id)

        self.assertEqual(len(operation.seen_remaining), 1)
        self.assertLess(operation.seen_remaining[0], fresh.remaining_network_operations)

    def test_affordability_is_settled_before_any_attempt_exists(self) -> None:
        """Refused with nothing charged, nothing running and nobody called."""
        started = self._started()
        operation = self._observing()
        allowance = self.execution_service.allowance(started.plan_id)
        cost = cost_for(ResearchPlanStepCapability.SOURCE_DISCOVERY)
        while allowance.affords(cost):
            allowance = allowance.charged(cost)
        self.execution_service._allowances[started.plan_id] = allowance

        self._advance(started.plan_id)

        _snapshot, step = self._durable_step(started.plan_id)
        self.assertEqual(operation.calls, [])
        self.assertIs(step.status, ResearchPlanStepStatus.PENDING)

    def test_a_failed_checkpoint_stops_before_the_provider(self) -> None:
        """A write that did not land is not a boundary anything may cross."""
        started = self._started()
        operation = self._observing()
        self.execution_service._execution_store = _RefusingStore(self.execution_store)

        response = self._advance(started.plan_id)

        self.assertEqual(operation.calls, [])
        self.assertIn("durably", response.message)


class CrashLeavesAnHonestRecordTests(AttemptDurabilityFixture):
    def test_a_crash_does_not_leave_the_step_pristine_pending(self) -> None:
        started = self._crashed()

        _snapshot, step = self._durable_step(started.plan_id)

        self.assertIsNot(step.status, ResearchPlanStepStatus.PENDING)

    def test_a_crashed_attempt_restores_as_interrupted(self) -> None:
        started = self._crashed()
        _curiosity, execution = self._restart()

        snapshot = execution.restored_execution(started.plan_id)

        [step] = snapshot.steps
        self.assertIs(step.status, ResearchPlanStepStatus.INTERRUPTED)
        self.assertIs(snapshot.status, ResearchPlanExecutionStatus.INTERRUPTED)

    def test_a_crash_does_not_refund_the_attempt(self) -> None:
        started = self._crashed()
        charged = self.execution_service.allowance(started.plan_id)

        snapshot, _step = self._durable_step(started.plan_id)

        self.assertEqual(
            snapshot.allowance.remaining_network_operations,
            charged.remaining_network_operations,
        )

    def test_the_outcome_is_not_recorded_as_success_or_failure(self) -> None:
        started = self._crashed()

        _snapshot, step = self._durable_step(started.plan_id)

        self.assertNotIn(
            step.status,
            (ResearchPlanStepStatus.COMPLETED, ResearchPlanStepStatus.FAILED),
        )

    def test_a_crash_after_the_provider_returned_is_still_unknown(self) -> None:
        """Boundary C: the call came back, the result never reached disk.

        The provider really did run, so the honest record is the same one a
        crash during the call leaves: attempted, charged, outcome unknown.
        """
        started = self._started()
        operation = self._observing()

        def die(*_arguments, **_keywords):
            raise Crash("The process ended before the result was written.")

        self.execution_service._charge_elapsed = die
        with self.assertRaises(Crash):
            self._advance(started.plan_id)

        _snapshot, step = self._durable_step(started.plan_id)
        self.assertEqual(operation.calls, ["step-1"])
        self.assertIs(step.status, ResearchPlanStepStatus.RUNNING)


class RestartTellsTheTruthTests(AttemptDurabilityFixture):
    def test_restarting_does_not_retry_the_provider(self) -> None:
        started = self._crashed()

        _curiosity, execution = self._restart()

        self.assertEqual(self.reopened_operation.calls, [])
        self.assertIsNone(execution.live_execution(started.plan_id))

    def test_resuming_an_interrupted_execution_performs_nothing(self) -> None:
        started = self._crashed()
        curiosity, execution = self._restart()

        self._resume(curiosity, started.plan_id)

        self.assertEqual(self.reopened_operation.calls, [])
        self.assertIsNotNone(execution.live_execution(started.plan_id))

    def test_resuming_restores_the_interrupted_step_not_a_pending_one(self) -> None:
        started = self._crashed()
        curiosity, execution = self._restart()

        self._resume(curiosity, started.plan_id)

        [step] = execution.live_execution(started.plan_id).steps
        self.assertIs(step.status, ResearchPlanStepStatus.INTERRUPTED)

    def test_resuming_refunds_nothing(self) -> None:
        started = self._crashed()
        charged = self.execution_service.allowance(started.plan_id)
        curiosity, execution = self._restart()

        self._resume(curiosity, started.plan_id)

        self.assertEqual(
            execution.allowance(started.plan_id).remaining_network_operations,
            charged.remaining_network_operations,
        )

    def test_resuming_does_not_charge_the_attempt_again(self) -> None:
        started = self._crashed()
        charged = self.execution_service.allowance(started.plan_id)
        curiosity, execution = self._restart()

        self._resume(curiosity, started.plan_id)
        second = execution.allowance(started.plan_id)

        self.assertEqual(second, charged)

    def test_advancing_an_interrupted_execution_refuses_and_says_why(self) -> None:
        started = self._crashed()
        curiosity, execution = self._restart()
        self._resume(curiosity, started.plan_id)

        response = self._advance_on(execution, started.plan_id)

        self.assertEqual(self.reopened_operation.calls, [])
        self.assertIn("interrupted", response.message.casefold())
        self.assertIn("unknown", response.message.casefold())

    def test_the_operator_is_told_the_attempt_was_already_charged(self) -> None:
        started = self._crashed()
        curiosity, execution = self._restart()
        self._resume(curiosity, started.plan_id)

        message = execution.process_status(
            self._status_request(started.plan_id)
        ).message

        self.assertIn("Attempt interrupted; outcome unknown", message)
        self.assertIn("will not run it again", message)


class UnchangedSemanticsTests(AttemptDurabilityFixture):
    def test_one_advance_still_performs_at_most_one_attempt(self) -> None:
        started = self._started()
        operation = self._observing()

        self._advance(started.plan_id)

        self.assertEqual(len(operation.calls), 1)

    def test_a_completed_step_is_still_completed(self) -> None:
        started = self._started()
        self._observing()

        self._advance(started.plan_id)

        _snapshot, step = self._durable_step(started.plan_id)
        self.assertIs(step.status, ResearchPlanStepStatus.COMPLETED)
        self.assertTrue(step.work_performed)

    def test_an_ordinary_provider_failure_is_still_a_failure(self) -> None:
        """A refusing provider fails the step, which is a known outcome."""
        started = self._started()
        self.execution_service._operation_registry = self._registry(
            _RefusingOperation()
        )

        self._advance(started.plan_id)

        _snapshot, step = self._durable_step(started.plan_id)
        self.assertIs(step.status, ResearchPlanStepStatus.FAILED)

    def test_cancelling_still_closes_the_execution(self) -> None:
        started = self._started()

        self._cancel(started.plan_id)

        snapshot, _step = self._durable_step(started.plan_id)
        self.assertIs(snapshot.status, ResearchPlanExecutionStatus.CANCELLED)

    def test_nothing_schedules_or_runs_in_the_background(self) -> None:
        vocabulary = module_vocabulary(SERVICE_SOURCE)

        for forbidden in (
            "thread",
            "sleep",
            "timer",
            "schedule",
            "asyncio",
            "daemon",
            "retry",
        ):
            with self.subTest(name=forbidden):
                self.assertEqual(
                    [word for word in vocabulary if forbidden in word.casefold()],
                    [],
                )

    def test_no_model_or_tool_is_reachable_from_the_attempt_path(self) -> None:
        vocabulary = module_vocabulary(SERVICE_SOURCE)

        for forbidden in ("ollama", "llm", "prompt", "subprocess", "shell"):
            with self.subTest(name=forbidden):
                self.assertEqual(
                    [word for word in vocabulary if forbidden in word.casefold()],
                    [],
                )


class _RefusingOperation:
    """A provider that fails in the ordinary, known way."""

    operation_name = "refusing_source_discovery"

    def run(self, step, context) -> ResearchPlanStepOperationResult:
        return ResearchPlanStepOperationResult(
            performed=True, detail="The provider refused.", succeeded=False
        )


class _RefusingStore:
    """A store that cannot be written to, standing in for a full or locked disk."""

    def __init__(self, delegate) -> None:
        self._delegate = delegate

    def load(self):
        return self._delegate.load()

    def save(self, snapshots) -> None:
        from core.Exceptions import ResearchError

        raise ResearchError("The execution store could not be written.")


if __name__ == "__main__":
    unittest.main()
