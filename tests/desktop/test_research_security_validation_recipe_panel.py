"""Behavior and reachability tests for the validation recipe desktop panel."""

from __future__ import annotations

import sys
import unittest
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock, patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainResponse import BrainResponse
from desktop.ResearchSecurityValidationRecipePanel import (
    ResearchSecurityValidationRecipePanel,
)
from research.ResearchSecurityValidationRecipeRecord import (
    ResearchSecurityValidationRecipeRecord,
)
from research.ResearchSecurityValidationRecipeSubjectKind import (
    ResearchSecurityValidationRecipeSubjectKind,
)
from response.ResponseComposer import SECURITY_VALIDATION_RECIPE_NOT_AUTHORITY_NOTICE
from tests.desktop.test_research_command_bindings import (
    RecordingVariable,
    RecordingWidget,
    build_real_window,
)

RECORDED = datetime(2026, 9, 28, 12, tzinfo=UTC)


class Variable:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value


class TextWidget:
    """Stand-in for `tk.Text`: only the two calls this panel actually makes."""

    def __init__(self, value: str = "") -> None:
        self._value = value

    def get(self, _start: str, _end: str) -> str:
        # A real Tk Text widget's "1.0".."end" always carries a trailing
        # newline; replicated here so splitlines() behaves identically.
        return self._value + "\n"

    def delete(self, _start: str, _end: str) -> None:
        self._value = ""


def panel() -> tuple[ResearchSecurityValidationRecipePanel, list[tuple]]:
    value = object.__new__(ResearchSecurityValidationRecipePanel)
    value._controller = Mock()
    dispatched: list[tuple] = []
    value._dispatch = lambda action, callback, label: dispatched.append(
        (action, callback, label)
    )
    value._details = {}
    value.program_id = Variable()
    value.subject_kind = Variable(
        ResearchSecurityValidationRecipeSubjectKind.FINDING.value
    )
    value.subject_id = Variable()
    value.notes = Variable()
    value.status = Variable()
    value.detail = Variable()
    value.steps_text = TextWidget()
    value.tree = Mock()
    value.tree.get_children.return_value = ()
    return value, dispatched


def recipe(
    recipe_id: str = "recipe-1",
    program_id: str = "program-a",
    subject_kind: ResearchSecurityValidationRecipeSubjectKind = (
        ResearchSecurityValidationRecipeSubjectKind.FINDING
    ),
    subject_id: str = "finding-1",
    steps: tuple[str, ...] = ("Step one", "Step two"),
    notes: str = "notes",
) -> ResearchSecurityValidationRecipeRecord:
    return ResearchSecurityValidationRecipeRecord(
        recipe_id=recipe_id,
        program_id=program_id,
        subject_kind=subject_kind,
        subject_id=subject_id,
        steps=steps,
        notes=notes,
        created_at=RECORDED,
    )


