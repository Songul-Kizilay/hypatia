"""Desktop access to executions paused for authority, after a restart or not."""

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


def listing(*execution_ids: str) -> BrainResponse:
    return BrainResponse(
        message="Executions paused for authority:",
        request_id="request",
        intent="research_plan_execution_paused",
        memory_count=0,
        research_paused_execution_ids=execution_ids,
        research_paused_execution_run_ids=tuple(
            execution_id.replace("plan", "run") for execution_id in execution_ids
        ),
    )


class PausedResearchExecutionsTests(unittest.TestCase):
    def test_controller_sends_only_the_read_only_listing_intent(self) -> None:
        brain = Mock()
        DesktopController(brain).paused_research_executions()

        request = brain.process.call_args.args[0]
        self.assertEqual(request.metadata, {"intent": "research_plan_execution_paused"})

    def window(self, response: BrainResponse | None) -> SimpleNamespace:
        window = SimpleNamespace(
            _controller=Mock(),
            _approval_request=Mock(side_effect=lambda call: response),
            _execution_id=Var("previous"),
        )
        return window

    def test_a_single_paused_execution_is_named_for_refresh_status(self) -> None:
        window = self.window(listing("plan-1"))

        TkinterDesktopWindow._show_paused_research_executions(window)

        window._approval_request.assert_called_once_with(
            window._controller.paused_research_executions
        )
        self.assertEqual(window._execution_id.get(), "plan-1")

    def test_several_or_no_paused_executions_leave_the_execution_id_unchanged(
        self,
    ) -> None:
        for response in (listing("plan-1", "plan-2"), listing(), None):
            with self.subTest(response=response):
                window = self.window(response)

                TkinterDesktopWindow._show_paused_research_executions(window)

                self.assertEqual(window._execution_id.get(), "previous")


if __name__ == "__main__":
    unittest.main()
