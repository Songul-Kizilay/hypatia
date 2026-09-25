"""Behavior and reachability tests for the security hypothesis desktop panel."""

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
from desktop.ResearchSecurityHypothesisPanel import ResearchSecurityHypothesisPanel
from research.ResearchAssetInventoryEntry import ResearchAssetScopeResolutionView
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchAssetObservationRecord import canonicalize_asset_value
from research.ResearchSecurityHypothesis import ResearchSecurityHypothesis
from research.ResearchSecurityHypothesisEntry import ResearchSecurityHypothesisEntry
from research.ResearchSecurityHypothesisEvidenceKind import (
    ResearchSecurityHypothesisEvidenceKind,
)
from research.ResearchSecurityHypothesisEvidenceLinkRecord import (
    ResearchSecurityHypothesisEvidenceLinkRecord,
)
from research.ResearchSecurityHypothesisEvidenceRelation import (
    ResearchSecurityHypothesisEvidenceRelation,
)
from research.ResearchSecurityHypothesisKind import ResearchSecurityHypothesisKind
from research.ResearchSecurityHypothesisOrigin import ResearchSecurityHypothesisOrigin
from research.ResearchSecurityHypothesisStatus import ResearchSecurityHypothesisStatus
from research.ResearchSecurityHypothesisStatusTransitionRecord import (
    ResearchSecurityHypothesisStatusTransitionRecord,
)
from tests.desktop.test_research_command_bindings import (
    RecordingVariable,
    RecordingWidget,
    build_real_window,
)

RECORDED = datetime(2026, 9, 25, 10, tzinfo=UTC)


class Variable:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value


def panel() -> tuple[ResearchSecurityHypothesisPanel, list[tuple]]:
    value = object.__new__(ResearchSecurityHypothesisPanel)
    value._controller = Mock()
    dispatched: list[tuple] = []
    value._dispatch = lambda action, callback, label: dispatched.append(
        (action, callback, label)
    )
    value._details = {}
    value.program_id = Variable()
    value.hypothesis_kind = Variable(ResearchSecurityHypothesisKind.UNKNOWN.value)
    value.subject_kind = Variable(ResearchAssetKind.HOSTNAME.value)
    value.subject_value = Variable()
    value.statement = Variable()
    value.rationale = Variable()
    value.required_validation = Variable()
    value.supporting_evidence_ids = Variable()
    value.attach_hypothesis_id = Variable()
    value.attach_evidence_ids = Variable()
    value.attach_relation = Variable(
        ResearchSecurityHypothesisEvidenceRelation.SUPPORTS.value
    )
    value.transition_hypothesis_id = Variable()
    value.transition_status = Variable(
        ResearchSecurityHypothesisStatus.NEEDS_EVIDENCE.value
    )
    value.transition_reason = Variable()
    value.status = Variable()
    value.detail = Variable()
    value.tree = Mock()
    value.tree.get_children.return_value = ()
    return value, dispatched


def hypothesis(
    hypothesis_id: str = "hypothesis-1",
    program_id: str = "program-a",
    status: ResearchSecurityHypothesisStatus = ResearchSecurityHypothesisStatus.OPEN,
    status_history: tuple[ResearchSecurityHypothesisStatusTransitionRecord, ...] = (),
) -> ResearchSecurityHypothesis:
    link = ResearchSecurityHypothesisEvidenceLinkRecord(
        link_id="link-1",
        hypothesis_id=hypothesis_id,
        program_id=program_id,
        evidence_kind=ResearchSecurityHypothesisEvidenceKind.HTTP_EVIDENCE,
        evidence_id="a" * 64,
        relation=ResearchSecurityHypothesisEvidenceRelation.SUPPORTS,
        recorded_at=RECORDED,
    )
    return ResearchSecurityHypothesis(
        hypothesis_id=hypothesis_id,
        program_id=program_id,
        hypothesis_kind=ResearchSecurityHypothesisKind.AUTHORIZATION,
        subject_kind=ResearchAssetKind.HOSTNAME,
        subject_canonical_value=canonicalize_asset_value(
            ResearchAssetKind.HOSTNAME, "example.test"
        ),
        statement="statement",
        rationale="rationale",
        required_validation="required validation",
        origin=ResearchSecurityHypothesisOrigin.OPERATOR_AUTHORED,
        created_at=RECORDED,
        supporting_evidence=(link,),
        contradicting_evidence=(),
        status=status,
        status_history=status_history,
    )


