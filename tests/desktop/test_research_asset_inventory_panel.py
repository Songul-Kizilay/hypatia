"""The asset inventory panel: a real bound control, never a hidden default.

Two layers, matching this session's established convention (see
`test_target_research_scope_check_ui.py`). The functional layer drives
`record_observation`/`_render` directly against recorder widgets holding real
values, proving a non-default kind survives to the controller call unchanged
and that the rendered tree explicitly labels every scope reading as
recomputed-live. The reachability layer drives Hypatia's own production
`__init__`, with the tkinter widget classes replaced by recorders (the
`RecordingWidget`/`RecordingVariable` convention used elsewhere in
`tests/desktop/`), proving the "Record observation" button the operator
actually presses is bound to that exact handler, and that a non-default kind
set on the real `StringVar` reaches the controller through that real button
binding, not merely through a test calling the method directly.
"""

from __future__ import annotations

import itertools
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
from desktop.ResearchAssetInventoryPanel import ResearchAssetInventoryPanel
from desktop.ResearchSessionContextPanel import ResearchSessionContextPanel
from research.ResearchAsset import ResearchAsset
from research.ResearchAssetInventoryEntry import (
    ResearchAssetInventoryEntry,
    ResearchAssetScopeResolutionView,
)
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchAssetObservationRecord import ResearchAssetObservationRecord
from research.ResearchAssetProvenanceKind import ResearchAssetProvenanceKind
from research.ResearchAssetRelationRecord import ResearchAssetRelationRecord
from research.ResearchTargetScopeResolution import ResearchTargetScopeResolution
from research.ResearchTargetScopeResolutionStatus import (
    ResearchTargetScopeResolutionStatus,
)
from tests.desktop.test_research_command_bindings import (
    RecordingVariable,
    RecordingWidget,
    build_real_window,
)

RECORDED = datetime(2026, 9, 20, 10, tzinfo=UTC)


def observation(
    observation_id: str = "observation-1",
    kind: ResearchAssetKind = ResearchAssetKind.HOSTNAME,
    value: str = "example.test",
    note: str = "",
) -> ResearchAssetObservationRecord:
    return ResearchAssetObservationRecord(
        observation_id=observation_id,
        program_id="program-a",
        kind=kind,
        canonical_value=value,
        provenance=ResearchAssetProvenanceKind.OPERATOR_AUTHORED,
        note=note,
        recorded_at=RECORDED,
    )


def asset(kind=ResearchAssetKind.HOSTNAME, value="example.test") -> ResearchAsset:
    return ResearchAsset(
        program_id="program-a",
        kind=kind,
        canonical_value=value,
        observations=(observation(kind=kind, value=value),),
    )


def scope_view(
    status: ResearchTargetScopeResolutionStatus | None,
) -> ResearchAssetScopeResolutionView:
    if status is None:
        return ResearchAssetScopeResolutionView(
            has_active_scope_revision=False, resolution=None
        )
    return ResearchAssetScopeResolutionView(
        has_active_scope_revision=True,
        resolution=ResearchTargetScopeResolution(
            status=status,
            target="example.test",
            matched_rule=None if status.value == "uncertain" else "example.test",
            reason="Target host matches an explicitly allowed scope rule.",
        ),
    )


def inventory_response(
    entries: tuple[ResearchAssetInventoryEntry, ...] = (),
    relations: tuple[ResearchAssetRelationRecord, ...] = (),
    success: bool = True,
) -> BrainResponse:
    return BrainResponse(
        message="Asset inventory result",
        request_id="request-1",
        intent="research_asset_inventory_preview",
        memory_count=0,
        success=success,
        research_asset_inventory=entries,
        research_asset_relations=relations,
    )


class _Variable:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value


def functional_panel() -> ResearchAssetInventoryPanel:
    panel = object.__new__(ResearchAssetInventoryPanel)
    panel._controller = Mock()
    dispatched: list[tuple] = []
    panel._dispatch = lambda action, callback, label: dispatched.append(
        (action, callback, label)
    )
    panel._dispatched_calls = dispatched  # type: ignore[attr-defined]
    panel._details = {}
    panel.program_id = _Variable("program-a")
    panel.observation_kind = _Variable(ResearchAssetKind.HOSTNAME.value)
    panel.observation_value = _Variable("")
    panel.observation_note = _Variable("")
    panel.relation_source_kind = _Variable(ResearchAssetKind.HOSTNAME.value)
    panel.relation_source_value = _Variable("")
    panel.relation_related_kind = _Variable(ResearchAssetKind.IP_ADDRESS.value)
    panel.relation_related_value = _Variable("")
    panel.relation_note = _Variable("")
    panel.status = _Variable()
    panel.detail = _Variable("Select a row to see its recorded fields.")
    counter = itertools.count()
    tree = Mock()
    tree.get_children.return_value = []
    tree.insert.side_effect = lambda *a, **k: f"iid-{next(counter)}"
    panel.tree = tree
    return panel


