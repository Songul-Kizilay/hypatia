"""Running a bounded continuation off the window's thread, and nothing more.

"Background" here means one thing only: the Tk event loop is not the thread
waiting for the steps. It does not mean unattended, scheduled, recurring, or
autonomous. A person presses a button, names an execution, names a bound, and
what runs is the bounded continuation that already existed — the same loop over
the same one-step advance, with the same budget checks, the same durable
checkpoint and the same refusals.

Almost nothing was built for this. The worker is the single-flight desktop
runner the window already owns, which is also why two clicks cannot race: the
second is told Hypatia is busy. The loop is `process_continue`. The stopping
rules, the budget and the cancellation are the execution service's. What is new
is a control, a confirmation that says what is and is not being granted, and the
wiring between them.

So these tests are mostly about absence. No authorization is created, no budget
is reset or topped up, no plan or capability changes, nothing retries, nothing
relaunches after a restart, and no worker starts from preparing, approving or
starting a plan. The one positive claim — that the window stays usable while
steps run — is proven with a real thread and a deterministic gate rather than a
sleep.
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
from desktop.DesktopRequestRunner import DesktopRequestRunner
from research.ResearchContinuationStopReason import ResearchContinuationStopReason
from research.ResearchExecutionContinuation import (
    MAX_FOREGROUND_CONTINUATION_STEPS,
    ResearchExecutionContinuation,
)
from research.ResearchPlanExecutionStatus import ResearchPlanExecutionStatus
from tests.desktop.test_research_command_bindings import build_real_window

WINDOW_SOURCE = (SRC_DIR / "desktop" / "TkinterDesktopWindow.py").read_text(
    encoding="utf-8"
)


class BackgroundControlFixture(unittest.TestCase):
    """The real window, with the controller and worker observed."""

    def setUp(self) -> None:
        self.window, self.widgets = build_real_window(
            plan_authorization_enabled=True, curiosity_enabled=True
        )
        self.calls: list[tuple[str, str]] = []
        self.window._controller = SimpleNamespace(
            continue_research_execution=self._continue
        )
        self.started: list[tuple] = []
        self.window._start_bounded_action = self._start_bounded_action
        self.window._plan_approval_status = SimpleNamespace(set=self.status)
        self.statuses: list[str] = []

    def status(self, value: str) -> None:
        self.statuses.append(value)

    def _continue(self, execution_id: str, steps: str) -> BrainResponse:
        """Return a real response, so the handler's type guard is exercised."""
        self.calls.append((execution_id, steps))
        return BrainResponse(
            message="done",
            request_id="request-1",
            intent="research_plan_execution_continue",
            memory_count=0,
            research_execution_continuation=ResearchExecutionContinuation(
                execution_id=execution_id,
                requested_max_steps=int(steps),
                final_status=ResearchPlanExecutionStatus.RUNNING,
                stop_reason=ResearchContinuationStopReason.BOUND_REACHED,
                attempted_step_ids=("step-1",),
            ),
        )

    def _start_bounded_action(self, action, on_success, label, **kwargs):
        self.started.append((action, on_success, label, kwargs))
        return "started"

    def _prime(self, execution_id: str = "plan-1", steps: str = "2") -> None:
        self.window._execution_id.set(execution_id)
        self.window._continuation_steps.set(steps)

    def _press(self, confirm: bool = True):
        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=confirm
        ) as dialog:
            self.window._continue_execution_in_background()
        return dialog


