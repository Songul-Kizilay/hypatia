"""Behavior and reachability tests for the security finding desktop panel."""

from __future__ import annotations

import dataclasses
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
from desktop.ResearchSecurityFindingPanel import ResearchSecurityFindingPanel
from research.ResearchAssetInventoryEntry import ResearchAssetScopeResolutionView
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchAssetObservationRecord import canonicalize_asset_value
from research.ResearchSecurityFinding import ResearchSecurityFinding
from research.ResearchSecurityFindingEntry import ResearchSecurityFindingEntry
from research.ResearchSecurityFindingEvidenceKind import (
    ResearchSecurityFindingEvidenceKind,
)
from research.ResearchSecurityFindingEvidenceLinkRecord import (
    ResearchSecurityFindingEvidenceLinkRecord,
)
from research.ResearchSecurityFindingEvidenceRelation import (
    ResearchSecurityFindingEvidenceRelation,
)
from research.ResearchSecurityFindingOrigin import ResearchSecurityFindingOrigin
from research.ResearchSecurityFindingStatus import ResearchSecurityFindingStatus
from research.ResearchSecurityFindingStatusTransitionRecord import (
    ResearchSecurityFindingStatusTransitionRecord,
)
from research.ResearchSecurityHypothesisKind import ResearchSecurityHypothesisKind
from research.ResearchTargetScope import ResearchTargetScope, TargetHostRule
from response.ResponseComposer import SECURITY_FINDING_NOT_AUTHORITY_NOTICE
from tests.desktop.test_research_command_bindings import (
    RecordingVariable,
    RecordingWidget,
    build_real_window,
)

RECORDED = datetime(2026, 9, 26, 10, tzinfo=UTC)


class Variable:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value


def panel() -> tuple[ResearchSecurityFindingPanel, list[tuple]]:
    value = object.__new__(ResearchSecurityFindingPanel)
    value._controller = Mock()
    dispatched: list[tuple] = []
    value._dispatch = lambda action, callback, label: dispatched.append(
        (action, callback, label)
    )
    value._details = {}
    value.program_id = Variable()
    value.source_hypothesis_id = Variable()
    value.title = Variable()
    value.description = Variable()
    value.required_followup = Variable()
    value.attach_finding_id = Variable()
    value.attach_evidence_ids = Variable()
    value.attach_relation = Variable(
        ResearchSecurityFindingEvidenceRelation.SUPPORTS.value
    )
    value.transition_finding_id = Variable()
    value.transition_status = Variable(
        ResearchSecurityFindingStatus.VALIDATION_REQUIRED.value
    )
    value.transition_reason = Variable()
    value.transition_duplicate_of_finding_id = Variable()
    value.transition_superseded_by_finding_id = Variable()
    value.status = Variable()
    value.detail = Variable()
    value.tree = Mock()
    value.tree.get_children.return_value = ()
    return value, dispatched


def finding(
    finding_id: str = "finding-1",
    program_id: str = "program-a",
    status: ResearchSecurityFindingStatus = ResearchSecurityFindingStatus.CANDIDATE,
    status_history: tuple[ResearchSecurityFindingStatusTransitionRecord, ...] = (),
) -> ResearchSecurityFinding:
    link = ResearchSecurityFindingEvidenceLinkRecord(
        link_id="link-1",
        finding_id=finding_id,
        program_id=program_id,
        evidence_kind=ResearchSecurityFindingEvidenceKind.HTTP_EVIDENCE,
        evidence_id="a" * 64,
        relation=ResearchSecurityFindingEvidenceRelation.SUPPORTS,
        recorded_at=RECORDED,
    )
    return ResearchSecurityFinding(
        finding_id=finding_id,
        program_id=program_id,
        source_hypothesis_id="hypothesis-1",
        finding_kind=ResearchSecurityHypothesisKind.AUTHORIZATION,
        subject_kind=ResearchAssetKind.HOSTNAME,
        subject_canonical_value=canonicalize_asset_value(
            ResearchAssetKind.HOSTNAME, "example.test"
        ),
        title="title",
        description="description",
        required_followup="required followup",
        origin=ResearchSecurityFindingOrigin.OPERATOR_AUTHORED,
        created_at=RECORDED,
        supporting_evidence=(link,),
        contradicting_evidence=(),
        validation_evidence=(),
        status=status,
        status_history=status_history,
    )


