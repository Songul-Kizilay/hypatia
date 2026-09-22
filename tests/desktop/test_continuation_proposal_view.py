"""Desktop wiring for Evaluate -> Adapt v1 continuation proposals.

Three things matter that a service-layer test alone cannot show: the new
"View continuation proposal" and "Use this proposal's question" controls are
really wired to their own handlers on the real construction path, showing a
proposal (or an ineligibility message) never invents or omits a field, and
the convenience action that copies `seed_question` into the question field
makes zero Brain/network/controller calls of its own -- it is pure `StringVar`
mutation, proven with a controller fixture that raises on any attribute
access.
"""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from desktop.DesktopController import DesktopController
from desktop.TkinterDesktopWindow import TkinterDesktopWindow
from research.ResearchAutonomyResult import AutonomyStopReason
from research.ResearchEvidenceCompletionEvaluation import (
    ResearchEvidenceCompletionLimitation,
    ResearchEvidenceCompletionStatus,
)
from research.ResearchMissionContinuationProposal import (
    ResearchMissionContinuationProposal,
)
from research.ResearchMissionGoalSatisfaction import (
    ResearchMissionGoalSatisfactionStatus,
)
from research.ResearchRunMarkdownRenderer import _clean_text
from tests.desktop.test_research_command_bindings import build_real_window

NOW = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)
PLAN_DIGEST = sha256(b"mission-plan-content").hexdigest()
SEED_QUESTION = "What do the recorded sources support?"


class Var:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value


def _proposal(**changes: object) -> ResearchMissionContinuationProposal:
    values: dict[str, object] = {
        "proposal_id": "proposal-1",
        "origin_run_id": "run-1",
        "origin_plan_digest": PLAN_DIGEST,
        "origin_stop_reason": AutonomyStopReason.STEP_INTERRUPTED,
        "origin_goal_status": ResearchMissionGoalSatisfactionStatus.UNRESOLVED,
        "origin_evidence_status": (
            ResearchEvidenceCompletionStatus.MATERIALLY_UNRESOLVED
        ),
        "origin_evidence_limitations": (
            ResearchEvidenceCompletionLimitation.MISSING_EVIDENCE,
        ),
        "seed_question": SEED_QUESTION,
        "generated_at": NOW,
    }
    values.update(changes)
    return ResearchMissionContinuationProposal(**values)  # type: ignore[arg-type]


def _response(
    proposal: ResearchMissionContinuationProposal | None, *, success: bool = True
) -> BrainResponse:
    return BrainResponse(
        message=(
            "Continuation proposal for plan plan-1 (origin run run-1): goal "
            "status unresolved."
            if proposal is not None
            else "No continuation proposal is available for this mission "
            "(it is not closed, has no recorded run, or its goal status is "
            "not `unresolved`/`partially_satisfied`)."
        ),
        request_id="req-1",
        intent="research_mission_continuation_proposal_preview",
        memory_count=0,
        success=success,
        research_mission_continuation_proposal=proposal,
    )


class ForbiddenController:
    """Any attribute access proves an unwanted Brain/network/provider call."""

    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"this action must never call controller.{name}.")


