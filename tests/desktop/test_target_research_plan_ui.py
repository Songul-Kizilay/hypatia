from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from desktop.TargetResearchDraft import TargetResearchDraft
from desktop.TkinterDesktopWindow import TkinterDesktopWindow


class _Variable:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value


class _Text:
    def __init__(self, value: str = "") -> None:
        self.value = value
        self.state = "normal"

    def get(self, *_args: object) -> str:
        return self.value

    def configure(self, **values: object) -> None:
        self.state = str(values.get("state", self.state))

    def delete(self, *_args: object) -> None:
        self.value = ""

    def insert(self, _index: object, value: str) -> None:
        self.value += value


def _draft() -> TargetResearchDraft:
    return TargetResearchDraft.from_fields(
        "program-1",
        "example.test",
        "",
        "",
        "",
        "https://example.test/security.txt",
    )


class TargetResearchPlanUiTests(unittest.TestCase):
    def _window(self) -> TkinterDesktopWindow:
        window = object.__new__(TkinterDesktopWindow)
        window._target_plan_draft = None
        window._reference_plan_text = None
        window._target_plan_status = _Variable()
        window._research_plan_instructions = _Text("manual step")
        window._research_plan_source_ids = _Text("doc-1")
        window._previewed_authority = object()
        window._previewed_fit = object()
        window._plan_approval_id = _Variable("approval-1")
        window._root = object()
        window._program_scope_enrollment_service = object()
        return window

    def test_apply_uses_immutable_typed_draft_and_invalidates_preview(self) -> None:
        window = self._window()
        draft = _draft()

        window._apply_target_plan_draft(draft)

        self.assertIs(window._target_plan_options()["target_draft"], draft)
        self.assertIn(
            "https://example.test/security.txt",
            window._research_plan_instructions.value,
        )
        self.assertEqual(window._research_plan_instructions.state, "disabled")
        self.assertEqual(window._research_plan_source_ids.value, "")
        self.assertIsNone(window._previewed_authority)
        self.assertEqual(window._plan_approval_id.get(), "")

    def test_clear_restores_reference_plan_without_touching_execution(self) -> None:
        window = self._window()
        window._apply_target_plan_draft(_draft())

        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=True
        ):
            window._clear_target_plan_draft()

        self.assertEqual(window._target_plan_options(), {})
        self.assertEqual(window._research_plan_instructions.value, "manual step")
        self.assertEqual(window._research_plan_source_ids.value, "doc-1")
        self.assertEqual(window._research_plan_instructions.state, "normal")

    def test_provider_comparison_is_blocked_while_target_mode_is_active(self) -> None:
        window = self._window()
        window._target_plan_draft = _draft()
        window._status = _Variable()
        window._start_request = Mock()

        window._preview_provider_comparison_plan()

        window._start_request.assert_not_called()
        self.assertIn("reference plan mode", window._status.get())

    def test_editor_receives_scope_enrollment_service_without_running_it(self) -> None:
        window = self._window()
        window._theme_mode = _Variable("eye_comfort")

        with patch(
            "desktop.TkinterDesktopWindow.TargetResearchDraftDialog"
        ) as dialog_type:
            window._open_target_plan_editor()

        dialog_type.assert_called_once()
        self.assertIs(
            dialog_type.call_args.kwargs["scope_enrollment_service"],
            window._program_scope_enrollment_service,
        )


if __name__ == "__main__":
    unittest.main()
