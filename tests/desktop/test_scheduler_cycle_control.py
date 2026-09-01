"""Letting a person take the scheduler's one turn, and nothing more.

The scheduler already existed, wired and durable, with queueing, pausing and a
worker cycle bounded to one task by default. What it never had was a way for
anybody to run that cycle: it is synchronous and demand-driven, with no thread,
no timer and no loop, so without a caller it simply never turned.

This is that caller and only that. The desktop reserves the one worker it
already owns, asks the existing service to take a turn, and shows what it
reported. It does not read the queue, choose a task, advance a step or invent a
status — a test here reads the handler and checks it mentions none of that
machinery, because the temptation in a UI is always to do the work itself.

One press is one cycle. Nothing schedules a second, nothing repeats, nothing
starts at launch, and a restart brings back the durable tasks without running
any of them. The scheduler's own bound decides how much a turn covers; the
desktop supplies no number of its own.

Failure semantics are the scheduler's and are left alone. Only running out of a
run's own allotment returns a task to the queue — a failure, block,
interruption or cancellation ends it, so no provider attempt is ever repeated.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import patch

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from brain.BrainResponse import BrainResponse
from cognition.BackgroundResearchSchedulerApplicationService import (
    DEFAULT_MAX_TASKS_PER_CYCLE,
    MAX_TASKS_PER_CYCLE_CEILING,
)
from desktop.DesktopRequestRunner import DesktopRequestRunner
from research.BackgroundTaskOutcome import BackgroundTaskOutcome
from tests.desktop.test_research_command_bindings import build_real_window

WINDOW_SOURCE = (SRC_DIR / "desktop" / "TkinterDesktopWindow.py").read_text(
    encoding="utf-8"
)
CONTROLLER_SOURCE = (SRC_DIR / "desktop" / "DesktopController.py").read_text(
    encoding="utf-8"
)
SCHEDULER_SOURCE = (
    SRC_DIR / "cognition" / "BackgroundResearchSchedulerApplicationService.py"
).read_text(encoding="utf-8")


class SchedulerControlFixture(unittest.TestCase):
    """The real window, with the worker and controller observed."""

    def setUp(self) -> None:
        self.window, self.widgets = build_real_window(
            plan_authorization_enabled=True, curiosity_enabled=True
        )
        self.cycles: list[str] = []
        self.window._controller = SimpleNamespace(
            run_background_scheduler_cycle=self._cycle
        )
        self.started: list[tuple] = []
        self.window._start_bounded_action = self._start_bounded_action
        self.statuses: list[str] = []
        self.window._plan_approval_status = SimpleNamespace(set=self.statuses.append)
        self.window._plan_approval_output = _Sink()
        self.window._append_response = lambda response: None

    def _cycle(self) -> BrainResponse:
        self.cycles.append("ran")
        return BrainResponse(
            message="Background worker cycle:\nTasks run this cycle: 1",
            request_id="request-1",
            intent="background_research_task",
            memory_count=0,
        )

    def _start_bounded_action(self, action, on_success, label, **kwargs):
        self.started.append((action, on_success, label, kwargs))
        return "started"

    def _press(self, confirm: bool = True):
        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=confirm
        ) as dialog:
            self.window._run_scheduler_cycle()
        return dialog


class OnePressIsOneCycleTests(SchedulerControlFixture):
    def test_pressing_reserves_the_one_worker(self) -> None:
        self._press()

        self.assertEqual(len(self.started), 1)

    def test_pressing_runs_the_cycle_exactly_once(self) -> None:
        self._press()
        action, _handler, _label, _kwargs = self.started[0]

        action()

        self.assertEqual(self.cycles, ["ran"])

    def test_declining_runs_nothing(self) -> None:
        self._press(confirm=False)

        self.assertEqual(self.started, [])
        self.assertEqual(self.cycles, [])

    def test_no_press_runs_nothing(self) -> None:
        """Building the window is not a reason for the scheduler to turn."""
        self.assertEqual(self.started, [])
        self.assertEqual(self.cycles, [])

    def test_finishing_does_not_start_another(self) -> None:
        self._press()
        _action, handler, _label, _kwargs = self.started[0]

        handler(self._cycle())

        self.assertEqual(len(self.started), 1)
        self.assertTrue(
            any("needs another press" in status for status in self.statuses)
        )

    def test_the_confirmation_promises_no_repetition(self) -> None:
        dialog = self._press()

        shown = dialog.call_args.args[1].casefold()
        self.assertIn("one bounded background research cycle", shown)
        self.assertIn("does not repeat", shown)
        self.assertIn("never starts on its own", shown)
        self.assertIn("nothing is approved, enlarged or retried here", shown)

    def test_the_confirmation_offers_no_schedule(self) -> None:
        """Words that would only appear if a schedule were being configured.

        Not a blanket word ban: the dialog says "every cycle is a press of this
        button", which is a promise there is no schedule, and a check tripping
        on it would be reading the sentence backwards.
        """
        shown = self._press().call_args.args[1].casefold()

        for forbidden in (
            "overnight",
            "recurring",
            "continuously",
            "repeat automatically",
            "run until",
        ):
            with self.subTest(name=forbidden):
                self.assertNotIn(forbidden, shown)


class TheDesktopDoesNoSchedulingTests(unittest.TestCase):
    """The UI asks; the service decides."""

    def _handler(self, *, code_only: bool = False) -> str:
        """Return the handler, optionally past its docstring.

        That docstring explains the desktop does not read the task queue, so a
        check for queue vocabulary has to look at the code — otherwise it finds
        the sentence denying it and fails for the opposite reason.
        """
        start = WINDOW_SOURCE.index("    def _run_scheduler_cycle(self)")
        end = WINDOW_SOURCE.index("\n    def ", start + 1)
        body = WINDOW_SOURCE[start:end]
        if not code_only:
            return body
        return body[body.index('"""', body.index('"""') + 3) + 3 :]

    def test_the_handler_selects_no_task(self) -> None:
        code = self._handler(code_only=True)

        for forbidden in ("_tasks", "pending", "queue", "next_runnable", "task_id"):
            with self.subTest(name=forbidden):
                self.assertNotIn(forbidden, code.casefold())

    def test_the_handler_advances_nothing_itself(self) -> None:
        body = self._handler(code_only=True)

        for forbidden in ("process_advance", "process_continue", "autonomy"):
            with self.subTest(name=forbidden):
                self.assertNotIn(forbidden, body)

    def test_the_handler_runs_no_loop_and_sets_no_timer(self) -> None:
        statements = [line.strip() for line in self._handler().splitlines()]

        for keyword in ("while ", "for "):
            with self.subTest(name=keyword):
                self.assertEqual(
                    [line for line in statements if line.startswith(keyword)], []
                )
        for spawned in ("Thread(", ".after(", "sleep("):
            with self.subTest(name=spawned):
                self.assertEqual([line for line in statements if spawned in line], [])

    def test_the_controller_only_sends_the_existing_intent(self) -> None:
        start = CONTROLLER_SOURCE.index("    def run_background_scheduler_cycle(")
        end = CONTROLLER_SOURCE.index("\n    def ", start + 1)
        body = CONTROLLER_SOURCE[start:end]

        self.assertIn('"intent": "background_research_worker_cycle"', body)
        for forbidden in ("budget", "authorization", "task_id", "max_"):
            with self.subTest(name=forbidden):
                self.assertNotIn(forbidden, body)

    def test_no_second_scheduler_was_written(self) -> None:
        for forbidden in ("_next_runnable", "BackgroundResearchTask", "retry"):
            with self.subTest(name=forbidden):
                self.assertNotIn(forbidden, WINDOW_SOURCE)
                self.assertNotIn(forbidden, CONTROLLER_SOURCE)


class TheCycleIsBoundedByTheServiceTests(unittest.TestCase):
    """The bound is the scheduler's, and the desktop supplies none."""

    def test_one_cycle_runs_a_finite_number_of_tasks(self) -> None:
        self.assertEqual(DEFAULT_MAX_TASKS_PER_CYCLE, 1)
        self.assertLessEqual(DEFAULT_MAX_TASKS_PER_CYCLE, MAX_TASKS_PER_CYCLE_CEILING)

    def test_the_cycle_loops_only_over_that_bound(self) -> None:
        start = SCHEDULER_SOURCE.index("    def process_worker_cycle(")
        end = SCHEDULER_SOURCE.index("\n    def ", start + 1)
        body = SCHEDULER_SOURCE[start:end]

        self.assertIn("for _ in range(self._max_tasks_per_cycle):", body)
        self.assertNotIn("while ", body)

    def test_the_desktop_names_no_bound_of_its_own(self) -> None:
        start = CONTROLLER_SOURCE.index("    def run_background_scheduler_cycle(")
        end = CONTROLLER_SOURCE.index("\n    def ", start + 1)

        self.assertNotIn("max_tasks", CONTROLLER_SOURCE[start:end])


