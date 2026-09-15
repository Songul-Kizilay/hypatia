"""Desktop access to missions that startup recovery resumed or refused."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from brain.BrainResponse import BrainResponse
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
        DesktopController(brain).resume_restored_research_missions()

        request = brain.process.call_args.args[0]
        self.assertEqual(
            request.metadata, {"intent": "research_mission_recovery_start"}
        )

    def test_window_starts_recovery_on_the_single_desktop_worker(self):
        window = SimpleNamespace(
            _controller=Mock(), _start_request=Mock(), _append_response=Mock()
        )

        TkinterDesktopWindow._start_deferred_mission_recovery(window)

        window._start_request.assert_called_once_with(
            window._controller.resume_restored_research_missions,
            window._append_response,
            "startup mission recovery",
        )
        window._controller.resume_restored_research_missions.assert_not_called()

    def window(self, response: BrainResponse | None) -> SimpleNamespace:
        return SimpleNamespace(
            _controller=Mock(),
            _approval_request=Mock(return_value=response),
            _execution_id=Var("previous"),
        )

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