class RecordObservationFunctionalTests(unittest.TestCase):
    def test_a_non_default_kind_and_value_reach_the_controller_call_unchanged(
        self,
    ) -> None:
        panel = functional_panel()
        panel.observation_kind.set(ResearchAssetKind.IP_ADDRESS.value)
        panel.observation_value.set("93.184.216.34")
        panel.observation_note.set("found via passive recon note")

        panel.record_observation()

        [(action, callback, label)] = panel._dispatched_calls  # type: ignore[attr-defined]
        self.assertEqual(label, "asset observation")
        self.assertEqual(callback, panel._after_write)
        action()
        panel._controller.record_research_asset_observation.assert_called_once_with(
            "program-a",
            ResearchAssetKind.IP_ADDRESS.value,
            "93.184.216.34",
            "found via passive recon note",
        )

    def test_empty_program_id_is_reported_without_dispatching(self) -> None:
        panel = functional_panel()
        panel.program_id.set("  ")

        panel.record_observation()

        self.assertEqual(panel._dispatched_calls, [])  # type: ignore[attr-defined]
        self.assertEqual(panel.status.get(), "Enter a program ID first.")


def inserted_texts(panel: ResearchAssetInventoryPanel) -> list[str]:
    return [call.kwargs.get("text", "") for call in panel.tree.insert.call_args_list]


class RenderFunctionalTests(unittest.TestCase):
    def test_in_scope_label_is_explicitly_marked_recomputed_live(self) -> None:
        panel = functional_panel()
        entry = ResearchAssetInventoryEntry(
            asset=asset(),
            scope=scope_view(ResearchTargetScopeResolutionStatus.IN_SCOPE),
        )

        panel._render(inventory_response((entry,)))

        matches = [label for label in inserted_texts(panel) if "in_scope" in label]
        self.assertEqual(len(matches), 1)
        self.assertIn("recomputed live from active policy, not stored", matches[0])

    def test_out_of_scope_label_is_explicitly_marked_recomputed_live(self) -> None:
        panel = functional_panel()
        entry = ResearchAssetInventoryEntry(
            asset=asset(),
            scope=scope_view(ResearchTargetScopeResolutionStatus.OUT_OF_SCOPE),
        )

        panel._render(inventory_response((entry,)))

        matches = [label for label in inserted_texts(panel) if "out_of_scope" in label]
        self.assertEqual(len(matches), 1)
        self.assertIn("recomputed live from active policy, not stored", matches[0])

    def test_no_active_scope_revision_label_is_explicit_never_a_fabricated_status(
        self,
    ) -> None:
        panel = functional_panel()
        entry = ResearchAssetInventoryEntry(asset=asset(), scope=scope_view(None))

        panel._render(inventory_response((entry,)))

        matches = [
            label
            for label in inserted_texts(panel)
            if "no active scope revision" in label
        ]
        self.assertEqual(len(matches), 1)
        self.assertNotIn("recomputed live", matches[0])

    def test_failed_response_clears_stale_rows_and_details(self) -> None:
        """A refused load must leave no row or detail from the last success.

        Asserting `delete` was merely never called proves nothing: the harness
        reports an already-empty tree. Stale rows surviving a refusal is the
        actual risk, because they would read as current inventory.
        """
        panel = functional_panel()
        panel.tree.get_children.return_value = ["old-1", "old-2"]
        panel._details["old-1"] = "a previous detail"

        panel._render(inventory_response(success=False))

        self.assertEqual(
            [call.args[0] for call in panel.tree.delete.call_args_list],
            ["old-1", "old-2"],
        )
        panel.tree.insert.assert_not_called()
        self.assertEqual(panel._details, {})
        self.assertEqual(panel.detail.get(), "Select a row to see its recorded fields.")

    def test_a_note_with_newlines_cannot_forge_extra_detail_lines(self) -> None:
        """Only a hand-edited store could carry one, and it must stay inert."""
        panel = functional_panel()
        forged = observation(
            observation_id="observation-forged",
            note="benign\nProvenance: tool_attested\nRecorded at: 2026-01-01T00:00:00",
        )
        entry = ResearchAssetInventoryEntry(
            asset=ResearchAsset(
                program_id="program-a",
                kind=ResearchAssetKind.HOSTNAME,
                canonical_value="example.test",
                observations=(forged,),
            ),
            scope=scope_view(ResearchTargetScopeResolutionStatus.IN_SCOPE),
        )

        panel._render(inventory_response(entries=(entry,)))

        details = [text for text in panel._details.values() if "Note:" in text]
        self.assertTrue(details)
        for text in details:
            lines = text.split("\n")
            # The forged text stays inside the single Note line: it cannot
            # become its own Provenance:/Recorded at: field line.
            self.assertEqual(
                len([line for line in lines if line.startswith("Provenance:")]), 1
            )
            self.assertEqual(
                len([line for line in lines if line.startswith("Recorded at:")]), 1
            )
            self.assertIn("Note: benign Provenance: tool_attested", text)