class ResearchSecurityValidationRecipePanelBehaviorTests(unittest.TestCase):
    def test_load_dispatches_literal_operator_input(self) -> None:
        value, dispatched = panel()
        value.program_id.set("  program-a  ")
        value.subject_kind.set(
            ResearchSecurityValidationRecipeSubjectKind.HYPOTHESIS.value
        )
        value.subject_id.set("  hypothesis-1  ")

        value.load()

        [(action, _callback, label)] = dispatched
        self.assertEqual(label, "validation recipes")
        action()
        value._controller.preview_research_security_validation_recipes.assert_called_once_with(
            "program-a",
            ResearchSecurityValidationRecipeSubjectKind.HYPOTHESIS.value,
            "hypothesis-1",
        )

    def test_load_refuses_without_calling_the_controller_when_ids_are_blank(
        self,
    ) -> None:
        value, dispatched = panel()
        value.program_id.set("program-a")
        value.subject_id.set("   ")

        value.load()

        self.assertEqual(dispatched, [])
        self.assertIn("Enter a program ID", value.status.get())

    def test_record_recipe_dispatches_literal_operator_input(self) -> None:
        value, dispatched = panel()
        value.program_id.set("program-a")
        value.subject_kind.set(
            ResearchSecurityValidationRecipeSubjectKind.FINDING.value
        )
        value.subject_id.set(" finding-1 ")
        value.steps_text = TextWidget("Step one\n  Step two  \n\nStep three")
        value.notes.set("  some notes  ")

        value.record_recipe()

        [(action, _callback, label)] = dispatched
        self.assertEqual(label, "validation recipe")
        action()
        value._controller.record_research_security_validation_recipe.assert_called_once_with(
            "program-a",
            ResearchSecurityValidationRecipeSubjectKind.FINDING.value,
            "finding-1",
            ("Step one", "Step two", "Step three"),
            "  some notes  ",
        )

    def test_record_recipe_refuses_with_zero_steps_without_calling_the_controller(
        self,
    ) -> None:
        value, dispatched = panel()
        value.program_id.set("program-a")
        value.subject_id.set("finding-1")
        value.steps_text = TextWidget("   \n\n  ")

        value.record_recipe()

        self.assertEqual(dispatched, [])
        self.assertIn("Enter at least one step", value.status.get())

    def test_after_write_clears_the_form_and_reloads_on_success(self) -> None:
        value, dispatched = panel()
        value.program_id.set("program-a")
        value.subject_id.set("finding-1")
        value.steps_text = TextWidget("Step one")
        value.notes.set("notes")

        value._after_write(
            BrainResponse(
                message="Security validation recipe recorded:",
                request_id="request-1",
                intent="research_security_validation_recipe_record",
                memory_count=0,
            )
        )

        self.assertEqual(value.steps_text.get("1.0", "end"), "\n")
        self.assertEqual(value.notes.get(), "")
        # Reload was triggered: the load() dispatch is now queued.
        [(_action, _callback, label)] = dispatched
        self.assertEqual(label, "validation recipes")

    def test_after_write_leaves_the_form_untouched_on_failure(self) -> None:
        value, dispatched = panel()
        value.steps_text = TextWidget("Step one")
        value.notes.set("notes")

        value._after_write(
            BrainResponse(
                message="Security validation recipe rejected:",
                request_id="request-1",
                intent="research_security_validation_recipe_record",
                memory_count=0,
                success=False,
            )
        )

        self.assertEqual(value.steps_text.get("1.0", "end"), "Step one\n")
        self.assertEqual(value.notes.get(), "notes")
        self.assertEqual(dispatched, [])

    def test_render_lists_step_count_and_created_at(self) -> None:
        value, _dispatched = panel()
        value.tree.insert.return_value = "row-1"

        value._render(
            BrainResponse(
                message="ok",
                request_id="request-1",
                intent="research_security_validation_recipe_preview",
                memory_count=0,
                research_security_validation_recipes=(recipe(),),
            )
        )

        (call,) = value.tree.insert.call_args_list
        label = call.kwargs["text"]
        self.assertIn(RECORDED.isoformat(), label)
        self.assertIn("2 step(s)", label)

    def test_render_detail_shows_every_recorded_field_and_the_notice(self) -> None:
        value, _dispatched = panel()
        value.tree.insert.return_value = "row-1"

        value._render(
            BrainResponse(
                message="ok",
                request_id="request-1",
                intent="research_security_validation_recipe_preview",
                memory_count=0,
                research_security_validation_recipes=(
                    recipe(steps=("Replay the request.", "Observe the response.")),
                ),
            )
        )

        detail = value._details["row-1"]
        self.assertIn("Recipe ID: recipe-1", detail.splitlines())
        self.assertIn("Subject: finding finding-1", detail.splitlines())
        self.assertIn("  1. Replay the request.", detail.splitlines())
        self.assertIn("  2. Observe the response.", detail.splitlines())
        self.assertIn("Notes: notes", detail.splitlines())
        self.assertIn(SECURITY_VALIDATION_RECIPE_NOT_AUTHORITY_NOTICE, detail)

    def test_render_on_failure_clears_the_tree_and_reports_the_message(self) -> None:
        value, _dispatched = panel()

        value._render(
            BrainResponse(
                message="Security validation recipe preview rejected:",
                request_id="request-1",
                intent="research_security_validation_recipe_preview",
                memory_count=0,
                success=False,
            )
        )

        self.assertEqual(
            value.status.get(), "Security validation recipe preview rejected:"
        )
        self.assertEqual(value._details, {})

    def test_render_distinguishes_a_successful_empty_result_from_a_failure(
        self,
    ) -> None:
        # An independent external review (Abacus/route-llm) and hypatia-qa
        # both independently named this exact gap: a subject with zero
        # recorded recipes and a genuinely failed preview both render an
        # empty tree, so nothing previously pinned that the panel tells
        # them apart via `response.success`, only via incidental message
        # text. This asserts the real distinguishing signal directly.
        value, _dispatched = panel()

        value._render(
            BrainResponse(
                message="Security validation recipes: 0",
                request_id="request-1",
                intent="research_security_validation_recipe_preview",
                memory_count=0,
                research_security_validation_recipes=(),
            )
        )

        self.assertEqual(value.status.get(), "Security validation recipes: 0")
        self.assertEqual(value._details, {})
        self.assertNotIn("rejected", value.status.get().lower())

    def test_on_select_shows_the_stored_detail_for_the_selected_row(self) -> None:
        value, _dispatched = panel()
        value._details = {"row-1": "detail text"}
        value.tree.selection.return_value = ("row-1",)

        value._on_select()

        self.assertEqual(value.detail.get(), "detail text")

    def test_on_select_with_nothing_selected_shows_the_default_prompt(self) -> None:
        value, _dispatched = panel()
        value.tree.selection.return_value = ()

        value._on_select()

        self.assertEqual(value.detail.get(), "Select a row to see its recorded fields.")