class OnlyRunningOutIsRequeuedTests(unittest.TestCase):
    """A failed attempt is never repeated; an unfinished one may continue."""

    def test_only_budget_exhaustion_is_retryable(self) -> None:
        retryable = [outcome for outcome in BackgroundTaskOutcome if outcome.retryable]

        self.assertEqual(retryable, [BackgroundTaskOutcome.RETRYABLE_BUDGET_EXHAUSTED])

    def test_failure_block_interruption_and_cancel_end_the_task(self) -> None:
        for outcome in (
            BackgroundTaskOutcome.FAILED,
            BackgroundTaskOutcome.BLOCKED,
            BackgroundTaskOutcome.INTERRUPTED,
            BackgroundTaskOutcome.CANCELLED,
        ):
            with self.subTest(name=outcome.value):
                self.assertFalse(outcome.retryable)

    def test_completion_is_not_retryable(self) -> None:
        self.assertFalse(BackgroundTaskOutcome.COMPLETED.retryable)


class TheOneWorkerStillGuardsEverythingTests(unittest.TestCase):
    """A cycle occupies the same single-flight worker as any other action."""

    def test_a_second_cycle_cannot_start_while_one_runs(self) -> None:
        runner = DesktopRequestRunner()
        entered = Event()
        release = Event()

        def slow():
            entered.set()
            release.wait(timeout=5)
            return "done"

        try:
            self.assertEqual(runner.start(slow), "started")
            self.assertTrue(entered.wait(timeout=5))

            self.assertEqual(runner.start(lambda: "second cycle"), "busy")
        finally:
            release.set()
            runner.stop()

    def test_the_caller_is_not_blocked_by_the_cycle(self) -> None:
        runner = DesktopRequestRunner()
        entered = Event()
        release = Event()

        def slow():
            entered.set()
            release.wait(timeout=5)
            return "done"

        try:
            runner.start(slow)

            self.assertTrue(entered.wait(timeout=5))
            self.assertTrue(runner.is_running())
        finally:
            release.set()
            runner.stop()

    def test_the_worker_frees_after_the_cycle(self) -> None:
        runner = DesktopRequestRunner()
        try:
            runner.start(lambda: "cycle")
            for _ in range(500):
                if not runner.is_running():
                    break
            list(runner.drain())

            self.assertEqual(runner.start(lambda: "next"), "started")
        finally:
            runner.stop()


