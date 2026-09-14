"""Handing the operator the queue the scheduler already kept.

Everything below the surface was there: a durable task store, five routed
intents, and a worker cycle that turns only when somebody presses. The queue was
simply invisible, which meant the one press added in the previous milestone was
aimed at a list nobody could see, add to, or hold back.

So this is a window onto that store and nothing more. Creating queues one exact
execution and runs no research; listing reads and selects nothing; pause, resume
and cancel send one task identity to the service and let the domain decide
whether the move is legal. No task record is built here, no status is inferred,
and no eligibility is second-guessed in the UI — when the scheduler refuses, the
refusal is what the operator sees.

Two identities are in play and the tests keep them apart. A task is what the
queue holds; an execution is what research runs on. Pause, resume and cancel act
on the task ID. Cancelling a task stops the scheduler choosing it and leaves the
execution exactly as it was — stopping that is still the separate execution
control, and confusing the two would quietly stop the wrong thing.

Deterministic fakes throughout. No network, no model, no sleeps, no timers.
"""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from cognition.BackgroundResearchSchedulerApplicationService import (
    BACKGROUND_TASK_CANCEL_INTENT,
    BACKGROUND_TASK_CREATE_INTENT,
    BACKGROUND_TASK_LIST_INTENT,
    BACKGROUND_TASK_PAUSE_INTENT,
    BACKGROUND_TASK_RESUME_INTENT,
)
from desktop.DesktopController import DesktopController
from tests.desktop.test_research_command_bindings import build_real_window

WINDOW_SOURCE = (SRC_DIR / "desktop" / "TkinterDesktopWindow.py").read_text(
    encoding="utf-8"
)
CONTROLLER_SOURCE = (SRC_DIR / "desktop" / "DesktopController.py").read_text(
    encoding="utf-8"
)

QUEUE_METHODS = (
    "create_background_task",
    "list_background_tasks",
    "pause_background_task",
    "resume_background_task",
    "cancel_background_task",
)


def _method(source: str, name: str, *, code_only: bool) -> str:
    """Return one method's source, optionally past its docstring.

    ``code_only`` matters more than it looks. These docstrings exist to say what
    the method does *not* do — grant authority, read a status, run research — so
    a vocabulary check run across the prose finds the denial and fails for
    exactly the reason the denial was written. The check has to read the code.
    """
    start = source.index(f"    def {name}(")
    body = source[start : source.index("\n    def ", start + 1)]
    if not code_only:
        return body
    opening = body.find('"""')
    if opening == -1:
        return body
    return body[body.index('"""', opening + 3) + 3 :]


def controller_method(name: str, *, code_only: bool = False) -> str:
    return _method(CONTROLLER_SOURCE, name, code_only=code_only)


def window_method(name: str, *, code_only: bool = False) -> str:
    return _method(WINDOW_SOURCE, name, code_only=code_only)


class RecordingBrain:
    """Accepts requests and answers with a fixed, inspectable response."""

    def __init__(self, response: BrainResponse | None = None) -> None:
        self.requests: list[BrainRequest] = []
        self._response = response or BrainResponse(
            message="queue",
            request_id="request-1",
            intent="background_research_task",
            memory_count=0,
        )

    def process(self, request: BrainRequest) -> BrainResponse:
        self.requests.append(request)
        return self._response

    @property
    def metadata(self) -> dict[str, object]:
        [request] = self.requests
        return dict(request.metadata)


class ControllerFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.brain = RecordingBrain()
        self.controller = DesktopController(self.brain)