class TheLaunchIsExplicitTests(BackgroundControlFixture):
    def test_one_press_reserves_the_one_worker(self) -> None:
        self._prime()

        self._press()

        self.assertEqual(len(self.started), 1)

    def test_the_worker_runs_the_named_execution_and_bound(self) -> None:
        self._prime(execution_id="plan-7", steps="3")

        self._press()

        action, _handler, _label, _kwargs = self.started[0]
        action()
        self.assertEqual(self.calls, [("plan-7", "3")])

    def test_declining_the_confirmation_starts_nothing(self) -> None:
        self._prime()

        self._press(confirm=False)

        self.assertEqual(self.started, [])

    def test_a_missing_execution_identity_starts_nothing(self) -> None:
        self._prime(execution_id="   ")

        dialog = self._press()

        dialog.assert_not_called()
        self.assertEqual(self.started, [])

    def test_a_missing_bound_starts_nothing(self) -> None:
        """There is no "as many as it takes" here either."""
        self._prime(steps="   ")

        dialog = self._press()

        dialog.assert_not_called()
        self.assertEqual(self.started, [])

    def test_the_confirmation_says_what_is_not_being_granted(self) -> None:
        self._prime()

        dialog = self._press()

        shown = dialog.call_args.args[1]
        self.assertIn("already granted", shown)
        self.assertIn("grants no", shown)
        self.assertIn("retries nothing", shown)
        self.assertIn("budget exhaustion", shown)

    def test_the_confirmation_promises_no_unattended_running(self) -> None:
        self._prime()

        dialog = self._press()

        shown = dialog.call_args.args[1].casefold()
        self.assertIn("not unattended", shown)
        self.assertIn("closing hypatia stops it", shown)
        for forbidden in ("overnight", "schedule", "recurring", "every day"):
            with self.subTest(name=forbidden):
                self.assertNotIn(forbidden, shown)

    def test_a_cancellation_signal_is_handed_to_the_worker(self) -> None:
        self._prime()

        self._press()

        _action, _handler, _label, kwargs = self.started[0]
        self.assertIsNotNone(kwargs.get("cancellation_signal"))


class TheResultIsReportedFromCanonicalStateTests(BackgroundControlFixture):
    def test_the_status_reports_attempted_against_requested(self) -> None:
        self._prime(steps="3")
        self._press()
        _action, handler, _label, _kwargs = self.started[0]

        handler(self._continue("plan-1", "3"))

        self.assertTrue(
            any("1 of 3 steps attempted" in status for status in self.statuses)
        )

    def test_the_status_reports_the_canonical_stop_reason(self) -> None:
        self._prime()
        self._press()
        _action, handler, _label, _kwargs = self.started[0]

        handler(self._continue("plan-1", "2"))

        self.assertTrue(any("bound_reached" in status for status in self.statuses))


class TheOneWorkerIsTheGuardTests(unittest.TestCase):
    """Two presses cannot race, because the runner admits one at a time."""

    def test_a_second_start_is_refused_while_one_runs(self) -> None:
        runner = DesktopRequestRunner()
        release = Event()
        entered = Event()

        def slow():
            entered.set()
            release.wait(timeout=5)
            return "done"

        try:
            self.assertEqual(runner.start(slow), "started")
            self.assertTrue(entered.wait(timeout=5))

            self.assertEqual(runner.start(lambda: "second"), "busy")
        finally:
            release.set()
            runner.stop()

    def test_the_worker_really_leaves_the_calling_thread_free(self) -> None:
        """The whole point: the window is usable while the steps run."""
        runner = DesktopRequestRunner()
        release = Event()
        entered = Event()

        def slow():
            entered.set()
            release.wait(timeout=5)
            return "done"

        try:
            runner.start(slow)

            # Reached only because the caller was never blocked by `slow`.
            self.assertTrue(entered.wait(timeout=5))
            self.assertTrue(runner.is_running())
        finally:
            release.set()
            runner.stop()

    def test_finishing_frees_the_worker_for_the_next_action(self) -> None:
        runner = DesktopRequestRunner()
        try:
            runner.start(lambda: "first")
            for _ in range(500):
                if not runner.is_running():
                    break
            list(runner.drain())

            self.assertEqual(runner.start(lambda: "second"), "started")
        finally:
            runner.stop()

    def test_a_stopped_runner_starts_nothing(self) -> None:
        runner = DesktopRequestRunner()
        runner.stop()

        self.assertEqual(runner.start(lambda: "anything"), "stopped")


