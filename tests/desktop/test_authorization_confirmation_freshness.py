"""What the confirmation says must be what the approval records.

A preview drawn a minute ago describes the budget as it was then. If somebody
edits the boxes afterwards, one of two things has to be true: either the dialog
speaks for the current values, or it speaks for the older ones and says so.
What must never happen is a dialog showing one grant while a different one is
recorded, and the two approval surfaces reach that guarantee from opposite
directions because the runtime treats them differently.

Approving a Curiosity proposal parses the budget fields at the moment of
approving, so the dialog re-reads them, recomputes the fit against the exact
proposal, and refuses before opening if the current values are unusable or too
small. Nobody has to press Prepare again to be safe.

Confirming an operator-authored plan records the approval object built when
Preview ran, budget included. There is nothing current to show: the older
figure *is* the authority. So the dialog shows exactly that and says plainly
that edits since Preview are not part of it. Showing the current boxes there
would be the mismatch this file exists to prevent.

Nothing here runs research. Re-reading a proposal to check a fit reaches no
provider, no network and no model, and declining a dialog records nothing.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from desktop.TkinterDesktopWindow import _granted_authority_lines
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchPlanBudgetRequirement import ResearchPlanBudgetFit
from tests.desktop.test_research_command_bindings import build_real_window
from tests.research.test_curiosity_authorization_budget import (
    DEFAULT,
    REQUIRED_NETWORK,
    CuriosityBudgetFixture,
)

WINDOW_SOURCE = (SRC_DIR / "desktop" / "TkinterDesktopWindow.py").read_text(
    encoding="utf-8"
)


class TheSharedRendererTests(unittest.TestCase):
    """One renderer, so the two surfaces cannot describe a grant differently."""

    def test_it_names_the_authority_being_granted(self) -> None:
        rendered = "\n".join(_granted_authority_lines(ResearchAutonomyBudget()))

        self.assertIn("This is the authority you are about to grant", rendered)

    def test_it_shows_the_budget_it_was_given(self) -> None:
        budget = ResearchAutonomyBudget(max_network_operations=1, max_step_advances=2)

        rendered = "\n".join(_granted_authority_lines(budget))

        self.assertIn("network operations: 1", rendered)
        self.assertIn("step advances: 2", rendered)

    def test_seconds_appear_only_as_granted_authority(self) -> None:
        rendered = "\n".join(_granted_authority_lines(ResearchAutonomyBudget()))

        self.assertIn("seconds: 60.0", rendered)
        self.assertNotIn("seconds required", rendered.casefold())

    def test_a_fit_is_shown_when_one_is_known(self) -> None:
        budget = ResearchAutonomyBudget()
        fit = ResearchPlanBudgetFit(
            required=__import__(
                "research.ResearchOperationCost", fromlist=["ResearchOperationCost"]
            ).ResearchOperationCost(network_operations=1),
            required_advances=2,
            budget=budget,
        )

        rendered = "\n".join(_granted_authority_lines(budget, fit))

        self.assertIn("Network operations required: 1", rendered)

    def test_nothing_is_invented_when_no_fit_is_known(self) -> None:
        rendered = "\n".join(_granted_authority_lines(ResearchAutonomyBudget()))

        self.assertNotIn("required", rendered.casefold())


class CuriosityConfirmsCurrentValuesTests(CuriosityBudgetFixture):
    """The Curiosity dialog re-reads the boxes; approving parses them anyway."""

    def setUp(self) -> None:
        super().setUp()
        self.window, _widgets = build_real_window(
            curiosity_enabled=True, plan_authorization_enabled=True
        )
        self.window._controller = _RecordingController(self)
        self.requests: list = []
        self.statuses: list[str] = []
        self.window._review_request = self._run
        self.window._review_status = SimpleNamespace(set=self.statuses.append)

    def _run(self, call):
        response = call()
        self.requests.append(response)
        return response

    def _prime(self, digest: str, **fields: str) -> None:
        self.window._curiosity_question_id.set(self.question.question_id)
        self.window._curiosity_plan_digest.set(digest)
        self.window._curiosity_advances.set(fields.get("advances", ""))
        self.window._curiosity_network.set(fields.get("network", ""))
        self.window._curiosity_seconds.set(fields.get("seconds", ""))

    def _authorize_through_window(self, confirm: bool = True):
        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno",
            return_value=confirm,
        ) as dialog:
            self.window._authorize_curiosity_research_proposal()
        return dialog

    def test_the_dialog_shows_the_current_grant_not_the_previewed_one(self) -> None:
        """Prepared at the default, then edited down before approving."""
        digest = self._prepare().curiosity_proposal.digest
        self._prime(digest, advances="2", network=str(REQUIRED_NETWORK))

        dialog = self._authorize_through_window()

        shown = dialog.call_args.args[1]
        self.assertIn(f"network operations: {REQUIRED_NETWORK}", shown)
        self.assertNotIn(f"network operations: {DEFAULT.max_network_operations}", shown)

    def test_the_current_grant_is_what_gets_recorded(self) -> None:
        digest = self._prepare().curiosity_proposal.digest
        self._prime(digest, advances="2", network=str(REQUIRED_NETWORK))

        self._authorize_through_window()

        [authorization] = [
            entry for entry in self._authorizations() if entry.consumption is None
        ]
        self.assertEqual(authorization.budget.max_network_operations, REQUIRED_NETWORK)

    def test_a_currently_insufficient_grant_opens_no_dialog(self) -> None:
        digest = self._prepare().curiosity_proposal.digest
        self._prime(digest, network="0")

        dialog = self._authorize_through_window()

        dialog.assert_not_called()
        self.assertEqual(self._authorizations(), [])

    def test_a_currently_insufficient_grant_says_what_is_short(self) -> None:
        digest = self._prepare().curiosity_proposal.digest
        self._prime(digest, network="0")

        self._authorize_through_window()

        self.assertTrue(any("Short by" in status for status in self.statuses))

    def test_currently_malformed_input_opens_no_dialog(self) -> None:
        """A previously valid preview does not rescue what is there now."""
        digest = self._prepare().curiosity_proposal.digest
        self._prime(digest, network="plenty")

        dialog = self._authorize_through_window()

        dialog.assert_not_called()
        self.assertEqual(self._authorizations(), [])

    def test_blank_fields_still_mean_the_default(self) -> None:
        digest = self._prepare().curiosity_proposal.digest
        self._prime(digest)

        dialog = self._authorize_through_window()

        shown = dialog.call_args.args[1]
        self.assertIn(f"network operations: {DEFAULT.max_network_operations}", shown)

    def test_a_stale_digest_is_refused_rather_than_moved(self) -> None:
        self._prepare()
        self._prime("0" * 64)

        dialog = self._authorize_through_window()

        dialog.assert_not_called()
        self.assertEqual(self._authorizations(), [])

    def test_declining_the_dialog_records_nothing(self) -> None:
        digest = self._prepare().curiosity_proposal.digest
        self._prime(digest, advances="2", network="1")

        self._authorize_through_window(confirm=False)

        self.assertEqual(self._authorizations(), [])

    def test_confirming_runs_no_research(self) -> None:
        digest = self._prepare().curiosity_proposal.digest
        self._prime(digest, advances="2", network="1")

        self._authorize_through_window()

        self.assertEqual(self.operation.calls, [])

    def test_checking_the_current_fit_runs_no_research(self) -> None:
        digest = self._prepare().curiosity_proposal.digest
        self._prime(digest, network="0")

        self._authorize_through_window()

        self.assertEqual(self.operation.calls, [])


class _RecordingController:
    """Routes the window's calls at the real services this fixture built."""

    def __init__(self, fixture: CuriosityBudgetFixture) -> None:
        self._fixture = fixture

    def prepare_curiosity_research_proposal(
        self,
        question_id: str,
        max_step_advances: str = "",
        max_network_operations: str = "",
        max_seconds: str = "",
    ):
        return self._fixture._prepare(
            **_present(
                max_step_advances=max_step_advances,
                max_network_operations=max_network_operations,
                max_seconds=max_seconds,
            )
        )

    def authorize_curiosity_research_proposal(
        self,
        question_id: str,
        expected_plan_digest: str,
        max_step_advances: str = "",
        max_network_operations: str = "",
        max_seconds: str = "",
    ):
        return self._fixture._authorize(
            **_present(
                max_step_advances=max_step_advances,
                max_network_operations=max_network_operations,
                max_seconds=max_seconds,
            )
        )