class TheControllerUsesTheExistingIntentsTests(ControllerFixture):
    """Five controls, five intents that already existed and already route."""

    def test_creating_sends_the_canonical_create_intent(self) -> None:
        self.controller.create_background_task("plan-1")

        self.assertEqual(self.brain.metadata["intent"], BACKGROUND_TASK_CREATE_INTENT)

    def test_creating_names_the_exact_execution(self) -> None:
        self.controller.create_background_task("plan-1")

        self.assertEqual(self.brain.metadata["research_plan_id"], "plan-1")

    def test_listing_sends_the_canonical_list_intent(self) -> None:
        self.controller.list_background_tasks()

        self.assertEqual(self.brain.metadata["intent"], BACKGROUND_TASK_LIST_INTENT)

    def test_pause_resume_and_cancel_send_their_own_intents(self) -> None:
        expected = {
            "pause_background_task": BACKGROUND_TASK_PAUSE_INTENT,
            "resume_background_task": BACKGROUND_TASK_RESUME_INTENT,
            "cancel_background_task": BACKGROUND_TASK_CANCEL_INTENT,
        }
        for name, intent in expected.items():
            with self.subTest(name=name):
                brain = RecordingBrain()

                getattr(DesktopController(brain), name)("task-1")

                self.assertEqual(brain.metadata["intent"], intent)

    def test_every_control_goes_through_the_brain(self) -> None:
        """Three of the five send through one shared helper.

        So the helper is what has to reach the brain on their behalf, and
        checking each method for the call directly would only prove they do
        not share one.
        """
        for name in QUEUE_METHODS:
            with self.subTest(name=name):
                body = controller_method(name, code_only=True)

                self.assertTrue(
                    "self._brain.process(" in body
                    or "self._background_task_ruling(" in body
                )

        self.assertIn(
            "self._brain.process(",
            controller_method("_background_task_ruling", code_only=True),
        )

    def test_no_control_holds_the_scheduler_service(self) -> None:
        for name in (*QUEUE_METHODS, "_background_task_ruling"):
            with self.subTest(name=name):
                body = controller_method(name, code_only=True)

                for forbidden in ("self._scheduler", "task_store", "self._tasks"):
                    self.assertNotIn(forbidden, body)


class TheTwoIdentitiesStayApartTests(ControllerFixture):
    """A task is not an execution, and neither field may stand in for the other."""

    def test_pause_resume_and_cancel_send_a_task_identity(self) -> None:
        for name in (
            "pause_background_task",
            "resume_background_task",
            "cancel_background_task",
        ):
            with self.subTest(name=name):
                brain = RecordingBrain()

                getattr(DesktopController(brain), name)("task-7")

                self.assertEqual(brain.metadata["background_task_id"], "task-7")

    def test_pause_resume_and_cancel_send_no_execution_identity(self) -> None:
        for name in (
            "pause_background_task",
            "resume_background_task",
            "cancel_background_task",
        ):
            with self.subTest(name=name):
                brain = RecordingBrain()

                getattr(DesktopController(brain), name)("task-7")

                self.assertNotIn("research_plan_id", brain.metadata)

    def test_creating_sends_no_task_identity(self) -> None:
        """The scheduler mints the task ID; the desktop never proposes one."""
        self.controller.create_background_task("plan-1")

        self.assertNotIn("background_task_id", self.brain.metadata)

    def test_listing_names_no_identity_at_all(self) -> None:
        self.controller.list_background_tasks()

        self.assertEqual(set(self.brain.metadata), {"intent"})

    def test_the_window_keeps_separate_fields(self) -> None:
        window, _widgets = build_real_window(plan_authorization_enabled=True)

        self.assertIsNot(window._scheduler_task_id, window._execution_id)

    def test_the_queue_controls_read_the_task_field(self) -> None:
        for name in (
            "_pause_background_task",
            "_resume_background_task",
            "_cancel_background_task",
        ):
            with self.subTest(name=name):
                self.assertNotIn("_execution_id", window_method(name))

    def test_creating_reads_the_execution_field(self) -> None:
        body = window_method("_create_background_task", code_only=True)

        self.assertIn("self._execution_id.get()", body)