class NothingSchedulesItselfTests(unittest.TestCase):
    """No timer, no recurrence, no start-up turn."""

    def test_the_scheduler_has_no_timer_or_polling_loop(self) -> None:
        for forbidden in ("threading", "Timer(", "sleep(", "schedule_every"):
            with self.subTest(name=forbidden):
                self.assertNotIn(forbidden, SCHEDULER_SOURCE)

    def test_nothing_runs_a_cycle_at_startup(self) -> None:
        bootstrap = (SRC_DIR / "core" / "Bootstrap.py").read_text("utf-8")
        engine = (SRC_DIR / "cognition" / "CognitiveEngine.py").read_text("utf-8")

        for source in (bootstrap, engine):
            self.assertNotIn("process_worker_cycle()", source)

    def test_the_engine_only_runs_a_cycle_when_asked(self) -> None:
        engine = (SRC_DIR / "cognition" / "CognitiveEngine.py").read_text("utf-8")

        self.assertIn(
            "if scheduler.is_worker_cycle_request(request):\n"
            "            return scheduler.process_worker_cycle(request)",
            engine,
        )

    def test_only_one_control_runs_a_cycle(self) -> None:
        _window, widgets = build_real_window(plan_authorization_enabled=True)
        labels = [
            widget.text
            for widget in widgets
            if getattr(widget, "command", None) is not None
            and isinstance(getattr(widget, "text", None), str)
        ]

        self.assertEqual(
            [label for label in labels if "scheduler" in label.casefold()],
            ["Run scheduler cycle"],
        )


class _Sink:
    """Stands in for the panel's text widget."""

    def configure(self, **_kwargs) -> None:
        return None

    def delete(self, *_args) -> None:
        return None

    def insert(self, *_args) -> None:
        return None


if __name__ == "__main__":
    unittest.main()