class ViewContinuationProposalHandlerTests(unittest.TestCase):
    def window(self, plan_id: str = "plan-1") -> SimpleNamespace:
        window = SimpleNamespace(
            _controller=Mock(),
            _status=Mock(),
            _root=None,
            _mission_plan_id="",
            _execution_id=Var(plan_id),
            _continuation_proposal=None,
            _continuation_proposal_plan_id=None,
            _research_plan_preview=Mock(),
            _research_question=Var(),
        )
        window._audit_plan_id = lambda: TkinterDesktopWindow._audit_plan_id(window)
        window._render_continuation_proposal = (
            lambda response: TkinterDesktopWindow._render_continuation_proposal(
                window, response
            )
        )
        window._use_continuation_proposal_question = (
            lambda: TkinterDesktopWindow._use_continuation_proposal_question(window)
        )
        return window

    def test_no_plan_id_never_calls_the_controller(self) -> None:
        window = self.window()
        window._execution_id = Var("")

        TkinterDesktopWindow._view_continuation_proposal(window)

        window._controller.continuation_proposal_preview.assert_not_called()

    def test_a_named_plan_calls_the_controller_exactly_once(self) -> None:
        window = self.window()
        window._controller.continuation_proposal_preview.return_value = _response(
            _proposal()
        )

        TkinterDesktopWindow._view_continuation_proposal(window)

        window._controller.continuation_proposal_preview.assert_called_once_with(
            "plan-1"
        )

    def test_an_eligible_proposal_is_shown_and_stored_verbatim(self) -> None:
        window = self.window()
        proposal = _proposal()

        TkinterDesktopWindow._render_continuation_proposal(window, _response(proposal))

        self.assertIs(window._continuation_proposal, proposal)
        self.assertEqual(window._continuation_proposal_plan_id, "plan-1")
        inserted = window._research_plan_preview.insert.call_args.args[1]
        self.assertIn(proposal.origin_run_id, inserted)
        self.assertIn(proposal.origin_plan_digest, inserted)
        self.assertIn(proposal.origin_stop_reason.value, inserted)
        self.assertIn(proposal.origin_goal_status.value, inserted)
        self.assertIn(proposal.origin_evidence_status.value, inserted)
        self.assertIn(proposal.origin_evidence_limitations[0].value, inserted)
        self.assertIn(proposal.seed_question, inserted)
        # Rendering a returned proposal never issues a second Brain call.
        window._controller.continuation_proposal_preview.assert_not_called()
        self.assertEqual(
            window._status.set.call_args.args[0],
            "continuation proposal: previewed; nothing written",
        )

    def test_seed_question_control_characters_are_normalized_without_truncation(
        self,
    ) -> None:
        """Fix 1: `_clean_text` normalizes, but never truncates, the seed
        question -- unlike `_traceability_text`, which would cut it to 300
        characters and break the "Use this proposal's question" round-trip.
        """
        window = self.window()
        # Written as an escape (not a literal glyph) so the source file
        # itself never embeds a raw directional-override character.
        directional_override = chr(0x202E)  # RIGHT-TO-LEFT OVERRIDE
        long_question = "Q" * 100 + directional_override + "X" * 1800 + "?"
        proposal = _proposal(seed_question=long_question)

        TkinterDesktopWindow._render_continuation_proposal(window, _response(proposal))

        inserted = window._research_plan_preview.insert.call_args.args[1]
        # The unsafe directional-override control character never reaches
        # the rendered preview...
        self.assertNotIn(directional_override, inserted)
        self.assertIn(_clean_text(long_question), inserted)
        # ...but nothing is truncated: the full 1,902-character question is
        # present (modulo the single normalized character).
        self.assertEqual(len(long_question), len(_clean_text(long_question)))
        self.assertIn("Q" * 100, inserted)
        self.assertIn("X" * 1800, inserted)

        # "Use this proposal's question" still copies the FULL, untruncated,
        # un-normalized question verbatim -- this fix is display-only.
        window._use_continuation_proposal_question()

        self.assertEqual(window._research_question.get(), long_question)

    def test_use_after_selector_changed_to_a_different_mission_is_refused(
        self,
    ) -> None:
        """Fix 2, exercised through the real view -> selector-change -> use
        sequence: view mission A's proposal, change the selector to mission
        B without viewing B's own proposal, then "Use this proposal's
        question" must refuse rather than silently feeding A's stale seed
        question into B's question field.
        """
        window = self.window("plan-a")
        proposal = _proposal()

        TkinterDesktopWindow._render_continuation_proposal(window, _response(proposal))
        self.assertEqual(window._continuation_proposal_plan_id, "plan-a")

        window._execution_id.set("plan-b")

        window._use_continuation_proposal_question()

        self.assertEqual(window._research_question.get(), "")
        window._status.set.assert_called_with(
            "The selected mission changed; view its continuation proposal " "again."
        )

    def test_use_for_the_same_still_selected_mission_still_succeeds(self) -> None:
        """Companion test: the guard must not over-refuse the same mission."""
        window = self.window("plan-a")
        proposal = _proposal()

        TkinterDesktopWindow._render_continuation_proposal(window, _response(proposal))

        window._use_continuation_proposal_question()

        self.assertEqual(window._research_question.get(), proposal.seed_question)
        window._status.set.assert_called_with(
            "research question: set from continuation proposal"
        )

    def test_a_not_eligible_response_shows_its_message_without_a_proposal(
        self,
    ) -> None:
        window = self.window()

        TkinterDesktopWindow._render_continuation_proposal(window, _response(None))

        self.assertIsNone(window._continuation_proposal)
        inserted = window._research_plan_preview.insert.call_args.args[1]
        self.assertIn("No continuation proposal is available", inserted)
        window._status.set.assert_called_once()
        self.assertIn(
            "No continuation proposal is available",
            window._status.set.call_args.args[0],
        )

    def test_an_unsuccessful_response_never_fabricates_a_proposal(self) -> None:
        """Fix 3: uses the real exception-path message shape.

        `ResearchMissionAuditApplicationService.process`'s single shared
        `except ResearchError` handler (which this intent also goes
        through) always produces
        `f"Mission audit export was not completed: {error}"`. Using that
        real shape here -- distinct from the generic ineligibility text
        used elsewhere in this file -- proves the widget shows the actual
        distinguishing error text on failure, not just that it doesn't
        crash or fabricate a proposal.
        """
        window = self.window()
        response = BrainResponse(
            message=(
                "Mission audit export was not completed: the mission store "
                "is temporarily unavailable."
            ),
            request_id="req-1",
            intent="research_mission_continuation_proposal_preview",
            memory_count=0,
            success=False,
            research_mission_continuation_proposal=None,
        )

        TkinterDesktopWindow._render_continuation_proposal(window, response)

        self.assertIsNone(window._continuation_proposal)
        self.assertIsNone(window._continuation_proposal_plan_id)
        inserted = window._research_plan_preview.insert.call_args.args[1]
        self.assertEqual(inserted, response.message)
        window._status.set.assert_called_once_with(response.message)