class EmptyIdentitiesAreRefusedTests(ControllerFixture):
    def test_an_empty_execution_is_refused(self) -> None:
        for blank in ("", "   "):
            with self.subTest(name=repr(blank)):
                with self.assertRaises(ValueError):
                    self.controller.create_background_task(blank)

    def test_an_empty_task_is_refused(self) -> None:
        for name in (
            "pause_background_task",
            "resume_background_task",
            "cancel_background_task",
        ):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    getattr(self.controller, name)("  ")

    def test_a_refused_identity_sends_nothing(self) -> None:
        with self.assertRaises(ValueError):
            self.controller.create_background_task("")

        self.assertEqual(self.brain.requests, [])

    def test_surrounding_space_is_trimmed_not_rejected(self) -> None:
        self.controller.create_background_task("  plan-1  ")

        self.assertEqual(self.brain.metadata["research_plan_id"], "plan-1")


class QueueingGrantsAndRunsNothingTests(ControllerFixture):
    """Creating a task is not approving one, and never performs research."""

    def test_creating_sends_no_budget(self) -> None:
        """The scheduler's own default bound applies; the desktop names none."""
        self.controller.create_background_task("plan-1")

        self.assertEqual(set(self.brain.metadata), {"intent", "research_plan_id"})

    def test_no_queue_control_carries_authority(self) -> None:
        for name in (*QUEUE_METHODS, "_background_task_ruling"):
            with self.subTest(name=name):
                body = controller_method(name, code_only=True)

                for forbidden in (
                    "authorization",
                    "approve",
                    "budget_from",
                    "max_step_advances",
                ):
                    self.assertNotIn(forbidden, body)

    def test_no_queue_control_advances_research(self) -> None:
        for name in (*QUEUE_METHODS, "_background_task_ruling"):
            with self.subTest(name=name):
                body = controller_method(name, code_only=True)

                for forbidden in (
                    "process_advance",
                    "process_continue",
                    "worker_cycle",
                    "autonomy",
                ):
                    self.assertNotIn(forbidden, body)

    def test_the_queue_handlers_run_no_loop_and_set_no_timer(self) -> None:
        for name in (
            "_create_background_task",
            "_list_background_tasks",
            "_pause_background_task",
            "_resume_background_task",
            "_cancel_background_task",
        ):
            with self.subTest(name=name):
                lines = [line.strip() for line in window_method(name).splitlines()]

                for keyword in ("while ", "for "):
                    self.assertEqual(
                        [line for line in lines if line.startswith(keyword)], []
                    )
                for spawned in ("Thread(", ".after(", "sleep(", "run_at"):
                    self.assertEqual([line for line in lines if spawned in line], [])

    def test_the_desktop_builds_no_task_record(self) -> None:
        for forbidden in (
            "BackgroundResearchTask(",
            "BackgroundResearchTaskStatus",
            "JsonFileBackgroundTaskStore",
        ):
            with self.subTest(name=forbidden):
                self.assertNotIn(forbidden, WINDOW_SOURCE)
                self.assertNotIn(forbidden, CONTROLLER_SOURCE)


