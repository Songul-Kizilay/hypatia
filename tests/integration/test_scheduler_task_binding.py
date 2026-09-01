"""A queued task must name an execution that exists and could still move.

Until v0.3.279 the scheduler wrote a durable task for any string at all. The
task sat PENDING, looked ordinary in the list, and only revealed itself when a
cycle spent a slot on it and autonomy answered that no such execution exists.
The same was true of an execution that had already completed, or one waiting on
a human to resolve an interrupted step: a task that could never run, recorded as
though it might.

So creation now reads the canonical execution and refuses when queueing would be
meaningless. What counts as meaningless is not a new opinion invented here — it
is the part of autonomy's own stop decision that depends on execution state
alone, extracted so both callers ask one question. A test below pins that: every
status these tests accept is a status autonomy can genuinely step from, and
every status refused is one it would immediately stop on.

Two things this validation is careful not to become. It is not a promise about
the future — an execution can finish or break after the task is queued, and that
stays the worker cycle's business against live state, so nothing is frozen into
the task. And it is not authority: reading an execution advances nothing,
consumes no approval, and touches no budget.

Real execution service, real scheduler, real task store. No network, no model,
no sleeps.
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
from cognition.BackgroundResearchSchedulerApplicationService import (
    BACKGROUND_TASK_CREATE_INTENT,
)
from research.ResearchAutonomyResult import AutonomyStopReason
from research.ResearchExecutionProgressBlock import progress_block
from research.ResearchPlanExecutionStatus import ResearchPlanExecutionStatus
from research.ResearchPlanStepStatus import ResearchPlanStepStatus
from tests.integration.test_operator_scheduler_cycle import SchedulerCycleFixture

SCHEDULER_SOURCE = (
    SRC_DIR / "cognition" / "BackgroundResearchSchedulerApplicationService.py"
).read_text(encoding="utf-8")
AUTONOMY_SOURCE = (
    SRC_DIR / "cognition" / "ResearchAutonomyApplicationService.py"
).read_text(encoding="utf-8")
PORT_SOURCE = (SRC_DIR / "research" / "ReadsResearchExecution.py").read_text(
    encoding="utf-8"
)
WINDOW_SOURCE = (SRC_DIR / "desktop" / "TkinterDesktopWindow.py").read_text(
    encoding="utf-8"
)
CONTROLLER_SOURCE = (SRC_DIR / "desktop" / "DesktopController.py").read_text(
    encoding="utf-8"
)


class BindingFixture(SchedulerCycleFixture):
    """One real execution named "plan-many", plus the real scheduler."""

    def _create(self, execution_id: str):
        return self.scheduler.process_create(
            BrainRequest(
                message="scheduler",
                metadata={
                    "intent": BACKGROUND_TASK_CREATE_INTENT,
                    "research_plan_id": execution_id,
                },
            )
        )

    def _live(self):
        state = self.execution.live_execution("plan-many")
        assert state is not None
        return state


class AnExistingExecutionCanBeQueuedTests(BindingFixture):
    def test_a_running_execution_is_accepted(self) -> None:
        response = self._create("plan-many")

        self.assertIsNotNone(response.background_research_task)

    def test_the_task_stores_the_exact_identity_submitted(self) -> None:
        self._create("plan-many")

        self.assertEqual(self._task().execution_id, "plan-many")

    def test_the_stored_identity_is_the_one_asked_for_not_the_first_found(
        self,
    ) -> None:
        """With one execution around, a substitution is invisible.

        Every other test here would pass if creation quietly bound to whatever
        execution the process happened to hold, because it holds exactly one.
        So this puts a second one ahead of it and asks for the later one by
        name.
        """
        from dataclasses import replace

        state = self._live()
        decoy = replace(state, plan_id="plan-decoy")
        self.execution._executions = {"plan-decoy": decoy, "plan-many": state}

        self._create("plan-many")

        self.assertEqual(self._task().execution_id, "plan-many")

    def test_acceptance_runs_no_research(self) -> None:
        self._create("plan-many")

        self.assertEqual(self.reopened_operation.calls, [])

    def test_an_accepted_execution_really_can_step(self) -> None:
        """The acceptance is not a guess: the very next cycle advances it."""
        self._create("plan-many")

        self._cycle()

        self.assertTrue(self.reopened_operation.calls)


class AnUnknownExecutionIsRefusedTests(BindingFixture):
    def test_an_unknown_identifier_creates_no_task(self) -> None:
        self._create("plan-nobody-started")

        self.assertEqual(self.scheduler.tasks(), ())

    def test_the_refusal_names_the_identifier_that_was_asked_for(self) -> None:
        response = self._create("plan-nobody-started")

        self.assertIn("Background research task rejected:", response.message)
        self.assertIn("plan-nobody-started", response.message)

    def test_a_refusal_writes_nothing_durable(self) -> None:
        self._create("plan-nobody-started")

        self.assertEqual(self.task_store.load(), [])

    def test_a_refusal_creates_no_execution(self) -> None:
        self._create("plan-nobody-started")

        self.assertIsNone(self.execution.live_execution("plan-nobody-started"))

    def test_a_refusal_reaches_no_provider(self) -> None:
        self._create("plan-nobody-started")

        self.assertEqual(self.reopened_operation.calls, [])

    def test_no_fallback_to_the_one_execution_that_does_exist(self) -> None:
        """The tempting bug: one live execution, so "obviously" they meant it."""
        self._create("plan-nobody-started")

        self.assertEqual(self.scheduler.tasks(), ())
        self.assertIsNot(
            self.execution.live_execution("plan-many"),
            None,
        )

    def test_a_near_miss_identifier_is_still_unknown(self) -> None:
        """Close is not equal. Nothing here resolves to the live execution."""
        for wrong in ("plan-man", "PLAN-MANY", "plan-many-2", "plan"):
            with self.subTest(name=wrong):
                self.scheduler._tasks.clear()

                self._create(wrong)

                self.assertEqual(self.scheduler.tasks(), ())

    def test_surrounding_space_resolves_to_the_same_exact_identity(self) -> None:
        """Trimming is the existing metadata rule, not a fuzzy match.

        ``_required_text`` already strips, and the stripped value is the exact
        identifier — so this is accepted, and what gets stored is the exact one.
        """
        self._create("  plan-many  ")

        self.assertEqual(self._task().execution_id, "plan-many")


class ADeadExecutionIsRefusedTests(BindingFixture):
    """Statuses no cycle could ever move, refused before a task exists."""

    def _close(self, status: ResearchPlanExecutionStatus) -> None:
        """Put the canonical execution into a legal terminal state.

        The state dataclass refuses incoherent combinations — it will not call
        an execution completed while steps are still pending — so each terminal
        case is built the way the domain would actually reach it.
        """
        from dataclasses import replace

        state = self._live()
        steps = state.steps
        if status is ResearchPlanExecutionStatus.COMPLETED:
            steps = tuple(
                replace(step, status=ResearchPlanStepStatus.COMPLETED)
                for step in state.steps
            )
        elif status is ResearchPlanExecutionStatus.FAILED:
            steps = tuple(
                (
                    replace(step, status=ResearchPlanStepStatus.FAILED)
                    if index == 0
                    else step
                )
                for index, step in enumerate(state.steps)
            )
        self.execution._executions["plan-many"] = replace(
            state, status=status, steps=steps
        )

    def test_terminal_executions_cannot_be_queued(self) -> None:
        for status in (
            ResearchPlanExecutionStatus.COMPLETED,
            ResearchPlanExecutionStatus.FAILED,
            ResearchPlanExecutionStatus.CANCELLED,
        ):
            with self.subTest(name=status.value):
                self.setUp()
                self._close(status)

                self._create("plan-many")

                self.assertEqual(self.scheduler.tasks(), ())

    def test_the_refusal_says_which_stop_reason_applies(self) -> None:
        self._close(ResearchPlanExecutionStatus.COMPLETED)

        response = self._create("plan-many")

        self.assertIn(AutonomyStopReason.EXECUTION_TERMINAL.value, response.message)

    def test_an_execution_awaiting_a_human_cannot_be_queued(self) -> None:
        """Interrupted and blocked steps need a person, not a cycle.

        Autonomy stops on them immediately, and the human action that clears
        them is an explicit ruling on the execution. Queueing one would record
        a task whose only possible outcome is to fail.
        """
        for step_status, reason in (
            (ResearchPlanStepStatus.INTERRUPTED, AutonomyStopReason.STEP_INTERRUPTED),
            (ResearchPlanStepStatus.BLOCKED, AutonomyStopReason.STEP_BLOCKED),
            (ResearchPlanStepStatus.FAILED, AutonomyStopReason.STEP_FAILED),
        ):
            with self.subTest(name=step_status.value):
                self.setUp()
                self._halt_first_step(step_status)

                response = self._create("plan-many")

                self.assertEqual(self.scheduler.tasks(), ())
                self.assertIn(reason.value, response.message)

    def _halt_first_step(self, step_status: ResearchPlanStepStatus) -> None:
        from dataclasses import replace

        state = self._live()
        steps = tuple(
            replace(step, status=step_status) if index == 0 else step
            for index, step in enumerate(state.steps)
        )
        self.execution._executions["plan-many"] = replace(state, steps=steps)

    def test_an_execution_with_nothing_left_to_do_is_refused(self) -> None:
        from dataclasses import replace

        state = self._live()
        steps = tuple(
            replace(step, status=ResearchPlanStepStatus.COMPLETED)
            for step in state.steps
        )
        self.execution._executions["plan-many"] = replace(state, steps=steps)

        response = self._create("plan-many")

        self.assertEqual(self.scheduler.tasks(), ())
        self.assertIn(AutonomyStopReason.NO_PENDING_STEP.value, response.message)


class TheEligibilityRuleIsAutonomysOwnTests(BindingFixture):
    """Accepted means "autonomy could step from here", not a second opinion."""

    def test_the_accepted_state_has_no_progress_block(self) -> None:
        self.assertIsNone(progress_block(self._live()))

    def test_every_refused_state_is_one_autonomy_stops_on(self) -> None:
        from dataclasses import replace

        state = self._live()
        cases = (
            replace(
                state,
                status=ResearchPlanExecutionStatus.COMPLETED,
                steps=tuple(
                    replace(step, status=ResearchPlanStepStatus.COMPLETED)
                    for step in state.steps
                ),
            ),
            replace(
                state,
                steps=tuple(
                    (
                        replace(step, status=ResearchPlanStepStatus.INTERRUPTED)
                        if index == 0
                        else step
                    )
                    for index, step in enumerate(state.steps)
                ),
            ),
        )
        for index, case in enumerate(cases):
            with self.subTest(name=index):
                self.assertIsNotNone(progress_block(case))

    def test_autonomy_asks_the_same_question(self) -> None:
        """One rule, one place. Two copies would drift, and one would decide."""
        self.assertIn("blocked = progress_block(state)", AUTONOMY_SOURCE)
        self.assertIn("progress_block(state)", SCHEDULER_SOURCE)

    def test_the_scheduler_reimplements_none_of_it(self) -> None:
        start = SCHEDULER_SOURCE.index("    def _binding_refusal(")
        body = SCHEDULER_SOURCE[start : SCHEDULER_SOURCE.index("\n    def ", start + 1)]

        for forbidden in (
            "ResearchPlanStepStatus",
            "ResearchPlanExecutionStatus",
            ".terminal",
            "next_pending_step_id",
        ):
            with self.subTest(name=forbidden):
                self.assertNotIn(forbidden, body)


class ValidationTakesNoAuthorityTests(BindingFixture):
    """Reading an execution to check it is not the same as touching it."""

    def test_creating_does_not_change_the_execution(self) -> None:
        before = self._live()

        self._create("plan-many")

        self.assertEqual(self._live(), before)

    def test_creating_does_not_consume_the_allowance(self) -> None:
        before = self.execution.allowance("plan-many")

        self._create("plan-many")

        self.assertEqual(self.execution.allowance("plan-many"), before)

    def test_creating_leaves_the_plan_and_its_steps_alone(self) -> None:
        before = self.execution.live_plan("plan-many")

        self._create("plan-many")

        self.assertEqual(self.execution.live_plan("plan-many"), before)

    def test_creating_grants_no_authorization(self) -> None:
        before = len(list(self.authorization_service.authorizations()))

        self._create("plan-many")

        self.assertEqual(len(list(self.authorization_service.authorizations())), before)

    def test_a_refused_create_changes_nothing_either(self) -> None:
        before = self._live()

        self._create("plan-nobody-started")

        self.assertEqual(self._live(), before)

    def test_creating_neither_starts_nor_advances(self) -> None:
        start = SCHEDULER_SOURCE.index("    def process_create(")
        create = SCHEDULER_SOURCE[
            start : SCHEDULER_SOURCE.index("\n    def ", start + 1)
        ]
        start = SCHEDULER_SOURCE.index("    def _binding_refusal(")
        checking = SCHEDULER_SOURCE[
            start : SCHEDULER_SOURCE.index("\n    def ", start + 1)
        ]

        for forbidden in (
            "process_advance",
            "process_run",
            "process_start",
            "_autonomy_service",
        ):
            with self.subTest(name=forbidden):
                self.assertNotIn(forbidden, create)
                self.assertNotIn(forbidden, checking)


class ThePortStaysReadOnlyTests(unittest.TestCase):
    """The scheduler gained a lookup, not the execution service."""

    def test_the_port_offers_only_a_read(self) -> None:
        methods = [
            line.strip()
            for line in PORT_SOURCE.splitlines()
            if line.strip().startswith("def ")
        ]

        self.assertEqual(len(methods), 1)
        self.assertTrue(methods[0].startswith("def live_execution("))

    def test_the_port_grants_no_mutation(self) -> None:
        """Read the declarations, not the prose.

        The docstring lists advancing, cancelling, authorizing and budgets as
        the powers this port deliberately withholds, so a scan of the whole
        file finds those words and fails on the sentence promising they are
        absent.
        """
        declarations = "\n".join(
            line
            for line in PORT_SOURCE.splitlines()
            if line.strip().startswith(("def ", "class ", "from ", "import "))
        )

        for forbidden in (
            "process_advance",
            "process_cancel",
            "process_start",
            "process_resolve",
            "process_recover",
            "authoriz",
            "budget",
        ):
            with self.subTest(name=forbidden):
                self.assertNotIn(forbidden, declarations)

    def test_the_scheduler_holds_the_port_not_the_service(self) -> None:
        self.assertIn("executions: ReadsResearchExecution", SCHEDULER_SOURCE)
        self.assertNotIn(
            "ResearchPlanExecutionApplicationService",
            SCHEDULER_SOURCE,
        )

    def test_the_scheduler_only_ever_reads(self) -> None:
        self.assertEqual(SCHEDULER_SOURCE.count("self._executions."), 1)
        self.assertIn("self._executions.live_execution(", SCHEDULER_SOURCE)


class TheDesktopDoesNotDuplicateThisTests(unittest.TestCase):
    """One validation, at the service, surfaced verbatim by the UI."""

    def test_the_desktop_reads_no_execution_state(self) -> None:
        for forbidden in (
            "live_execution",
            "progress_block",
            "ReadsResearchExecution",
            "ResearchPlanExecutionStatus",
        ):
            with self.subTest(name=forbidden):
                self.assertNotIn(forbidden, WINDOW_SOURCE)
                self.assertNotIn(forbidden, CONTROLLER_SOURCE)

    def test_the_controller_still_sends_the_same_create_intent(self) -> None:
        start = CONTROLLER_SOURCE.index("    def create_background_task(")
        body = CONTROLLER_SOURCE[
            start : CONTROLLER_SOURCE.index("\n    def ", start + 1)
        ]

        self.assertIn('"intent": "background_research_task_create"', body)
        self.assertIn('"research_plan_id": normalized', body)


class NothingWasFrozenIntoTheTaskTests(BindingFixture):
    """Validation says "meaningful when created", not "runnable forever"."""

    def test_the_task_records_no_execution_state(self) -> None:
        self._create("plan-many")
        task = self._task()

        for absent in ("status", "state", "steps"):
            with self.subTest(name=absent):
                self.assertFalse(
                    [
                        field
                        for field in task.__slots__
                        if absent in field and field != "status"
                    ]
                )

    def test_an_execution_that_dies_after_creation_still_queues(self) -> None:
        """The task stays; the cycle is what discovers the change."""
        from dataclasses import replace

        self._create("plan-many")
        state = self._live()
        self.execution._executions["plan-many"] = replace(
            state, status=ResearchPlanExecutionStatus.CANCELLED
        )

        self._cycle()

        self.assertEqual(self.reopened_operation.calls, [])
        self.assertEqual(len(self.scheduler.tasks()), 1)

    def test_the_cycle_still_decides_against_live_state(self) -> None:
        start = SCHEDULER_SOURCE.index("    def _run(")
        body = SCHEDULER_SOURCE[start : SCHEDULER_SOURCE.index("\n    def ", start + 1)]

        self.assertIn("self._autonomy_service.process_run(", body)
        self.assertNotIn("_binding_refusal", body)


class RestartKeepsTheExactBindingTests(BindingFixture):
    def test_a_rebuilt_scheduler_keeps_the_execution_identity(self) -> None:
        self._create("plan-many")

        rebuilt = self._scheduler()

        self.assertEqual(rebuilt.tasks()[0].execution_id, "plan-many")

    def test_rebuilding_revalidates_nothing_and_runs_nothing(self) -> None:
        self._create("plan-many")

        self._scheduler()

        self.assertEqual(self.reopened_operation.calls, [])

    def test_restore_performs_no_binding_check(self) -> None:
        """Startup stays inert: no cleanup, no repair, no cycle."""
        start = SCHEDULER_SOURCE.index("    def _restore(")
        body = SCHEDULER_SOURCE[start : SCHEDULER_SOURCE.index("\n    def ", start + 1)]

        for forbidden in ("_binding_refusal", "live_execution", "process_worker_cycle"):
            with self.subTest(name=forbidden):
                self.assertNotIn(forbidden, body)


class NoSchedulingMachineryWasAddedTests(unittest.TestCase):
    def test_no_timer_recurrence_or_startup_run(self) -> None:
        for forbidden in ("run_at", "Timer(", "sleep(", "threading", "recurrence"):
            with self.subTest(name=forbidden):
                self.assertNotIn(forbidden, SCHEDULER_SOURCE)

    def test_no_task_store_lock_was_introduced(self) -> None:
        """Deliberately still absent; it is the next prerequisite, not this one."""
        for forbidden in ("Lock(", "RLock("):
            with self.subTest(name=forbidden):
                self.assertNotIn(forbidden, SCHEDULER_SOURCE)


if __name__ == "__main__":
    unittest.main()
