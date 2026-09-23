"""The tri-state scope check is a real bound control, never a hidden refusal.

Two layers, matching this session's established conventions. The functional
layer drives `_check_target_scope` directly against fake widgets holding real
text, proving the computed status/matched-rule text is correct. The
reachability layer drives Hypatia's own production `__init__`, with the
tkinter widget classes replaced by recorders (the `build_real_window`/
`RecordingWidget` convention used elsewhere in `tests/desktop/`), proving the
"Check scope" button the operator actually presses is bound to that exact
handler rather than merely existing in source.
"""

from __future__ import annotations

import sys
import unittest
from contextlib import ExitStack
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from desktop.TargetResearchDraftDialog import TargetResearchDraftDialog
from tests.desktop.test_research_command_bindings import (
    RecordingVariable,
    RecordingWidget,
)


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

    def get(self, *_args: object) -> str:
        return self.value


def _dialog() -> TargetResearchDraftDialog:
    dialog = object.__new__(TargetResearchDraftDialog)
    dialog.fields = {
        "allowed_hosts": _Text("example.test\n*.example.test"),
        "excluded_hosts": _Text("admin.example.test"),
        "allowed_networks": _Text(""),
        "excluded_networks": _Text(""),
        "source_urls": _Text(""),
    }
    dialog.scope_check_status = _Variable()
    return dialog


class TargetScopeCheckFunctionalTests(unittest.TestCase):
    """Drives `_check_target_scope` directly against fake widgets with real text."""

    def test_reports_in_scope_out_of_scope_and_uncertain_for_entered_urls(
        self,
    ) -> None:
        dialog = _dialog()
        dialog.fields["source_urls"] = _Text(
            "https://api.example.test/report\n"
            "https://admin.example.test/panel\n"
            "https://unrelated.test/page"
        )

        dialog._check_target_scope()

        status = dialog.scope_check_status.get()
        self.assertIn("api.example.test: in_scope", status)
        self.assertIn("matched rule: *.example.test", status)
        self.assertIn("admin.example.test: out_of_scope", status)
        self.assertIn("matched rule: admin.example.test", status)
        self.assertIn("unrelated.test: uncertain", status)
        self.assertIn("no rule in this scope addresses this host", status)
        self.assertIn("not an authorization to fetch", status)

    def test_empty_url_field_is_reported_without_raising(self) -> None:
        dialog = _dialog()

        dialog._check_target_scope()

        self.assertIn("enter at least one source URL", dialog.scope_check_status.get())

    def test_invalid_scope_fields_are_reported_without_raising(self) -> None:
        dialog = _dialog()
        dialog.fields["allowed_hosts"] = _Text("not a valid host!!")
        dialog.fields["source_urls"] = _Text("https://example.test/")

        dialog._check_target_scope()

        self.assertIn("Scope check unavailable", dialog.scope_check_status.get())

    def test_malformed_url_row_is_reported_per_row_without_aborting_the_rest(
        self,
    ) -> None:
        dialog = _dialog()
        dialog.fields["source_urls"] = _Text(
            "not a url at all\nhttps://example.test/page"
        )

        dialog._check_target_scope()

        status = dialog.scope_check_status.get()
        self.assertIn("not a url at all:", status)
        self.assertIn("example.test: in_scope", status)

    def test_this_check_never_changes_apply_accept_refuse_behaviour(self) -> None:
        """The check is read-only decoration; `apply()` is untouched by it."""
        dialog = _dialog()
        dialog.program = _Variable("program-a")
        dialog.action = _Variable("Read page only")
        dialog._scope_enrollment_service = None
        dialog._active_scope_revisions = ()
        dialog._on_apply = Mock()
        dialog.window = Mock()
        dialog.status = _Variable()
        dialog.fields["source_urls"] = _Text("https://admin.example.test/panel")

        dialog._check_target_scope()
        dialog.apply()

        # The scope check ran (informational), but apply() still refuses the
        # excluded host exactly as it always did — the two are independent.
        dialog._on_apply.assert_not_called()
        self.assertIn("Draft not applied", dialog.status.get())


def build_real_dialog(
    **kwargs: Any,
) -> tuple[TargetResearchDraftDialog, list[RecordingWidget]]:
    """Run Hypatia's own dialog construction with recorder widgets in place of Tk."""
    RecordingWidget.instances = []
    module = "desktop.TargetResearchDraftDialog"
    widget_names = (
        "tk.Toplevel",
        "ttk.Frame",
        "ttk.LabelFrame",
        "ttk.Label",
        "ttk.Entry",
        "ttk.Combobox",
        "ttk.Button",
    )
    with ExitStack() as stack:
        for name in widget_names:
            stack.enter_context(patch(f"{module}.{name}", RecordingWidget))
        stack.enter_context(patch(f"{module}.tk.StringVar", RecordingVariable))
        stack.enter_context(
            patch(f"{module}.scrolledtext.ScrolledText", RecordingWidget)
        )
        dialog = TargetResearchDraftDialog(
            object(), None, kwargs.pop("on_apply", lambda draft: None), **kwargs
        )
    return dialog, list(RecordingWidget.instances)


class TargetScopeCheckReachabilityTests(unittest.TestCase):
    """Proves the real constructor wires a "Check scope" control to the handler."""

    def test_the_real_builder_produces_a_bound_check_scope_control(self) -> None:
        dialog, widgets = build_real_dialog()

        matches = [
            widget
            for widget in widgets
            if widget.text == "Check scope (no network, not an authorization)"
            and widget.command is not None
        ]

        self.assertEqual(len(matches), 1)
        [widget] = matches
        self.assertEqual(
            getattr(widget.command, "__func__", None),
            TargetResearchDraftDialog._check_target_scope,
        )
        self.assertIs(getattr(widget.command, "__self__", None), dialog)

    def test_the_status_label_is_bound_to_the_dialogs_own_variable(self) -> None:
        dialog, widgets = build_real_dialog()

        matching = [
            widget
            for widget in widgets
            if widget.textvariable is dialog.scope_check_status
        ]

        self.assertEqual(len(matching), 1)


if __name__ == "__main__":
    unittest.main()