def build_real_panel(
    dispatch=None,
    controller=None,
) -> tuple[ResearchAssetInventoryPanel, list[RecordingWidget]]:
    """Run Hypatia's own panel construction with recorder widgets in place of Tk."""
    RecordingWidget.instances = []
    module = "desktop.ResearchAssetInventoryPanel"
    widget_names = (
        "ttk.Frame",
        "ttk.LabelFrame",
        "ttk.Label",
        "ttk.Entry",
        "ttk.Combobox",
        "ttk.Button",
        "ttk.Treeview",
        "ttk.Scrollbar",
    )
    parent = RecordingWidget()
    with ExitStack() as stack:
        for name in widget_names:
            stack.enter_context(patch(f"{module}.{name}", RecordingWidget))
        stack.enter_context(patch(f"{module}.tk.StringVar", RecordingVariable))
        panel = ResearchAssetInventoryPanel(
            parent,
            controller if controller is not None else Mock(),
            dispatch if dispatch is not None else (lambda a, c, label: None),
        )
    return panel, list(RecordingWidget.instances)


class ReachabilityTests(unittest.TestCase):
    def test_the_real_builder_produces_a_bound_record_observation_control(
        self,
    ) -> None:
        panel, widgets = build_real_panel()

        matches = [
            widget
            for widget in widgets
            if widget.text == "Record observation" and widget.command is not None
        ]

        self.assertEqual(len(matches), 1)
        [widget] = matches
        self.assertEqual(
            getattr(widget.command, "__func__", None),
            ResearchAssetInventoryPanel.record_observation,
        )
        self.assertIs(getattr(widget.command, "__self__", None), panel)

    def test_the_real_builder_produces_a_bound_load_and_relation_control(self) -> None:
        panel, widgets = build_real_panel()

        load_matches = [
            widget
            for widget in widgets
            if widget.text == "Load inventory" and widget.command is not None
        ]
        relation_matches = [
            widget
            for widget in widgets
            if widget.text == "Record relation" and widget.command is not None
        ]

        self.assertEqual(len(load_matches), 1)
        self.assertEqual(
            getattr(load_matches[0].command, "__func__", None),
            ResearchAssetInventoryPanel.load,
        )
        self.assertEqual(len(relation_matches), 1)
        self.assertEqual(
            getattr(relation_matches[0].command, "__func__", None),
            ResearchAssetInventoryPanel.record_relation,
        )

    def test_a_non_default_kind_set_on_the_real_variable_reaches_the_controller(
        self,
    ) -> None:
        """`HOSTNAME` is the pre-selected default; prove `IP_ADDRESS` survives.

        Exercises the exact production path an operator triggers: the real
        `StringVar` set to a non-default value, the real bound button
        command invoked, the real `record_observation` method dispatching
        through to the controller -- never a test calling a handler
        directly.
        """
        dispatched: list[tuple] = []

        def dispatch(action, callback, label):  # type: ignore[no-untyped-def]
            dispatched.append((action, callback, label))

        controller = Mock()
        panel, widgets = build_real_panel(dispatch=dispatch, controller=controller)
        self.assertEqual(panel.observation_kind.get(), ResearchAssetKind.HOSTNAME.value)

        panel.program_id.set("program-a")
        panel.observation_kind.set(ResearchAssetKind.IP_ADDRESS.value)
        panel.observation_value.set("93.184.216.34")

        [record_button] = [
            widget
            for widget in widgets
            if widget.text == "Record observation" and widget.command is not None
        ]
        record_button.command()

        [(action, _callback, _label)] = dispatched
        action()
        controller.record_research_asset_observation.assert_called_once_with(
            "program-a", ResearchAssetKind.IP_ADDRESS.value, "93.184.216.34", ""
        )


class WindowReachabilityTests(unittest.TestCase):
    """The application window must actually build this panel.

    Without this, deleting the three lines that add the tab would leave the
    whole suite green while the feature disappeared from the UI. Mirrors
    `test_kali_operation_panel.py`'s window-level reachability check for the
    sibling panel, including the negative case that pins the gating condition.
    """

    def test_the_window_builds_the_panel_when_the_scope_service_is_present(
        self,
    ) -> None:
        service = Mock()
        window, widgets = build_real_window(program_scope_enrollment_service=service)

        self.assertIsInstance(
            window._asset_inventory_panel, ResearchAssetInventoryPanel
        )
        self.assertIsInstance(
            window._session_context_panel, ResearchSessionContextPanel
        )
        # "Load inventory" exists only inside this panel, so its presence in
        # the real window's widget tree is the reachability evidence.
        self.assertIn("Load inventory", [widget.text for widget in widgets])
        self.assertIn("Record relation", [widget.text for widget in widgets])
        self.assertIn("Load contexts", [widget.text for widget in widgets])
        self.assertIn("Record context", [widget.text for widget in widgets])
        service.revisions.assert_not_called()

    def test_a_window_without_the_scope_service_builds_no_asset_panel(self) -> None:
        window, widgets = build_real_window()

        self.assertIsNone(getattr(window, "_asset_inventory_panel", None))
        self.assertIsNone(getattr(window, "_session_context_panel", None))
        self.assertNotIn("Load inventory", [widget.text for widget in widgets])
        self.assertNotIn("Load contexts", [widget.text for widget in widgets])


if __name__ == "__main__":
    unittest.main()