def build_real_panel(
    dispatch=None,
    controller=None,
) -> tuple[ResearchSecurityValidationRecipePanel, list[RecordingWidget]]:
    """Run Hypatia's own panel construction with recorder widgets in place of Tk."""
    RecordingWidget.instances = []
    module = "desktop.ResearchSecurityValidationRecipePanel"
    widget_names = (
        "ttk.Frame",
        "ttk.LabelFrame",
        "ttk.Label",
        "ttk.Entry",
        "ttk.Combobox",
        "ttk.Button",
        "ttk.Treeview",
        "ttk.Scrollbar",
        "tk.Text",
    )
    parent = RecordingWidget()
    with ExitStack() as stack:
        for name in widget_names:
            stack.enter_context(patch(f"{module}.{name}", RecordingWidget))
        stack.enter_context(patch(f"{module}.tk.StringVar", RecordingVariable))
        panel_value = ResearchSecurityValidationRecipePanel(
            parent,
            controller if controller is not None else Mock(),
            dispatch if dispatch is not None else (lambda a, c, label: None),
        )
    return panel_value, list(RecordingWidget.instances)


class ReachabilityTests(unittest.TestCase):
    def test_the_real_builder_binds_load_and_record_controls(self) -> None:
        panel_value, widgets = build_real_panel()

        bindings = {
            "Load recipes": ResearchSecurityValidationRecipePanel.load,
            "Record recipe": ResearchSecurityValidationRecipePanel.record_recipe,
        }
        for label, expected_method in bindings.items():
            with self.subTest(label=label):
                matches = [
                    widget
                    for widget in widgets
                    if widget.text == label and widget.command is not None
                ]
                self.assertEqual(len(matches), 1)
                [widget] = matches
                self.assertEqual(
                    getattr(widget.command, "__func__", None), expected_method
                )
                self.assertIs(getattr(widget.command, "__self__", None), panel_value)

    def test_a_non_default_subject_kind_reaches_the_controller(self) -> None:
        dispatched: list[tuple] = []

        def dispatch(action, callback, label):  # type: ignore[no-untyped-def]
            dispatched.append((action, callback, label))

        controller = Mock()
        panel_value, widgets = build_real_panel(
            dispatch=dispatch, controller=controller
        )
        panel_value.program_id.set("program-a")
        panel_value.subject_kind.set(
            ResearchSecurityValidationRecipeSubjectKind.HYPOTHESIS.value
        )
        panel_value.subject_id.set("hypothesis-1")

        [load_button] = [
            widget
            for widget in widgets
            if widget.text == "Load recipes" and widget.command is not None
        ]
        load_button.command()

        [(action, _callback, _label)] = dispatched
        action()
        controller.preview_research_security_validation_recipes.assert_called_once_with(
            "program-a",
            ResearchSecurityValidationRecipeSubjectKind.HYPOTHESIS.value,
            "hypothesis-1",
        )


class WindowReachabilityTests(unittest.TestCase):
    """The application window must actually build this panel.

    Mirrors `ResearchSecurityFindingPanel`'s own window-level reachability
    check, including the negative case that pins the gating condition.
    """

    def test_the_window_builds_the_panel_when_the_scope_service_is_present(
        self,
    ) -> None:
        service = Mock()
        window, widgets = build_real_window(program_scope_enrollment_service=service)

        self.assertIsInstance(
            window._security_validation_recipe_panel,
            ResearchSecurityValidationRecipePanel,
        )
        self.assertIn("Load recipes", [widget.text for widget in widgets])
        self.assertIn("Record recipe", [widget.text for widget in widgets])

    def test_a_window_without_the_scope_service_builds_no_recipe_panel(self) -> None:
        window, widgets = build_real_window()

        self.assertIsNone(getattr(window, "_security_validation_recipe_panel", None))
        self.assertNotIn("Load recipes", [widget.text for widget in widgets])


if __name__ == "__main__":
    unittest.main()