def entry(
    hypothesis_value: ResearchSecurityHypothesis | None = None,
    has_active_scope_revision: bool = False,
) -> ResearchSecurityHypothesisEntry:
    return ResearchSecurityHypothesisEntry(
        hypothesis=hypothesis_value or hypothesis(),
        scope=ResearchAssetScopeResolutionView(
            has_active_scope_revision=has_active_scope_revision, resolution=None
        ),
    )


class ResearchSecurityHypothesisPanelBehaviorTests(unittest.TestCase):
    def test_create_hypothesis_dispatches_literal_operator_input(self) -> None:
        value, dispatched = panel()
        value.program_id.set(" program-a ")
        value.hypothesis_kind.set(ResearchSecurityHypothesisKind.AUTHORIZATION.value)
        value.subject_kind.set(ResearchAssetKind.HOSTNAME.value)
        value.subject_value.set("example.test")
        value.statement.set("statement")
        value.rationale.set("rationale")
        value.required_validation.set("required validation")
        value.supporting_evidence_ids.set(f"{'a' * 64}, {'b' * 64}")

        value.create_hypothesis()

        [(action, _callback, label)] = dispatched
        self.assertEqual(label, "security hypothesis")
        action()
        value._controller.create_research_security_hypothesis.assert_called_once_with(
            "program-a",
            ResearchSecurityHypothesisKind.AUTHORIZATION.value,
            ResearchAssetKind.HOSTNAME.value,
            "example.test",
            "statement",
            "rationale",
            "required validation",
            ("a" * 64, "b" * 64),
        )

    def test_attach_evidence_dispatches_literal_operator_input(self) -> None:
        value, dispatched = panel()
        value.program_id.set("program-a")
        value.attach_hypothesis_id.set(" hypothesis-1 ")
        value.attach_evidence_ids.set("a" * 64)
        value.attach_relation.set(
            ResearchSecurityHypothesisEvidenceRelation.CONTRADICTS.value
        )

        value.attach_evidence()

        [(action, _callback, label)] = dispatched
        self.assertEqual(label, "security hypothesis evidence")
        action()
        controller = value._controller
        controller.attach_research_security_hypothesis_evidence.assert_called_once_with(
            "hypothesis-1",
            "program-a",
            ("a" * 64,),
            ResearchSecurityHypothesisEvidenceRelation.CONTRADICTS.value,
        )

    def test_transition_status_dispatches_literal_operator_input(self) -> None:
        value, dispatched = panel()
        value.program_id.set("program-a")
        value.transition_hypothesis_id.set("hypothesis-1")
        value.transition_status.set(ResearchSecurityHypothesisStatus.REFUTED.value)
        value.transition_reason.set("no longer plausible")

        value.transition_hypothesis_status()

        [(action, _callback, label)] = dispatched
        self.assertEqual(label, "security hypothesis status transition")
        action()
        controller = value._controller
        controller.transition_research_security_hypothesis_status.assert_called_once_with(
            "hypothesis-1",
            "program-a",
            ResearchSecurityHypothesisStatus.REFUTED.value,
            "no longer plausible",
        )

    def test_render_keeps_instruction_like_status_reason_inside_one_field(
        self,
    ) -> None:
        value, _dispatched = panel()
        transition = ResearchSecurityHypothesisStatusTransitionRecord(
            transition_id="transition-1",
            hypothesis_id="hypothesis-1",
            program_id="program-a",
            status=ResearchSecurityHypothesisStatus.NEEDS_EVIDENCE,
            reason="reason\nStatus: refuted",
            recorded_at=RECORDED,
        )
        value.tree.insert.return_value = "row-1"

        value._render(
            BrainResponse(
                message="ok",
                request_id="request-1",
                intent="research_security_hypothesis_preview",
                memory_count=0,
                research_security_hypotheses=(
                    entry(
                        hypothesis(
                            status=ResearchSecurityHypothesisStatus.NEEDS_EVIDENCE,
                            status_history=(transition,),
                        )
                    ),
                ),
            )
        )

        detail = value._details["row-1"]
        self.assertEqual(
            len([line for line in detail.splitlines() if line.startswith("Status: ")]),
            1,
        )
        self.assertIn("reason Status: refuted", detail)
        self.assertIn("This is a hypothesis, not a finding", detail)

    def test_render_reports_scope_recomputed_live(self) -> None:
        value, _dispatched = panel()
        value.tree.insert.return_value = "row-1"

        value._render(
            BrainResponse(
                message="ok",
                request_id="request-1",
                intent="research_security_hypothesis_preview",
                memory_count=0,
                research_security_hypotheses=(entry(has_active_scope_revision=False),),
            )
        )

        detail = value._details["row-1"]
        self.assertIn("no active scope revision for this program", detail)