class UseContinuationProposalQuestionTests(unittest.TestCase):
    def window(self, plan_id: str = "") -> SimpleNamespace:
        window = SimpleNamespace(
            _controller=ForbiddenController(),
            _status=Mock(),
            _mission_plan_id="",
            _execution_id=Var(plan_id),
            _continuation_proposal=None,
            _continuation_proposal_plan_id=None,
            _research_question=Var(),
        )
        window._audit_plan_id = lambda: TkinterDesktopWindow._audit_plan_id(window)
        return window

    def test_sets_the_question_field_to_exactly_the_seed_question(self) -> None:
        window = self.window("plan-1")
        proposal = _proposal()
        window._continuation_proposal = proposal
        window._continuation_proposal_plan_id = "plan-1"

        # `ForbiddenController` proves this call touches no controller
        # attribute: any access would raise `AssertionError` immediately.
        TkinterDesktopWindow._use_continuation_proposal_question(window)

        self.assertEqual(window._research_question.get(), proposal.seed_question)

    def test_without_a_shown_proposal_nothing_is_set(self) -> None:
        window = self.window()

        TkinterDesktopWindow._use_continuation_proposal_question(window)

        self.assertEqual(window._research_question.get(), "")
        window._status.set.assert_called_once()

    def test_a_stale_proposal_for_a_different_mission_is_refused(self) -> None:
        """Fix 2: viewed for plan-a, selector now reads plan-b -- refuse."""
        window = self.window("plan-a")
        proposal = _proposal()
        window._continuation_proposal = proposal
        window._continuation_proposal_plan_id = "plan-a"

        # The operator changes the mission selector without viewing that
        # mission's own continuation proposal first.
        window._execution_id.set("plan-b")

        TkinterDesktopWindow._use_continuation_proposal_question(window)

        self.assertEqual(window._research_question.get(), "")
        window._status.set.assert_called_once_with(
            "The selected mission changed; view its continuation proposal " "again."
        )

    def test_the_same_mission_still_succeeds(self) -> None:
        """Companion to the staleness guard: it must not over-refuse."""
        window = self.window("plan-a")
        proposal = _proposal()
        window._continuation_proposal = proposal
        window._continuation_proposal_plan_id = "plan-a"

        TkinterDesktopWindow._use_continuation_proposal_question(window)

        self.assertEqual(window._research_question.get(), proposal.seed_question)


