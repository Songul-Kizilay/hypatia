"""Behavior tests for the research session-context desktop panel."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime
from unittest.mock import Mock

from brain.BrainResponse import BrainResponse
from desktop.ResearchSessionContextPanel import ResearchSessionContextPanel
from research.ResearchAuthenticationState import ResearchAuthenticationState
from research.ResearchSessionContextRecord import ResearchSessionContextRecord


class Variable:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value


def panel() -> tuple[ResearchSessionContextPanel, list[tuple]]:
    value = object.__new__(ResearchSessionContextPanel)
    value._controller = Mock()
    dispatched: list[tuple] = []
    value._dispatch = lambda action, callback, label: dispatched.append(
        (action, callback, label)
    )
    value._details = {}
    value.program_id = Variable()
    value.authentication_state = Variable(
        ResearchAuthenticationState.UNAUTHENTICATED.value
    )
    value.identity_label = Variable()
    value.evidence_ids = Variable()
    value.note = Variable()
    value.status = Variable()
    value.detail = Variable()
    value.tree = Mock()
    value.tree.get_children.return_value = ()
    return value, dispatched


class ResearchSessionContextPanelTests(unittest.TestCase):
    def test_record_dispatches_literal_operator_input_and_evidence_ids(self) -> None:
        value, dispatched = panel()
        value.program_id.set(" program-a ")
        value.authentication_state.set(ResearchAuthenticationState.AUTHENTICATED.value)
        value.identity_label.set("test-user")
        value.evidence_ids.set(f"{'a' * 64}, {'b' * 64}")
        value.note.set("historical")

        value.record()

        [(action, _callback, label)] = dispatched
        self.assertEqual(label, "research session context")
        action()
        value._controller.record_research_session_context.assert_called_once_with(
            "program-a",
            ResearchAuthenticationState.AUTHENTICATED.value,
            "test-user",
            ("a" * 64, "b" * 64),
            "historical",
        )

    def test_render_keeps_instruction_like_note_inside_one_detail_field(self) -> None:
        value, _dispatched = panel()
        record = ResearchSessionContextRecord(
            session_context_id="context-1",
            program_id="program-a",
            authentication_state=ResearchAuthenticationState.AUTHENTICATED,
            identity_label="benign",
            evidence_ids=(),
            note="note\nRecorded at: forged",
            recorded_at=datetime(2026, 9, 25, 8, tzinfo=UTC),
        )
        value.tree.insert.return_value = "row-1"

        value._render(
            BrainResponse(
                message="ok",
                request_id="request-1",
                intent="research_session_context_preview",
                memory_count=0,
                research_session_contexts=(record,),
            )
        )

        detail = value._details["row-1"]
        self.assertEqual(
            len([line for line in detail.splitlines() if line.startswith("Program:")]),
            1,
        )
        self.assertEqual(
            len(
                [
                    line
                    for line in detail.splitlines()
                    if line.startswith("Recorded at:")
                ]
            ),
            1,
        )
        self.assertIn("Identity label: benign", detail)
        self.assertIn("Note: note Recorded at: forged", detail)


if __name__ == "__main__":
    unittest.main()