def build_real_panel(
    dispatch=None,
    controller=None,
) -> tuple[ResearchSecurityHypothesisPanel, list[RecordingWidget]]:
    """Run Hypatia's own panel construction with recorder widgets in place of Tk."""
    RecordingWidget.instances = []
    module = "desktop.ResearchSecurityHypothesisPanel"
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
        panel_value = ResearchSecurityHypothesisPanel(
            parent,
            controller if controller is not None else Mock(),
            dispatch if dispatch is not None else (lambda a, c, label: None),
        )
    return panel_value, list(RecordingWidget.instances)


class ReachabilityTests(unittest.TestCase):
    def test_the_real_builder_binds_create_attach_and_transition_controls(
        self,
    ) -> None:
        panel_value, widgets = build_real_panel()

        bindings = {
            "Record hypothesis": ResearchSecurityHypothesisPanel.create_hypothesis,
            "Attach evidence": ResearchSecurityHypothesisPanel.attach_evidence,
            "Transition status": (
                ResearchSecurityHypothesisPanel.transition_hypothesis_status
            ),
            "Load hypotheses": ResearchSecurityHypothesisPanel.load,
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

    def test_a_non_default_hypothesis_kind_reaches_the_controller(self) -> None:
        dispatched: list[tuple] = []

        def dispatch(action, callback, label):  # type: ignore[no-untyped-def]
            dispatched.append((action, callback, label))

        controller = Mock()
        panel_value, widgets = build_real_panel(
            dispatch=dispatch, controller=controller
        )
        self.assertEqual(
            panel_value.hypothesis_kind.get(),
            ResearchSecurityHypothesisKind.UNKNOWN.value,
        )

        panel_value.program_id.set("program-a")
        panel_value.hypothesis_kind.set(
            ResearchSecurityHypothesisKind.AUTHENTICATION.value
        )
        panel_value.subject_value.set("example.test")
        panel_value.statement.set("statement")
        panel_value.rationale.set("rationale")
        panel_value.required_validation.set("required validation")
        panel_value.supporting_evidence_ids.set("a" * 64)

        [record_button] = [
            widget
            for widget in widgets
            if widget.text == "Record hypothesis" and widget.command is not None
        ]
        record_button.command()

        [(action, _callback, _label)] = dispatched
        action()
        controller.create_research_security_hypothesis.assert_called_once_with(
            "program-a",
            ResearchSecurityHypothesisKind.AUTHENTICATION.value,
            ResearchAssetKind.HOSTNAME.value,
            "example.test",
            "statement",
            "rationale",
            "required validation",
            ("a" * 64,),
        )


class WindowReachabilityTests(unittest.TestCase):
    """The application window must actually build this panel.

    Mirrors `ResearchAssetInventoryPanel`'s own window-level reachability
    check, including the negative case that pins the gating condition.
    """

    def test_the_window_builds_the_panel_when_the_scope_service_is_present(
        self,
    ) -> None:
        service = Mock()
        window, widgets = build_real_window(program_scope_enrollment_service=service)

        self.assertIsInstance(
            window._security_hypothesis_panel, ResearchSecurityHypothesisPanel
        )
        self.assertIn("Load hypotheses", [widget.text for widget in widgets])
        self.assertIn("Attach evidence", [widget.text for widget in widgets])

    def test_a_window_without_the_scope_service_builds_no_hypothesis_panel(
        self,
    ) -> None:
        window, widgets = build_real_window()

        self.assertIsNone(getattr(window, "_security_hypothesis_panel", None))
        self.assertNotIn("Load hypotheses", [widget.text for widget in widgets])


if __name__ == "__main__":
    unittest.main()