def entry(
    finding_value: ResearchSecurityFinding | None = None,
    has_active_scope_revision: bool = False,
) -> ResearchSecurityFindingEntry:
    return ResearchSecurityFindingEntry(
        finding=finding_value or finding(),
        scope=ResearchAssetScopeResolutionView(
            has_active_scope_revision=has_active_scope_revision, resolution=None
        ),
    )


class ResearchSecurityFindingPanelBehaviorTests(unittest.TestCase):
    def test_create_finding_dispatches_literal_operator_input(self) -> None:
        value, dispatched = panel()
        value.program_id.set(" program-a ")
        value.source_hypothesis_id.set(" hypothesis-1 ")
        value.title.set("title")
        value.description.set("description")
        value.required_followup.set("required followup")

        value.create_finding()

        [(action, _callback, label)] = dispatched
        self.assertEqual(label, "security finding")
        action()
        value._controller.create_research_security_finding.assert_called_once_with(
            "program-a",
            "hypothesis-1",
            "title",
            "description",
            "required followup",
        )

    def test_attach_evidence_dispatches_literal_operator_input(self) -> None:
        value, dispatched = panel()
        value.program_id.set("program-a")
        value.attach_finding_id.set(" finding-1 ")
        value.attach_evidence_ids.set("a" * 64)
        value.attach_relation.set(
            ResearchSecurityFindingEvidenceRelation.VALIDATES.value
        )

        value.attach_evidence()

        [(action, _callback, label)] = dispatched
        self.assertEqual(label, "security finding evidence")
        action()
        controller = value._controller
        controller.attach_research_security_finding_evidence.assert_called_once_with(
            "finding-1",
            "program-a",
            ("a" * 64,),
            ResearchSecurityFindingEvidenceRelation.VALIDATES.value,
        )

    def test_transition_status_dispatches_literal_operator_input(self) -> None:
        value, dispatched = panel()
        value.program_id.set("program-a")
        value.transition_finding_id.set("finding-1")
        value.transition_status.set(ResearchSecurityFindingStatus.DUPLICATE.value)
        value.transition_reason.set("near-identical to an existing finding")
        value.transition_duplicate_of_finding_id.set(" finding-2 ")
        value.transition_superseded_by_finding_id.set("")

        value.transition_finding_status()

        [(action, _callback, label)] = dispatched
        self.assertEqual(label, "security finding status transition")
        action()
        controller = value._controller
        controller.transition_research_security_finding_status.assert_called_once_with(
            "finding-1",
            "program-a",
            ResearchSecurityFindingStatus.DUPLICATE.value,
            "near-identical to an existing finding",
            " finding-2 ",
            "",
        )

    def test_render_keeps_instruction_like_status_reason_inside_one_field(
        self,
    ) -> None:
        value, _dispatched = panel()
        transition = ResearchSecurityFindingStatusTransitionRecord(
            transition_id="transition-1",
            finding_id="finding-1",
            program_id="program-a",
            status=ResearchSecurityFindingStatus.VALIDATION_REQUIRED,
            reason="reason\nStatus: validated",
            duplicate_of_finding_id=None,
            superseded_by_finding_id=None,
            recorded_at=RECORDED,
        )
        value.tree.insert.return_value = "row-1"

        value._render(
            BrainResponse(
                message="ok",
                request_id="request-1",
                intent="research_security_finding_preview",
                memory_count=0,
                research_security_findings=(
                    entry(
                        finding(
                            status=ResearchSecurityFindingStatus.VALIDATION_REQUIRED,
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
        self.assertIn("reason Status: validated", detail)
        self.assertIn(SECURITY_FINDING_NOT_AUTHORITY_NOTICE, detail)

    def test_render_distinguishes_candidate_from_validated_by_plain_text_only(
        self,
    ) -> None:
        value, _dispatched = panel()
        value.tree.insert.return_value = "row-1"

        value._render(
            BrainResponse(
                message="ok",
                request_id="request-1",
                intent="research_security_finding_preview",
                memory_count=0,
                research_security_findings=(
                    entry(finding(status=ResearchSecurityFindingStatus.VALIDATED)),
                ),
            )
        )

        detail = value._details["row-1"]
        self.assertIn("Status: validated", detail)
        self.assertIn(SECURITY_FINDING_NOT_AUTHORITY_NOTICE, detail)

    def test_render_reports_scope_recomputed_live(self) -> None:
        value, _dispatched = panel()
        value.tree.insert.return_value = "row-1"

        value._render(
            BrainResponse(
                message="ok",
                request_id="request-1",
                intent="research_security_finding_preview",
                memory_count=0,
                research_security_findings=(entry(has_active_scope_revision=False),),
            )
        )

        detail = value._details["row-1"]
        self.assertIn("no active scope revision for this program", detail)

    def test_render_shows_duplicate_and_superseded_linkage(self) -> None:
        value, _dispatched = panel()
        transition = ResearchSecurityFindingStatusTransitionRecord(
            transition_id="transition-1",
            finding_id="finding-1",
            program_id="program-a",
            status=ResearchSecurityFindingStatus.DUPLICATE,
            reason="",
            duplicate_of_finding_id="finding-2",
            superseded_by_finding_id=None,
            recorded_at=RECORDED,
        )
        value.tree.insert.return_value = "row-1"

        value._render(
            BrainResponse(
                message="ok",
                request_id="request-1",
                intent="research_security_finding_preview",
                memory_count=0,
                research_security_findings=(
                    entry(
                        finding(
                            status=ResearchSecurityFindingStatus.DUPLICATE,
                            status_history=(transition,),
                        )
                    ),
                ),
            )
        )

        detail = value._details["row-1"]
        self.assertIn("Duplicate of: finding-2", detail)
        self.assertIn("Superseded by: none", detail)


def build_real_panel(
    dispatch=None,
    controller=None,
) -> tuple[ResearchSecurityFindingPanel, list[RecordingWidget]]:
    """Run Hypatia's own panel construction with recorder widgets in place of Tk."""
    RecordingWidget.instances = []
    module = "desktop.ResearchSecurityFindingPanel"
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
        panel_value = ResearchSecurityFindingPanel(
            parent,
            controller if controller is not None else Mock(),
            dispatch if dispatch is not None else (lambda a, c, label: None),
        )
    return panel_value, list(RecordingWidget.instances)


class ResearchSecurityFindingPanelListingTests(unittest.TestCase):
    """The listing names source hypothesis and created-at, per the milestone."""

    def _render_one(
        self, finding_value: ResearchSecurityFinding
    ) -> tuple[ResearchSecurityFindingPanel, str]:
        value, _dispatched = panel()
        value.tree.insert.return_value = "row-1"
        value._render(
            BrainResponse(
                message="ok",
                request_id="request-1",
                intent="research_security_finding_preview",
                memory_count=0,
                research_security_findings=(entry(finding_value),),
            )
        )
        (call,) = value.tree.insert.call_args_list
        return value, call.kwargs["text"]

    def test_each_row_names_its_source_hypothesis_and_created_at(self) -> None:
        _value, label = self._render_one(finding())

        self.assertIn("from hypothesis hypothesis-1", label)
        self.assertIn(f"created {RECORDED.isoformat()}", label)
        self.assertIn("(candidate)", label)

    def test_detail_names_created_at_and_source_hypothesis(self) -> None:
        value, _label = self._render_one(finding())

        detail = value._details["row-1"]
        self.assertIn(f"Created at: {RECORDED.isoformat()}", detail.splitlines())
        self.assertIn("Source hypothesis: hypothesis-1", detail.splitlines())

    def test_detail_pane_shows_every_recorded_field_and_live_scope(self) -> None:
        def link(
            link_id: str,
            evidence_id: str,
            relation: ResearchSecurityFindingEvidenceRelation,
        ) -> ResearchSecurityFindingEvidenceLinkRecord:
            return ResearchSecurityFindingEvidenceLinkRecord(
                link_id=link_id,
                finding_id="finding-1",
                program_id="program-a",
                evidence_kind=ResearchSecurityFindingEvidenceKind.HTTP_EVIDENCE,
                evidence_id=evidence_id,
                relation=relation,
                recorded_at=RECORDED,
            )

        value_finding = dataclasses.replace(
            finding(),
            title="Order endpoint exposes a sequential ID",
            description="Numeric ID observed in the request path",
            required_followup="Compare a second account's order",
            contradicting_evidence=(
                link(
                    "link-2",
                    "b" * 64,
                    ResearchSecurityFindingEvidenceRelation.CONTRADICTS,
                ),
            ),
            validation_evidence=(
                link(
                    "link-3",
                    "c" * 64,
                    ResearchSecurityFindingEvidenceRelation.VALIDATES,
                ),
            ),
        )
        resolution = ResearchTargetScope(
            allowed_hosts=(TargetHostRule("example.test"),)
        ).resolve_hostname("example.test")
        value, _dispatched = panel()
        value.tree.insert.return_value = "row-1"
        value._render(
            BrainResponse(
                message="ok",
                request_id="request-1",
                intent="research_security_finding_preview",
                memory_count=0,
                research_security_findings=(
                    ResearchSecurityFindingEntry(
                        finding=value_finding,
                        scope=ResearchAssetScopeResolutionView(
                            has_active_scope_revision=True, resolution=resolution
                        ),
                    ),
                ),
            )
        )

        lines = value._details["row-1"].splitlines()
        for expected in (
            "Finding ID: finding-1",
            "Program: program-a",
            "Kind: authorization",
            "Subject: hostname:example.test",
            "Title: Order endpoint exposes a sequential ID",
            "Description: Numeric ID observed in the request path",
            "Required followup: Compare a second account's order",
            "Origin: operator_authored",
            f"Supporting evidence IDs: {'a' * 64}",
            f"Contradicting evidence IDs: {'b' * 64}",
            f"Validation evidence IDs: {'c' * 64}",
            "Duplicate of: none",
            "Superseded by: none",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, lines)
        (scope_line,) = [line for line in lines if line.startswith("Scope: ")]
        self.assertIn("(recomputed live from active policy, not stored)", scope_line)

    def test_detail_notice_is_the_canonical_response_constant_for_every_status(
        self,
    ) -> None:
        for status in ResearchSecurityFindingStatus:
            with self.subTest(status=status):
                value, _label = self._render_one(finding(status=status))

                detail_lines = value._details["row-1"].splitlines()
                self.assertEqual(
                    detail_lines[-1], SECURITY_FINDING_NOT_AUTHORITY_NOTICE
                )
                self.assertEqual(
                    detail_lines.count(SECURITY_FINDING_NOT_AUTHORITY_NOTICE), 1
                )


class ReachabilityTests(unittest.TestCase):
    def test_the_real_builder_binds_create_attach_and_transition_controls(
        self,
    ) -> None:
        panel_value, widgets = build_real_panel()

        bindings = {
            "Record finding": ResearchSecurityFindingPanel.create_finding,
            "Attach evidence": ResearchSecurityFindingPanel.attach_evidence,
            "Transition status": (
                ResearchSecurityFindingPanel.transition_finding_status
            ),
            "Load findings": ResearchSecurityFindingPanel.load,
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

    def test_a_non_default_source_hypothesis_id_reaches_the_controller(self) -> None:
        dispatched: list[tuple] = []

        def dispatch(action, callback, label):  # type: ignore[no-untyped-def]
            dispatched.append((action, callback, label))

        controller = Mock()
        panel_value, widgets = build_real_panel(
            dispatch=dispatch, controller=controller
        )

        panel_value.program_id.set("program-a")
        panel_value.source_hypothesis_id.set("hypothesis-42")
        panel_value.title.set("title")
        panel_value.description.set("description")
        panel_value.required_followup.set("required followup")

        [record_button] = [
            widget
            for widget in widgets
            if widget.text == "Record finding" and widget.command is not None
        ]
        record_button.command()

        [(action, _callback, _label)] = dispatched
        action()
        controller.create_research_security_finding.assert_called_once_with(
            "program-a",
            "hypothesis-42",
            "title",
            "description",
            "required followup",
        )


class WindowReachabilityTests(unittest.TestCase):
    """The application window must actually build this panel.

    Mirrors `ResearchSecurityHypothesisPanel`'s own window-level reachability
    check, including the negative case that pins the gating condition.
    """

    def test_the_window_builds_the_panel_when_the_scope_service_is_present(
        self,
    ) -> None:
        service = Mock()
        window, widgets = build_real_window(program_scope_enrollment_service=service)

        self.assertIsInstance(
            window._security_finding_panel, ResearchSecurityFindingPanel
        )
        self.assertIn("Load findings", [widget.text for widget in widgets])
        self.assertIn("Attach evidence", [widget.text for widget in widgets])

    def test_a_window_without_the_scope_service_builds_no_finding_panel(self) -> None:
        window, widgets = build_real_window()

        self.assertIsNone(getattr(window, "_security_finding_panel", None))
        self.assertNotIn("Load findings", [widget.text for widget in widgets])


if __name__ == "__main__":
    unittest.main()