class TheWindowAsksBeforeChangingTheQueueTests(unittest.TestCase):
    """Every mutation is confirmed; reading is not."""

    def setUp(self) -> None:
        self.window, self.widgets = build_real_window(
            plan_authorization_enabled=True, curiosity_enabled=True
        )
        self.calls: list[tuple[str, object]] = []
        self.window._controller = SimpleNamespace(
            create_background_task=lambda execution_id: self._record(
                "create", execution_id
            ),
            list_background_tasks=lambda: self._record("list", None),
            pause_background_task=lambda task_id: self._record("pause", task_id),
            resume_background_task=lambda task_id: self._record("resume", task_id),
            cancel_background_task=lambda task_id: self._record("cancel", task_id),
        )
        self.statuses: list[str] = []
        self.window._plan_approval_status = SimpleNamespace(
            set=self.statuses.append, get=lambda: ""
        )
        self.window._plan_approval_output = _Sink()
        self.window._append_response = lambda response: None
        self.created = BrainResponse(
            message="queued",
            request_id="request-1",
            intent="background_research_task",
            memory_count=0,
            background_research_task=SimpleNamespace(task_id="task-9"),
        )

    def _record(self, name: str, value: object) -> BrainResponse:
        self.calls.append((name, value))
        if name == "create":
            return self.created
        return BrainResponse(
            message="ok",
            request_id="request-1",
            intent="background_research_task",
            memory_count=0,
        )

    def _press(self, handler: str, *, confirm: bool = True):
        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=confirm
        ) as dialog:
            getattr(self.window, handler)()
        return dialog

    def test_each_mutation_asks_first(self) -> None:
        self.window._execution_id.set("plan-1")
        self.window._scheduler_task_id.set("task-1")
        for handler in (
            "_create_background_task",
            "_pause_background_task",
            "_resume_background_task",
            "_cancel_background_task",
        ):
            with self.subTest(name=handler):
                dialog = self._press(handler)

                self.assertEqual(dialog.call_count, 1)

    def test_declining_changes_nothing(self) -> None:
        self.window._execution_id.set("plan-1")
        self.window._scheduler_task_id.set("task-1")
        for handler in (
            "_create_background_task",
            "_pause_background_task",
            "_resume_background_task",
            "_cancel_background_task",
        ):
            with self.subTest(name=handler):
                self.calls.clear()

                self._press(handler, confirm=False)

                self.assertEqual(self.calls, [])

    def test_reading_the_queue_asks_nothing(self) -> None:
        dialog = self._press("_list_background_tasks")

        self.assertEqual(dialog.call_count, 0)
        self.assertEqual(self.calls, [("list", None)])

    def test_a_missing_execution_queues_nothing(self) -> None:
        self.window._execution_id.set("   ")

        self._press("_create_background_task")

        self.assertEqual(self.calls, [])
        self.assertTrue(any("execution ID is required" in s for s in self.statuses))

    def test_a_missing_task_identity_changes_nothing(self) -> None:
        self.window._scheduler_task_id.set("")
        for handler in (
            "_pause_background_task",
            "_resume_background_task",
            "_cancel_background_task",
        ):
            with self.subTest(name=handler):
                self.calls.clear()

                self._press(handler)

                self.assertEqual(self.calls, [])

    def test_creating_carries_the_named_execution(self) -> None:
        self.window._execution_id.set("plan-4")

        self._press("_create_background_task")

        self.assertEqual(self.calls, [("create", "plan-4")])

    def test_the_created_task_identity_is_captured_from_the_record(self) -> None:
        """So the next press acts on the task the scheduler actually made."""
        self.window._execution_id.set("plan-4")

        self._press("_create_background_task")

        self.assertEqual(self.window._scheduler_task_id.get(), "task-9")

    def test_pause_resume_and_cancel_carry_the_task_identity(self) -> None:
        self.window._scheduler_task_id.set("task-3")
        for handler, name in (
            ("_pause_background_task", "pause"),
            ("_resume_background_task", "resume"),
            ("_cancel_background_task", "cancel"),
        ):
            with self.subTest(name=name):
                self.calls.clear()

                self._press(handler)

                self.assertEqual(self.calls, [(name, "task-3")])


class TheConfirmationsTellTheTruthTests(TheWindowAsksBeforeChangingTheQueueTests):
    """What the dialog promises has to match what the code does."""

    def _shown(self, handler: str) -> str:
        self.window._execution_id.set("plan-1")
        self.window._scheduler_task_id.set("task-1")
        return self._press(handler).call_args.args[1].casefold()

    def test_queueing_promises_nothing_runs_yet(self) -> None:
        shown = self._shown("_create_background_task")

        self.assertIn("nothing runs now", shown)
        self.assertIn("run scheduler cycle", shown)

    def test_queueing_does_not_claim_to_approve(self) -> None:
        shown = self._shown("_create_background_task")

        self.assertIn("queueing a task is not approving one", shown)

    def test_cancelling_a_task_does_not_claim_to_stop_the_execution(self) -> None:
        shown = self._shown("_cancel_background_task")

        self.assertIn("the queue entry only", shown)
        self.assertIn("keeps the state it has", shown)

    def test_pausing_does_not_claim_to_stop_the_execution(self) -> None:
        shown = self._shown("_pause_background_task")

        self.assertIn("execution it names is not stopped", shown)

    def test_resuming_promises_no_run(self) -> None:
        shown = self._shown("_resume_background_task")

        self.assertIn("nothing runs now", shown)

    def test_no_confirmation_offers_a_schedule(self) -> None:
        for handler in (
            "_create_background_task",
            "_pause_background_task",
            "_resume_background_task",
            "_cancel_background_task",
        ):
            with self.subTest(name=handler):
                shown = self._shown(handler)

                for forbidden in (
                    "overnight",
                    "recurring",
                    "continuously",
                    "automatically",
                    "retry",
                    "run until",
                ):
                    self.assertNotIn(forbidden, shown)


