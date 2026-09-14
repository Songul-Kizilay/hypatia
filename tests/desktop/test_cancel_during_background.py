"""Stopping a run you started, while it is still running.

Every desktop control is disabled while the one worker is busy, which is right
for anything that would start more work: a second request has nowhere to run.
It was wrong for exactly one control. Cancelling is how an operator stops a
continuation that is already going, and a stop button that only becomes
available once the thing has stopped is not a stop button.

So Cancel is now a control-plane action: not greyed out while the worker runs,
still going through the same canonical service, still synchronous, still on this
thread. Nothing about the runner changed and nothing else was let through — a
second continuation, an advance, a start, an approval all remain blocked, and a
test here checks that by identity rather than by hoping.

The safety of this rests on v0.3.272. A cancellation landing while a provider is
mid-call is preserved: the attempt's outcome is committed only if the execution
is still the one it started from, so the returning provider cannot undo the
cancellation and the next step never begins. That is proven here end to end,
gated on Events rather than timing, from the desktop control down to the durable
record.

The narrow commit window this file once documented is closed: every canonical
transition now takes the same lock, so a cancellation and an attempt outcome can
only happen one after the other. See `TheCommitWindowIsClosedTests`.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace
from unittest.mock import patch

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from brain.BrainRequest import BrainRequest
from research.ResearchPlanExecutionStatus import ResearchPlanExecutionStatus
from research.ResearchPlanStepOperationResult import ResearchPlanStepOperationResult
from tests.desktop.test_research_command_bindings import build_real_window
from tests.research.test_bounded_continuation import ContinuationFixture

WINDOW_SOURCE = (SRC_DIR / "desktop" / "TkinterDesktopWindow.py").read_text(
    encoding="utf-8"
)
SERVICE_SOURCE = (
    SRC_DIR / "cognition" / "ResearchPlanExecutionApplicationService.py"
).read_text(encoding="utf-8")


class TheStopControlStaysReachableTests(unittest.TestCase):
    """Which buttons the window disables while its worker is busy."""

    def setUp(self) -> None:
        self.window, self.widgets = build_real_window(
            plan_authorization_enabled=True, curiosity_enabled=True
        )

    def _button(self, label: str):
        [button] = [
            widget
            for widget in self.widgets
            if getattr(widget, "text", None) == label
            and getattr(widget, "command", None) is not None
        ]
        return button

    def test_cancelling_an_execution_is_a_control_plane_action(self) -> None:
        cancel = self._button("Cancel execution")

        self.assertIn(cancel, self.window._control_plane_controls)
        self.assertNotIn(cancel, self.window._request_controls)

    def test_everything_that_starts_work_is_still_disabled_when_busy(self) -> None:
        """The exemption is one button wide, checked by identity."""
        for label in (
            "Advance one step",
            "Continue bounded",
            "Continue in background",
            "Refresh status",
        ):
            with self.subTest(name=label):
                self.assertNotIn(
                    self._button(label), self.window._control_plane_controls
                )

    def test_only_the_stop_control_was_exempted(self) -> None:
        labels = {
            getattr(button, "text", None)
            for button in self.window._control_plane_controls
        }

        self.assertEqual(labels, {"Cancel execution"})

    def test_the_busy_switch_reaches_only_the_request_controls(self) -> None:
        """Asserted on the mechanism, because the harness records no widget state.

        The recorder answers any unknown attribute with a no-op, so watching for
        a disabled flag would watch nothing and pass for the wrong reason. What
        decides the outcome is which list the button is in and which list the
        busy switch walks, so that is what is checked.
        """
        start = WINDOW_SOURCE.index("    def _set_request_controls_busy(")
        end = WINDOW_SOURCE.index("\n    def ", start + 1)
        body = WINDOW_SOURCE[start:end]

        self.assertIn("for button in self._request_controls:", body)
        self.assertNotIn("_control_plane_controls", body)
        self.assertNotIn(
            self._button("Cancel execution"), self.window._request_controls
        )


class CancelDuringABackgroundRunTests(ContinuationFixture):
    """The whole path, from the desktop handler to the durable record."""

    def setUp(self) -> None:
        super().setUp()
        self.window, _widgets = build_real_window(
            plan_authorization_enabled=True, curiosity_enabled=True
        )
        self.statuses: list[str] = []
        self.window._plan_approval_status = SimpleNamespace(set=self.statuses.append)
        self.window._plan_approval_output = _Sink()
        self.window._append_response = lambda response: None

    def _held(self, count: int = 3):
        """Start a real continuation and wait until step-1 is in the provider."""
        self.gated = _GatedOperation()
        service = self._multi_step(count=count, operation=self.gated)
        self.service_under_test = service
        self.spent_before = service.allowance("plan-many").remaining_network_operations
        self.worker = Thread(target=lambda: self._continue(service, "plan-many", count))
        self.worker.start()
        self.assertTrue(self.gated.entered.wait(timeout=5))
        return service

    def _press_cancel(self, execution_id: str = "plan-many"):
        """Drive the real desktop handler, which is synchronous by design."""
        self.window._execution_id.set(execution_id)
        self.window._controller = SimpleNamespace(
            cancel_research_execution=lambda identity: (
                self.service_under_test.process_cancel(
                    BrainRequest(
                        message="Cancel",
                        metadata={
                            "intent": "research_plan_execution_cancel",
                            "research_plan_id": identity,
                        },
                    )
                )
            )
        )
        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=True
        ):
            self.window._cancel_execution()

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

    def test_the_cancel_returns_while_the_provider_is_still_gated(self) -> None:
        """The caller is not made to wait for the operation to come back."""
        self._held()

        self._press_cancel()

        self.assertFalse(self.gated.release.is_set())
        self.assertTrue(self.gated.entered.is_set())
        self._finish()

    def test_the_execution_is_cancelled_before_the_provider_returns(self) -> None:
        service = self._held()

        self._press_cancel()

        self.assertIs(
            service.live_execution("plan-many").status,
            ResearchPlanExecutionStatus.CANCELLED,
        )
        self._finish()

    def test_the_durable_record_is_cancelled_before_the_provider_returns(self) -> None:
        self._held()

        self._press_cancel()

        self.assertIs(self._durable().status, ResearchPlanExecutionStatus.CANCELLED)
        self._finish()

    def test_the_returning_provider_does_not_undo_it(self) -> None:
        service = self._held()
        self._press_cancel()

        self._finish()

        self.assertIs(
            service.live_execution("plan-many").status,
            ResearchPlanExecutionStatus.CANCELLED,
        )
        self.assertIs(self._durable().status, ResearchPlanExecutionStatus.CANCELLED)

    def test_no_later_step_ever_starts(self) -> None:
        self._held()
        self._press_cancel()

        self._finish()

        self.assertEqual(self.gated.calls, ["step-1"])

    def test_the_in_flight_attempt_stays_paid_for(self) -> None:
        service = self._held()
        self._press_cancel()

        self._finish()

        spent = (
            self.spent_before
            - service.allowance("plan-many").remaining_network_operations
        )
        self.assertEqual(spent, 1)

    def test_no_approval_is_created_by_cancelling(self) -> None:
        self._held()
        before = len(list(self.authorization_service.authorizations()))

        self._press_cancel()

        self.assertEqual(len(list(self.authorization_service.authorizations())), before)
        self._finish()

    def test_the_plan_is_untouched(self) -> None:
        service = self._held()
        before = service.live_plan("plan-many")

        self._press_cancel()

        self.assertEqual(service.live_plan("plan-many"), before)
        self._finish()

    def test_cancelling_a_different_execution_leaves_this_one_running(self) -> None:
        """Exact identity: the panel's id, never the busy worker's."""
        service = self._held()

        self._press_cancel(execution_id="some-other-execution")

        self.assertIs(
            service.live_execution("plan-many").status,
            ResearchPlanExecutionStatus.RUNNING,
        )
        self._finish()

    def test_a_missing_execution_id_refuses_without_cancelling(self) -> None:
        service = self._held()

        self._press_cancel(execution_id="   ")

        self.assertIs(
            service.live_execution("plan-many").status,
            ResearchPlanExecutionStatus.RUNNING,
        )
        self._finish()

    def test_cancelling_twice_is_harmless(self) -> None:
        service = self._held()
        self._press_cancel()

        self._press_cancel()

        self.assertIs(
            service.live_execution("plan-many").status,
            ResearchPlanExecutionStatus.CANCELLED,
        )
        self._finish()

    def test_the_status_line_reports_the_cancellation(self) -> None:
        self._held()

        self._press_cancel()

        self.assertTrue(self.statuses)
        self._finish()


class TheDesktopDoesNotTouchStateItselfTests(unittest.TestCase):
    """How the bypass is written, not only what it does."""

    def _handler(self) -> str:
        start = WINDOW_SOURCE.index("    def _cancel_execution(self)")
        end = WINDOW_SOURCE.index("\n    def ", start + 1)
        return WINDOW_SOURCE[start:end]

    def test_the_handler_goes_through_the_controller(self) -> None:
        body = self._handler()

        self.assertIn("self._controller.cancel_research_execution", body)

    def test_the_handler_touches_no_execution_state(self) -> None:
        body = self._handler()

        for forbidden in ("_executions", "_allowances", "execution_store", "process_"):
            with self.subTest(name=forbidden):
                self.assertNotIn(forbidden, body)

    def test_the_handler_starts_no_worker(self) -> None:
        body = self._handler()

        self.assertNotIn("_start_bounded_action", body)
        self.assertNotIn("_request_runner", body)

    def test_the_runner_was_not_made_concurrent(self) -> None:
        runner = (SRC_DIR / "desktop" / "DesktopRequestRunner.py").read_text(
            encoding="utf-8"
        )

        self.assertIn('"busy"', runner)
        for forbidden in ("bypass", "control_plane", "allow_concurrent"):
            with self.subTest(name=forbidden):
                self.assertNotIn(forbidden, runner)

    def test_no_cancellation_token_logic_reached_the_continuation(self) -> None:
        start = SERVICE_SOURCE.index("    def process_continue(")
        end = SERVICE_SOURCE.index("\n    def ", start + 1)
        body = SERVICE_SOURCE[start:end]

        self.assertNotIn("cancellation_token", body)
        self.assertNotIn("is_cancelled", body)


class TheCommitWindowIsClosedTests(ContinuationFixture):
    """The window v0.3.273 documented, now proven shut.

    Cancelling used to be able to land between the outcome commit's comparison
    and its write, and be overwritten. Both now take the same lock, so the two
    transitions can only happen one after the other. Either order is fine and
    the test allows both: what it refuses is the third outcome, where cancelling
    reports success and the execution ends up completed anyway.

    The cancel runs on its own thread precisely because it may now have to wait
    for the lock. Calling it from the test thread while the worker holds it
    would deadlock, which is itself a sign the serialization is real.
    """

    def test_cancelling_inside_the_commit_window_is_not_lost(self) -> None:
        gated = _GatedOperation()
        service = self._multi_step(count=3, operation=gated)
        worker_thread: dict[str, int] = {}
        inside_commit = Event()
        let_commit_finish = Event()

        class _WindowedExecutions(dict):
            """Hold the worker inside the commit, after its comparison passed."""

            def __setitem__(self, key, value):
                import threading

                if (
                    threading.get_ident() == worker_thread.get("id")
                    and getattr(value, "status", None)
                    is ResearchPlanExecutionStatus.RUNNING
                    and any(step.status.value == "completed" for step in value.steps)
                ):
                    inside_commit.set()
                    let_commit_finish.wait(timeout=5)
                super().__setitem__(key, value)

        import threading

        gated.on_enter = lambda: worker_thread.update(id=threading.get_ident())
        service._executions = _WindowedExecutions(service._executions)

        cancelled: dict[str, object] = {}
        worker = Thread(target=lambda: self._continue(service, "plan-many", 3))
        canceller = Thread(
            target=lambda: cancelled.update(
                response=service.process_cancel(
                    BrainRequest(
                        message="Cancel",
                        metadata={
                            "intent": "research_plan_execution_cancel",
                            "research_plan_id": "plan-many",
                        },
                    )
                )
            )
        )
        worker.start()
        try:
            self.assertTrue(gated.entered.wait(timeout=5))
            gated.release.set()
            self.assertTrue(inside_commit.wait(timeout=5))

            # Issued while the worker is provably inside the commit region.
            canceller.start()
            let_commit_finish.set()
            canceller.join(timeout=10)
            worker.join(timeout=10)

            self.assertFalse(canceller.is_alive())
            self.assertFalse(worker.is_alive())
            self.assertTrue(cancelled["response"].success)
            self.assertIs(
                service.live_execution("plan-many").status,
                ResearchPlanExecutionStatus.CANCELLED,
            )
        finally:
            gated.release.set()
            let_commit_finish.set()
            worker.join(timeout=10)
            if canceller.is_alive():
                canceller.join(timeout=10)

    def test_the_durable_record_agrees_after_the_window(self) -> None:
        """Live and durable must not disagree about a contended transition."""
        gated = _GatedOperation()
        service = self._multi_step(count=2, operation=gated)
        worker = Thread(target=lambda: self._continue(service, "plan-many", 2))
        worker.start()
        try:
            self.assertTrue(gated.entered.wait(timeout=5))
            service.process_cancel(
                BrainRequest(
                    message="Cancel",
                    metadata={
                        "intent": "research_plan_execution_cancel",
                        "research_plan_id": "plan-many",
                    },
                )
            )
            gated.release.set()
            worker.join(timeout=10)

            [snapshot] = [
                entry
                for entry in self.execution_store.load()
                if entry.plan_id == "plan-many"
            ]
            self.assertIs(
                service.live_execution("plan-many").status,
                ResearchPlanExecutionStatus.CANCELLED,
            )
            self.assertIs(snapshot.status, ResearchPlanExecutionStatus.CANCELLED)
        finally:
            gated.release.set()
            worker.join(timeout=10)


class _GatedOperation:
    """Holds step-1 open until released."""

    operation_name = "gated_discovery"

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.entered = Event()
        self.release = Event()
        self.on_enter = lambda: None

    def run(self, step, context) -> ResearchPlanStepOperationResult:
        self.calls.append(step.step_id)
        if step.step_id == "step-1":
            self.on_enter()
            self.entered.set()
            self.release.wait(timeout=5)
        return ResearchPlanStepOperationResult(
            performed=True, detail="Candidates recorded.", succeeded=True
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
