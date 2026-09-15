"""The UI confirms once and dispatches one cancellable goal action."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from brain.BrainResponse import BrainResponse
from desktop.TkinterDesktopWindow import (
    ADVISORY_RESTRICTION_LABEL,
    TkinterDesktopWindow,
)
from research.ResearchDisclosure import ResearchDisclosure
from research.SemanticMissionPolicy import SemanticMissionPolicy


def value(text):
    return Mock(get=Mock(return_value=text))


class ResearchGoalStartUiTests(unittest.TestCase):
    def test_learning_blank_time_uses_canonical_default(self):
        from research.ResearchAutonomyBudget import ResearchAutonomyBudget

        window = self.window()
        window._authorization_seconds = value("")
        TkinterDesktopWindow._start_learning_research(window)
        window._start_request.call_args.args[0]()
        budget = window._controller.preview_learning_research.call_args.args[2]
        self.assertEqual(budget.max_seconds, ResearchAutonomyBudget().max_seconds)

    def test_learning_disabled_approval_is_explained_without_crashing(self):
        window = self.window()
        del window._authorization_seconds
        TkinterDesktopWindow._start_learning_research(window)
        window._start_request.assert_not_called()
        self.assertIn("Enable", window._status.set.call_args.args[0])

    def test_learning_preview_then_one_confirmation_uses_displayed_policy(self):
        window = self.window()
        policy = SemanticMissionPolicy(
            "http://127.0.0.1:11434/v1/chat/completions",
            "fixture",
            ResearchDisclosure.LOCAL_ONLY,
        )
        preview = BrainResponse(
            message="Exact displayed destination",
            request_id="preview",
            intent="research_learning_preview",
            memory_count=0,
            research_plan_draft_preview=SimpleNamespace(
                plan=SimpleNamespace(
                    mission_scope=SimpleNamespace(semantic_policy=policy)
                )
            ),
        )
        TkinterDesktopWindow._start_learning_research(window)
        action, callback, _ = window._start_request.call_args.args
        action()
        window._controller.start_learning_research.assert_not_called()
        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=True
        ) as confirm:
            callback(preview)
        confirm.assert_called_once_with(
            "Approve bounded learning research?", preview.message
        )
        window._start_request.call_args.args[0]()
        call = window._controller.start_learning_research.call_args
        self.assertIs(call.args[3], policy)
        self.assertEqual(call.args[2].max_llm_operations, 2)
        self.assertEqual(call.args[2].max_step_advances, 18)

    def test_learning_decline_has_no_execution(self):
        window = self.window()
        TkinterDesktopWindow._start_learning_research(window)
        callback = window._start_request.call_args.args[1]
        response = BrainResponse(
            message="Preview",
            request_id="x",
            intent="preview",
            memory_count=0,
            research_plan_draft_preview=SimpleNamespace(
                plan=SimpleNamespace(
                    mission_scope=SimpleNamespace(semantic_policy=object())
                )
            ),
        )
        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=False
        ):
            callback(response)
        window._controller.start_learning_research.assert_not_called()
        self.assertEqual(window._start_request.call_count, 1)

    def test_comparison_is_explicit_once_and_never_raises_budget(self):
        window = self.window()
        with patch("desktop.TkinterDesktopWindow.messagebox.askyesno") as confirm:
            TkinterDesktopWindow._start_research_comparison(window)
        confirm.assert_not_called()
        window._start_request.assert_not_called()
        window._authorization_advances = value("11")
        window._authorization_network = value("5")
        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=True
        ) as confirm:
            TkinterDesktopWindow._start_research_comparison(window)
        confirm.assert_called_once()
        self.assertIn("two distinct", confirm.call_args.args[1])
        self.assertIn("cumulative 16 KiB", confirm.call_args.args[1])
        window._start_request.call_args.args[0]()
        self.assertTrue(
            window._controller.start_research_goal.call_args.kwargs["compare_sources"]
        )

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
            _render_learning_research_result=Mock(),
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
        self.assertIn("one source-grounded evidence record", confirm.call_args.args[1])
        self.assertIn("same budget", confirm.call_args.args[1])
        window._start_request.assert_called_once()
        action = window._start_request.call_args.args[0]
        action()
        window._controller.start_research_goal.assert_called_once()
        self.assertTrue(
            window._controller.start_research_goal.call_args.kwargs["record_evidence"]
        )
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