class TheServiceDecidesEligibilityTests(unittest.TestCase):
    """The UI never predicts a refusal, and never hides one."""

    def test_no_handler_inspects_task_status(self) -> None:
        for name in (
            "_pause_background_task",
            "_resume_background_task",
            "_cancel_background_task",
            "_background_task_action",
        ):
            with self.subTest(name=name):
                code = window_method(name, code_only=True).casefold()

                # Not a ban on the word "status": the panel's own status line
                # is called that. What must not appear is the *task's* status.
                for forbidden in (
                    "pending",
                    "paused",
                    "task.status",
                    "backgroundresearchtaskstatus",
                    "eligible",
                ):
                    self.assertNotIn(forbidden, code)

    def test_no_controller_method_filters_the_queue(self) -> None:
        for name in QUEUE_METHODS:
            with self.subTest(name=name):
                body = controller_method(name, code_only=True)

                for forbidden in ("if task", "filter", "eligible", "runnable"):
                    self.assertNotIn(forbidden, body)


class TheQueueIsVisibleTests(unittest.TestCase):
    """Controls exist, and the listing shows both identities."""

    def test_every_queue_control_is_offered(self) -> None:
        _window, widgets = build_real_window(plan_authorization_enabled=True)
        labels = {
            widget.text
            for widget in widgets
            if getattr(widget, "command", None) is not None
            and isinstance(getattr(widget, "text", None), str)
        }

        for label in (
            "Queue this execution",
            "Refresh tasks",
            "Pause task",
            "Resume task",
            "Cancel task",
            "Run scheduler cycle",
        ):
            with self.subTest(name=label):
                self.assertIn(label, labels)

    def test_the_queue_controls_are_disabled_while_a_request_runs(self) -> None:
        """Ordinary request controls, so a cycle in flight locks them all."""
        for name in (
            "_create_background_task",
            "_list_background_tasks",
            "_pause_background_task",
            "_resume_background_task",
            "_cancel_background_task",
        ):
            with self.subTest(name=name):
                self.assertIn(f"self.{name}", WINDOW_SOURCE)

        start = WINDOW_SOURCE.index('("Queue this execution", self._create')
        end = WINDOW_SOURCE.index('("Cancel task"', start) + 200
        self.assertIn("self._request_button(queue_buttons", WINDOW_SOURCE[start:end])


class TheListingNamesBothIdentitiesTests(unittest.TestCase):
    """A row nobody can act on is not a queue view."""

    def test_a_listed_row_carries_task_and_execution(self) -> None:
        from research.BackgroundResearchTask import BackgroundResearchTask
        from research.ResearchAutonomyBudget import ResearchAutonomyBudget
        from response.ResponseComposer import ResponseComposer

        moment = datetime(2026, 1, 1, tzinfo=UTC)
        task = BackgroundResearchTask(
            task_id="task-2",
            execution_id="plan-2",
            budget=ResearchAutonomyBudget(),
            created_at=moment,
            updated_at=moment,
        )

        rendered = ResponseComposer().background_task_list(
            BrainRequest(
                message="list", metadata={"intent": BACKGROUND_TASK_LIST_INTENT}
            ),
            (task,),
        )

        self.assertIn("task task-2", rendered.message)
        self.assertIn("execution plan-2", rendered.message)


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
