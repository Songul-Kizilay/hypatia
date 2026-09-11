"""The UI confirms once and dispatches one cancellable goal action."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from desktop.TkinterDesktopWindow import (
    ADVISORY_RESTRICTION_LABEL,
    TkinterDesktopWindow,
)


def value(text):
    return Mock(get=Mock(return_value=text))


class ResearchGoalStartUiTests(unittest.TestCase):
    def window(self):
        return SimpleNamespace(
            _target_plan_draft=None,
            _research_plan_constraints=value(""),
            _plan_restriction=value(ADVISORY_RESTRICTION_LABEL),
            _research_question=value("Research indirect prompt injection defenses."),
            _research_discovery_provider=value("crossref"),
            _authorization_advances=value("5"),
            _authorization_network=value("3"),
            _authorization_seconds=value("60"),
            _controller=Mock(),
            _start_request=Mock(),
            _append_response=Mock(),
            _status=Mock(),
        )

    def test_confirmed_start_dispatches_one_worker_action_with_cancellation(self):
        window = self.window()
        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=True
        ) as confirm:
            TkinterDesktopWindow._start_research_goal(window)
        confirm.assert_called_once()
        self.assertIn("incomplete", confirm.call_args.args[1])
        window._start_request.assert_called_once()
        action = window._start_request.call_args.args[0]
        action()
        window._controller.start_research_goal.assert_called_once()
        signal = window._start_request.call_args.kwargs["cancellation_signal"]
        self.assertIs(
            window._controller.start_research_goal.call_args.kwargs[
                "cancellation_token"
            ],
            signal,
        )

    def test_declining_starts_nothing(self):
        window = self.window()
        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=False
        ):
            TkinterDesktopWindow._start_research_goal(window)
        window._start_request.assert_not_called()

    def test_target_or_constraint_is_not_discarded(self):
        for key, change in (
            ("_target_plan_draft", object()),
            ("_research_plan_constraints", value("No external sources")),
            ("_plan_restriction", value("no_external_source_access")),
        ):
            window = self.window()
            setattr(window, key, change)
            with patch("desktop.TkinterDesktopWindow.messagebox.askyesno") as confirm:
                TkinterDesktopWindow._start_research_goal(window)
            confirm.assert_not_called()
            window._start_request.assert_not_called()

    def test_invalid_budget_starts_nothing(self):
        window = self.window()
        window._authorization_network = value("invalid")
        with patch("desktop.TkinterDesktopWindow.messagebox.askyesno") as confirm:
            TkinterDesktopWindow._start_research_goal(window)
        confirm.assert_not_called()
        window._start_request.assert_not_called()