def _present(**fields: str) -> dict[str, str]:
    """Send only the boxes the operator actually filled in, as the desktop does."""
    return {name: value for name, value in fields.items() if value.strip()}


class OperatorAuthoredConfirmsWhatItRecordsTests(unittest.TestCase):
    """The other surface records the previewed approval, and says exactly that."""

    def setUp(self) -> None:
        self.window, _widgets = build_real_window(plan_authorization_enabled=True)
        self.requested: list = []
        self.window._approval_request = self.requested.append
        self.window._plan_approval_status = SimpleNamespace(set=lambda value: None)

    def test_confirming_without_a_preview_records_nothing(self) -> None:
        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=True
        ) as dialog:
            self.window._confirm_plan_authorization()

        dialog.assert_not_called()
        self.assertEqual(self.requested, [])

    def test_the_dialog_shows_the_budget_the_preview_recorded(self) -> None:
        self.window._previewed_authority = ResearchAutonomyBudget(
            max_network_operations=1, max_step_advances=2
        )
        self.window._previewed_fit = None

        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=True
        ) as dialog:
            self.window._confirm_plan_authorization()

        shown = dialog.call_args.args[1]
        self.assertIn("network operations: 1", shown)
        self.assertEqual(len(self.requested), 1)

    def test_the_dialog_says_later_edits_are_not_part_of_it(self) -> None:
        """Truthful, because confirming records the object Preview built."""
        self.window._previewed_authority = ResearchAutonomyBudget()
        self.window._previewed_fit = None

        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=True
        ) as dialog:
            self.window._confirm_plan_authorization()

        shown = dialog.call_args.args[1]
        self.assertIn("press Preview again", shown)

    def test_declining_records_nothing(self) -> None:
        self.window._previewed_authority = ResearchAutonomyBudget()
        self.window._previewed_fit = None

        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=False
        ):
            self.window._confirm_plan_authorization()

        self.assertEqual(self.requested, [])


class NoReactiveMachineryTests(unittest.TestCase):
    """Nothing recomputes as somebody types; it happens when they press."""

    def test_no_variable_trace_recomputes_a_fit_as_somebody_types(self) -> None:
        """Traces are the mechanism reactive updates would need; there are none.

        Scoped to variable traces on purpose. The window schedules other work
        with `after`, which is unrelated to budgets, and forbidding it here
        would be a guard about something else wearing this test's name.
        """
        for forbidden in ("trace_add", "trace_variable", "trace_write"):
            with self.subTest(name=forbidden):
                self.assertNotIn(forbidden, WINDOW_SOURCE)

    def test_start_is_still_a_separate_action(self) -> None:
        self.assertIn("_start_authorized_curiosity_research_proposal", WINDOW_SOURCE)
        self.assertNotIn(
            "self._start_authorized_curiosity_research_proposal()", WINDOW_SOURCE
        )


if __name__ == "__main__":
    unittest.main()