class NothingElseLaunchesAWorkerTests(unittest.TestCase):
    """Preparing, approving and starting a plan remain entirely inert."""

    def _handler_body(self, name: str) -> str:
        start = WINDOW_SOURCE.index(f"    def {name}(self)")
        end = WINDOW_SOURCE.index("\n    def ", start + 1)
        return WINDOW_SOURCE[start:end]

    def test_preparing_a_proposal_starts_no_worker(self) -> None:
        self.assertNotIn(
            "_start_bounded_action",
            self._handler_body("_prepare_curiosity_research_proposal"),
        )

    def test_authorizing_starts_no_worker(self) -> None:
        self.assertNotIn(
            "_start_bounded_action",
            self._handler_body("_authorize_curiosity_research_proposal"),
        )

    def test_starting_an_execution_starts_no_worker(self) -> None:
        self.assertNotIn(
            "_start_bounded_action",
            self._handler_body("_start_authorized_curiosity_research_proposal"),
        )

    def test_only_the_background_control_reserves_the_worker_here(self) -> None:
        body = self._handler_body("_continue_execution_in_background")

        self.assertIn("_start_bounded_action", body)
        self.assertNotIn(
            "_start_bounded_action",
            self._handler_body("_continue_execution_bounded"),
        )


class NoSchedulingWasAddedTests(unittest.TestCase):
    """The worker is plumbing. It decides nothing about what to research."""

    def test_the_background_handler_starts_no_loop_of_its_own(self) -> None:
        """Structural, not textual: prose about waiting is not a loop.

        Matched at the start of a statement rather than anywhere in the text,
        because the confirmation this handler shows says the window stays
        usable "while they run" — a substring check would read that sentence as
        a loop and pass or fail for the wrong reason.
        """
        start = WINDOW_SOURCE.index("    def _continue_execution_in_background")
        end = WINDOW_SOURCE.index("\n    def ", start + 1)
        statements = [line.strip() for line in WINDOW_SOURCE[start:end].splitlines()]

        for keyword in ("while ", "for ", "async "):
            with self.subTest(name=keyword):
                self.assertEqual(
                    [line for line in statements if line.startswith(keyword)], []
                )
        for spawned in ("Thread(", ".after(", "sleep("):
            with self.subTest(name=spawned):
                self.assertEqual([line for line in statements if spawned in line], [])

    def test_it_delegates_the_stepping_to_the_canonical_continuation(self) -> None:
        start = WINDOW_SOURCE.index("    def _continue_execution_in_background")
        end = WINDOW_SOURCE.index("\n    def ", start + 1)
        body = WINDOW_SOURCE[start:end]

        self.assertIn("continue_research_execution", body)
        self.assertNotIn("process_advance", body)

    def test_the_bound_remains_the_canonical_one(self) -> None:
        """No separate, larger background ceiling was introduced."""
        self.assertEqual(MAX_FOREGROUND_CONTINUATION_STEPS, 10)
        self.assertNotIn("MAX_BACKGROUND", WINDOW_SOURCE)

    def test_no_relaunch_machinery_exists(self) -> None:
        """Nothing picks a stopped background run back up by itself.

        "resume_background" was on this list as a stand-in for that, from when
        nothing of the sort existed under any name. v0.3.278 added
        ``resume_background_task``, which is an operator pressing Resume on a
        named queue entry and runs nothing — so the guard now names the
        automatic kind directly rather than tripping on the explicit one.
        """
        for forbidden in (
            "auto_relaunch",
            "resume_background_continuation",
            "resume_background_run",
            "resume_background_worker",
            "restart_worker",
            "overnight",
        ):
            with self.subTest(name=forbidden):
                self.assertNotIn(forbidden, WINDOW_SOURCE.casefold())


if __name__ == "__main__":
    unittest.main()