class DesktopControllerContinuationProposalTests(unittest.TestCase):
    class RecordingBrain:
        def __init__(self, response: BrainResponse) -> None:
            self.requests: list[BrainRequest | str] = []
            self._response = response

        def process(self, request: BrainRequest | str) -> BrainResponse:
            self.requests.append(request)
            return self._response

    def test_sends_exactly_the_intent_and_plan_id(self) -> None:
        brain = self.RecordingBrain(_response(_proposal()))
        controller = DesktopController(brain)

        controller.continuation_proposal_preview("  plan-1  ")

        request = brain.requests[-1]
        assert isinstance(request, BrainRequest)
        self.assertEqual(
            request.metadata,
            {
                "intent": "research_mission_continuation_proposal_preview",
                "research_plan_id": "plan-1",
            },
        )
        self.assertEqual(request.source, "desktop")

    def test_an_empty_plan_id_is_refused_before_the_brain_is_reached(self) -> None:
        brain = self.RecordingBrain(_response(_proposal()))
        controller = DesktopController(brain)

        with self.assertRaises(ValueError):
            controller.continuation_proposal_preview("   ")

        self.assertEqual(brain.requests, [])


class RealWindowWiringTests(unittest.TestCase):
    """The real construction path must build both new buttons."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.window, cls.widgets = build_real_window()

    def test_the_view_continuation_proposal_button_is_bound_to_its_own_handler(
        self,
    ) -> None:
        matches = [
            widget
            for widget in self.widgets
            if widget.text == "View continuation proposal"
        ]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].command, self.window._view_continuation_proposal)

    def test_the_use_proposal_question_button_is_bound_to_its_own_handler(
        self,
    ) -> None:
        matches = [
            widget
            for widget in self.widgets
            if widget.text == "Use this proposal's question"
        ]
        self.assertEqual(len(matches), 1)
        self.assertEqual(
            matches[0].command, self.window._use_continuation_proposal_question
        )

    def test_using_the_question_action_never_starts_a_request_on_the_real_window(
        self,
    ) -> None:
        self.window._controller = ForbiddenController()
        proposal = _proposal()
        self.window._continuation_proposal = proposal
        self.window._continuation_proposal_plan_id = self.window._audit_plan_id()

        # No exception means the real bound method never touched the
        # (forbidden) controller.
        self.window._use_continuation_proposal_question()

        self.assertEqual(self.window._research_question.get(), proposal.seed_question)


class ContinuationProposalReentryFlowTests(unittest.TestCase):
    """Proves the convenience action feeds the exact, unmodified re-entry path.

    `tests/e2e/test_continuation_proposal_reentry.py` already proves the
    service layer treats a re-fed `seed_question` identically to manual
    entry. This proves the desktop half of that same chain: once
    `_use_continuation_proposal_question` sets `self._research_question`,
    the entirely unmodified `_preview_question_plan` reads that exact
    `StringVar` value and passes it, byte for byte, to the controller --
    the same call a person typing the question by hand would produce.
    """

    def test_the_stringvar_value_flows_unmodified_into_preview_question_plan(
        self,
    ) -> None:
        proposal = _proposal()
        window = SimpleNamespace(
            _research_question=Var(),
            _research_discovery_provider=Var("crossref"),
            _controller=Mock(),
            _status=Mock(),
            _mission_plan_id="",
            _execution_id=Var("plan-1"),
            _continuation_proposal=proposal,
            _continuation_proposal_plan_id="plan-1",
            _complete_question_plan_preview=Mock(),
        )
        window._audit_plan_id = lambda: TkinterDesktopWindow._audit_plan_id(window)
        recorded_labels: list[str] = []

        def fake_start_request(action, on_success, label, **_kwargs):
            recorded_labels.append(label)
            action()

        window._start_request = fake_start_request

        TkinterDesktopWindow._use_continuation_proposal_question(window)
        self.assertEqual(window._research_question.get(), proposal.seed_question)

        TkinterDesktopWindow._preview_question_plan(window)

        window._controller.preview_question_plan.assert_called_once_with(
            proposal.seed_question, "crossref"
        )
        self.assertEqual(recorded_labels, ["research opening preview"])


if __name__ == "__main__":
    unittest.main()
