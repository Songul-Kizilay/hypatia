"""Concurrency contract for the single-flight Tkinter request boundary."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from threading import Event
from time import monotonic
from typing import Any
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainResponse import BrainResponse
from desktop.DesktopRequestRunner import DesktopRequestRunner
from desktop.TkinterDesktopWindow import TkinterDesktopWindow


class DesktopRequestRunnerTests(unittest.TestCase):
    def test_one_request_runs_in_background_and_a_second_is_not_queued(self) -> None:
        runner = DesktopRequestRunner()
        entered = Event()
        release = Event()

        def action() -> str:
            entered.set()
            release.wait(timeout=1)
            return "completed"

        self.assertEqual(runner.start(action), "started")
        self.assertTrue(entered.wait(timeout=1))
        self.assertEqual(runner.start(lambda: "must not run"), "busy")

        release.set()
        self._wait_until_idle(runner)

        completions = runner.drain()
        self.assertEqual(len(completions), 1)
        self.assertEqual(completions[0].value, "completed")
        self.assertIsNone(completions[0].error)

    def test_expected_action_error_is_returned_to_the_event_thread(self) -> None:
        runner = DesktopRequestRunner()

        def invalid_action() -> object:
            raise ValueError("invalid request")

        self.assertEqual(runner.start(invalid_action), "started")
        self._wait_until_idle(runner)

        completions = runner.drain()
        self.assertEqual(len(completions), 1)
        self.assertIsInstance(completions[0].error, ValueError)
        self.assertIsNone(completions[0].value)

    def test_stop_discards_a_late_result_and_rejects_new_requests(self) -> None:
        runner = DesktopRequestRunner()
        entered = Event()
        release = Event()

        def action() -> str:
            entered.set()
            release.wait(timeout=1)
            return "too late"

        self.assertEqual(runner.start(action), "started")
        self.assertTrue(entered.wait(timeout=1))
        runner.stop()
        release.set()
        self._wait_until_idle(runner)

        self.assertEqual(runner.drain(), ())
        self.assertEqual(runner.start(lambda: "must not run"), "stopped")

    def test_thread_start_failure_releases_the_single_flight_reservation(self) -> None:
        runner = DesktopRequestRunner()
        with patch("desktop.DesktopRequestRunner.Thread") as thread_type:
            thread_type.return_value.start.side_effect = RuntimeError("unavailable")
            self.assertEqual(runner.start(lambda: "never"), "failed")

        self.assertEqual(runner.start(lambda: "recovered"), "started")
        self._wait_until_idle(runner)
        self.assertEqual(runner.drain()[0].value, "recovered")

    def test_window_presents_results_only_after_event_thread_polling(self) -> None:
        runner = DesktopRequestRunner()
        window = self._window_with(runner)
        entered = Event()
        release = Event()
        responses: list[BrainResponse] = []
        response = BrainResponse(
            message="Completed.",
            request_id="desktop-background",
            intent="conversation",
            memory_count=0,
        )

        def action() -> BrainResponse:
            entered.set()
            release.wait(timeout=1)
            return response

        window._start_request(action, responses.append, "message")

        self.assertTrue(entered.wait(timeout=1))
        self.assertEqual(responses, [])
        self.assertEqual(window._request_controls[0].states, [("disabled",)])
        window._start_request(lambda: response, responses.append, "second")
        self.assertEqual(
            window._status.values[-1],
            "Hypatia is already processing a request.",
        )

        release.set()
        self._wait_until_idle(runner)
        window._poll_requests()

        self.assertEqual(responses, [response])
        self.assertEqual(window._request_controls[0].states[-1], ("!disabled",))
        self.assertEqual(len(window._root.after_calls), 1)

    def test_window_shows_validation_errors_but_sanitizes_other_failures(self) -> None:
        runner = DesktopRequestRunner()
        window = self._window_with(runner)

        def invalid_action() -> BrainResponse:
            raise ValueError("A query cannot be empty.")

        window._start_request(invalid_action, self.fail, "validation")
        self._wait_until_idle(runner)
        window._poll_requests()
        self.assertEqual(window._status.values[-1], "A query cannot be empty.")

        def failed_action() -> BrainResponse:
            raise RuntimeError("provider token must stay private")

        window._start_request(failed_action, self.fail, "provider")
        self._wait_until_idle(runner)
        window._poll_requests()
        self.assertEqual(window._status.values[-1], "Desktop request failed.")
        self.assertNotIn("provider token", " ".join(window._status.values))

    def test_window_close_discards_a_late_worker_result(self) -> None:
        runner = DesktopRequestRunner()
        window = self._window_with(runner)
        entered = Event()
        release = Event()
        responses: list[BrainResponse] = []
        response = BrainResponse(
            message="Too late.",
            request_id="desktop-late",
            intent="conversation",
            memory_count=0,
        )

        def action() -> BrainResponse:
            entered.set()
            release.wait(timeout=1)
            return response

        window._start_request(action, responses.append, "message")
        self.assertTrue(entered.wait(timeout=1))
        window._close()
        release.set()
        self._wait_until_idle(runner)

        self.assertTrue(window._root.destroyed)
        self.assertEqual(runner.drain(), ())
        self.assertEqual(responses, [])

    def test_completed_message_does_not_erase_text_typed_while_waiting(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        window._composer = RecordingComposer("new draft")
        exchanges: list[tuple[str, str, BrainResponse]] = []
        window._append_exchange = lambda speaker, message, response: exchanges.append(
            (speaker, message, response)
        )
        response = BrainResponse(
            message="Completed.",
            request_id="desktop-draft",
            intent="conversation",
            memory_count=0,
        )

        window._complete_message("original message", response)

        self.assertEqual(exchanges, [("You", "original message", response)])
        self.assertEqual(window._composer.value, "new draft")
        self.assertEqual(window._composer.delete_calls, 0)

        window._composer = RecordingComposer("original message")
        window._complete_message("original message", response)
        self.assertEqual(window._composer.value, "")
        self.assertEqual(window._composer.delete_calls, 1)

    def test_window_collects_nested_command_buttons_for_single_flight(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        nested_button = RecordingButton()
        top_button = RecordingButton([nested_button])
        root = RecordingTreeNode([RecordingTreeNode(), top_button])

        with patch("desktop.TkinterDesktopWindow.ttk.Button", RecordingButton):
            controls = window._collect_request_controls(root)

        self.assertEqual(controls, [top_button, nested_button])

    def _window_with(self, runner: DesktopRequestRunner) -> Any:
        window: Any = object.__new__(TkinterDesktopWindow)
        window._request_runner = runner
        window._request_completion_handler = None
        window._request_controls = [RecordingControl()]
        window._closing = False
        window._status = RecordingStatus()
        window._root = RecordingRoot()
        return window

    def _wait_until_idle(self, runner: DesktopRequestRunner) -> None:
        deadline = monotonic() + 2
        while runner.is_running() and monotonic() < deadline:
            Event().wait(0.01)
        self.assertFalse(runner.is_running(), "background request did not finish")


class RecordingControl:
    def __init__(self) -> None:
        self.states: list[tuple[str, ...]] = []

    def state(self, statespec: tuple[str, ...]) -> None:
        self.states.append(statespec)


class RecordingStatus:
    def __init__(self) -> None:
        self.values: list[str] = []

    def set(self, value: str) -> None:
        self.values.append(value)


class RecordingRoot:
    def __init__(self) -> None:
        self.after_calls: list[tuple[int, object]] = []
        self.destroyed = False

    def after(self, delay_ms: int, callback: object) -> None:
        self.after_calls.append((delay_ms, callback))

    def destroy(self) -> None:
        self.destroyed = True


class RecordingComposer:
    def __init__(self, value: str) -> None:
        self.value = value
        self.delete_calls = 0

    def get(self, _start: str, _end: str) -> str:
        return self.value

    def delete(self, _start: str, _end: str) -> None:
        self.delete_calls += 1
        self.value = ""


class RecordingTreeNode:
    def __init__(self, children: list[object] | None = None) -> None:
        self.children = children or []

    def winfo_children(self) -> list[object]:
        return self.children


class RecordingButton(RecordingTreeNode):
    pass


if __name__ == "__main__":
    unittest.main()
