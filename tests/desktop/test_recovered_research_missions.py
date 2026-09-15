"""Desktop access to missions that startup recovery resumed or refused."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from brain.BrainResponse import BrainResponse
from core.CancellationSignal import CancellationSignal
from desktop.DesktopController import DesktopController
from desktop.TkinterDesktopWindow import TkinterDesktopWindow


class Var:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value


def listing(*mission_ids: str) -> BrainResponse:
    return BrainResponse(
        message="Missions recovered at startup (this session):",
        request_id="request",
        intent="research_plan_execution_recovered",
        memory_count=0,
        research_recovered_mission_ids=mission_ids,
    )


class RecoveredResearchMissionsTests(unittest.TestCase):
    def test_controller_sends_only_the_read_only_listing_intent(self):
        brain = Mock()
        DesktopController(brain).recovered_research_missions()

        request = brain.process.call_args.args[0]
        self.assertEqual(
            request.metadata, {"intent": "research_plan_execution_recovered"}
        )

    def test_controller_sends_the_once_per_process_recovery_intent(self):
        brain = Mock()
        signal = CancellationSignal()
        DesktopController(brain).resume_restored_research_missions(
            cancellation_token=signal
        )

        request = brain.process.call_args.args[0]
        self.assertEqual(
            request.metadata, {"intent": "research_mission_recovery_start"}
        )
        self.assertIs(request.cancellation_token, signal)

    def test_window_starts_cancellable_recovery_on_the_single_desktop_worker(self):
        window = SimpleNamespace(
            _controller=Mock(),
            _start_request=Mock(),
            _render_startup_mission_recovery=Mock(),
        )

        TkinterDesktopWindow._start_deferred_mission_recovery(window)

        action, on_success, label = window._start_request.call_args.args
        kwargs = window._start_request.call_args.kwargs
        self.assertIs(on_success, window._render_startup_mission_recovery)
        self.assertEqual(label, "startup mission recovery")
        self.assertTrue(kwargs["preserve_cancelled_result"])
        window._controller.resume_restored_research_missions.assert_not_called()
        action()
        window._controller.resume_restored_research_missions.assert_called_once_with(
            cancellation_token=kwargs["cancellation_signal"]
        )

    def window(self, response: BrainResponse | None) -> SimpleNamespace:
        window = SimpleNamespace(
            _controller=Mock(),
            _approval_request=Mock(side_effect=lambda call: response),
            _append_response=Mock(),
            _execution_id=Var("previous"),
            _plan_authorization_enabled=True,
        )
        window._render_recovered_research_missions = (
            lambda value: TkinterDesktopWindow._render_recovered_research_missions(
                window, value
            )
        )
        return window

    def recovery_result(self, success: bool = True) -> BrainResponse:
        return BrainResponse(
            message="Startup mission recovery finished: 1 mission(s) resumed",
            request_id="recovery",
            intent="research_mission_recovery_start",
            memory_count=0,
            success=success,
        )

    def test_startup_recovery_with_outcomes_shows_listing_without_a_click(self):
        window = self.window(listing("plan-1"))
        window._controller.recovered_research_missions.return_value = listing("plan-1")
        result = self.recovery_result()

        TkinterDesktopWindow._render_startup_mission_recovery(window, result)

        window._append_response.assert_called_once_with(result)
        window._controller.recovered_research_missions.assert_called_once_with()
        window._approval_request.assert_called_once()
        self.assertEqual(window._execution_id.get(), "plan-1")

    def test_startup_recovery_without_execution_panel_only_appends_result(self):
        window = self.window(listing("plan-1"))
        window._plan_authorization_enabled = False
        result = self.recovery_result()

        TkinterDesktopWindow._render_startup_mission_recovery(window, result)

        window._append_response.assert_called_once_with(result)
        window._controller.recovered_research_missions.assert_not_called()
        window._approval_request.assert_not_called()

    def test_startup_recovery_without_outcomes_leaves_the_panel_alone(self):
        for listed, success in ((listing(), True), (listing("plan-1"), False)):
            with self.subTest(listed=listed, success=success):
                window = self.window(listed)
                window._controller.recovered_research_missions.return_value = listed

                TkinterDesktopWindow._render_startup_mission_recovery(
                    window, self.recovery_result(success)
                )

                window._approval_request.assert_not_called()
                self.assertEqual(window._execution_id.get(), "previous")

    def test_single_recovered_mission_is_named_for_refresh_status(self):
        window = self.window(listing("plan-1"))

        TkinterDesktopWindow._show_recovered_research_missions(window)

        window._approval_request.assert_called_once_with(
            window._controller.recovered_research_missions
        )
        self.assertEqual(window._execution_id.get(), "plan-1")

    def test_several_or_no_missions_leave_the_execution_id_unchanged(self):
        for response in (listing("plan-1", "plan-2"), listing(), None):
            with self.subTest(response=response):
                window = self.window(response)

                TkinterDesktopWindow._show_recovered_research_missions(window)

                self.assertEqual(window._execution_id.get(), "previous")


if __name__ == "__main__":
    unittest.main()
