"""What the grant permits, shown where a person arms an unattended run.

This is the last control in the chain that asks a human to authorize something
that will happen when they are not watching. It named the grant — "Deferred
grant: grant-1" — and stopped there. An identifier is not a description: the
operator could see *which* authority was about to be used but not *what it
allows*, which is the one thing worth reading before pressing the button.

The grant already carries its own restriction snapshot, so nothing needs
deriving. The screen shows that record and only that record. Re-deriving from
the current plan would be the subtle mistake available here: a grant is a
statement about the plan as it stood when the grant was made, and a plan can
move afterwards. What the grant recorded is what the run is permitted under.

Reading this screen is inert. It arms nothing, writes nothing, and touches no
grant, task, execution or budget; only the explicit confirmation that follows
creates a schedule.

Deterministic. No network, no model, no execution.
"""

from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from research.DeferredGrantAuthorizer import DeferredGrantAuthorizer
from research.ResearchPlanRestriction import ResearchPlanRestriction
from tests.research.test_deferred_execution_grants import grant_for
from tests.research.test_one_shot_deferred_execution import (
    RUN_AT,
    OneShotFixture,
    Value,
)

NO_EXTERNAL = ResearchPlanRestriction.NO_EXTERNAL_SOURCE_ACCESS


class GrantVisibilityFixture(OneShotFixture):
    """Shared setup: a plan and its grant that genuinely agree."""

    def _restrict(self, restrictions) -> None:
        """Put the same restriction on the plan and on its grant.

        Both, deliberately. A grant claiming a restriction its plan does not
        carry is a mismatch and is already ineligible, so restricting only the
        grant would test the refusal path instead of the display.
        """
        if restrictions:
            from research.ResearchPlanConstraint import ResearchPlanConstraint
            from research.ResearchPlanExecutionState import (
                ResearchPlanExecutionState,
            )

            self.context.plan = replace(
                self.context.plan,
                constraints=tuple(
                    ResearchPlanConstraint(
                        text="Do not access external sources.", restriction=value
                    )
                    for value in sorted(restrictions, key=lambda v: v.value)
                ),
            )
            self.context.execution = ResearchPlanExecutionState.prepare(
                self.context.plan
            ).start()
        [stored] = self.grants.records
        self.grants.records = [
            replace(
                stored,
                plan_digest=self._digest(),
                approved_restrictions=restrictions,
            )
        ]

    def _digest(self) -> str:
        from research.ResearchPlanDigest import plan_digest

        return plan_digest(self.context.plan)


class ArmingShowsWhatTheGrantPermitsTests(GrantVisibilityFixture):
    """Driven through the real scheduler, which is what the desktop calls."""

    def test_case_a_a_restricted_grant_names_its_restriction(self) -> None:
        self._restrict(frozenset({NO_EXTERNAL}))

        view = self.service.preview("task-1", RUN_AT)

        self.assertEqual(view.approved_restrictions_text, "no_external_source_access")
        self.assertIn(
            "Approved restrictions: no_external_source_access",
            view.confirmation_text(),
        )

    def test_case_b_a_recorded_empty_grant_says_none(self) -> None:
        self._restrict(frozenset())

        view = self.service.preview("task-1", RUN_AT)

        self.assertEqual(view.approved_restrictions_text, "none")
        self.assertIn("Approved restrictions: none", view.confirmation_text())

    def test_the_confirmation_still_names_the_grant_and_time(self) -> None:
        """The new line adds to the existing identity, it does not replace it."""
        view = self.service.preview("task-1", RUN_AT)
        text = view.confirmation_text()

        self.assertIn("Deferred grant: grant-1", text)
        self.assertIn("Run once at:", text)
        self.assertIn("never repeats", text)

    def test_the_armed_view_describes_the_same_grant(self) -> None:
        self._restrict(frozenset({NO_EXTERNAL}))

        view = self.service.schedule("task-1", RUN_AT)

        self.assertIsNotNone(view.schedule)
        self.assertEqual(view.approved_restrictions_text, "no_external_source_access")


class TheDisplayedGrantIsTheGrantBeingArmedTests(GrantVisibilityFixture):
    """Case D: two grants, and only the selected one may speak."""

    def test_only_the_selected_grants_state_is_shown(self) -> None:
        self._restrict(frozenset({NO_EXTERNAL}))
        [stored] = self.grants.records
        self.grants.records = [replace(stored, grant_id="grant-a")]

        view = self.service.preview("task-1", RUN_AT)

        self.assertEqual(view.grant_id, "grant-a")
        self.assertEqual(view.approved_restrictions_text, "no_external_source_access")

    def test_a_second_unrestricted_grant_does_not_leak_into_the_display(
        self,
    ) -> None:
        """A revoked sibling must not become the thing described."""
        self._restrict(frozenset({NO_EXTERNAL}))
        [stored] = self.grants.records
        restricted = replace(stored, grant_id="grant-a")
        retired = replace(
            stored, grant_id="grant-b", approved_restrictions=frozenset()
        ).revoked(RUN_AT, DeferredGrantAuthorizer.TRUSTED_LOCAL_OPERATOR)
        self.grants.records = [restricted, retired]

        view = self.service.preview("task-1", RUN_AT)

        self.assertEqual(view.grant_id, "grant-a")
        self.assertEqual(view.approved_restrictions_text, "no_external_source_access")

    def test_the_view_reports_the_grant_it_was_given(self) -> None:
        view = self.service.preview("task-1", RUN_AT)

        assert view.grant is not None
        self.assertEqual(view.grant.grant_id, view.grant_id)


class TheGrantIsTheAuditSourceTests(unittest.TestCase):
    """Never the current plan, and never free-form constraint wording."""

    def test_a_legacy_grant_reads_as_unavailable_not_none(self) -> None:
        """Unknown stays unknown wherever an existing grant is described."""
        from tests.research.test_deferred_execution_grants import Context

        context = Context()
        legacy = replace(grant_for(context), approved_restrictions=None)

        self.assertEqual(
            legacy.approved_restrictions_text, "unavailable for legacy grant"
        )

    def test_the_view_without_a_grant_says_unavailable_not_none(self) -> None:
        from research.OneShotDeferredExecutionScheduleView import (
            OneShotDeferredExecutionScheduleView,
        )

        view = OneShotDeferredExecutionScheduleView(
            task_id="task-1", grant_id="grant-1", run_at=RUN_AT
        )

        self.assertEqual(view.approved_restrictions_text, "unavailable")
        self.assertNotEqual(view.approved_restrictions_text, "none")

    def test_the_wording_is_the_grants_own(self) -> None:
        """One phrasing for an existing grant, shared by every screen."""
        from research.DeferredExecutionControlView import (
            DeferredExecutionControlView,
        )
        from research.DeferredExecutionEligibility import DeferredExecutionDecision
        from research.ResearchAutonomyBudget import ResearchAutonomyBudget
        from tests.research.test_deferred_execution_grants import Context

        context = Context()
        granted = replace(
            grant_for(context), approved_restrictions=frozenset({NO_EXTERNAL})
        )
        control = DeferredExecutionControlView(
            task_id="task-1",
            execution_id="execution-1",
            plan_digest="a" * 64,
            task_budget=ResearchAutonomyBudget(),
            grant=granted,
            decision=DeferredExecutionDecision(True, "deferred_eligible"),
        )

        self.assertEqual(
            control.approved_restrictions_text, granted.approved_restrictions_text
        )

    def test_no_free_text_becomes_a_restriction(self) -> None:
        from research.ResearchPlanConstraint import ResearchPlanConstraint
        from tests.research.test_deferred_execution_grants import Context

        context = Context()
        advisory = ResearchPlanConstraint(text="Do not access external sources.")
        bare = replace(grant_for(context), approved_restrictions=frozenset())

        self.assertIsNone(advisory.restriction)
        self.assertEqual(bare.approved_restrictions_text, "none")


class OpeningTheConfirmationArmsNothingTests(GrantVisibilityFixture):
    def test_preview_persists_no_schedule(self) -> None:
        self.service.preview("task-1", RUN_AT)

        self.assertEqual(self.schedules.records, [])

    def test_preview_leaves_the_grant_untouched(self) -> None:
        before = list(self.grants.records)

        self.service.preview("task-1", RUN_AT)

        self.assertEqual(self.grants.records, before)

    def test_preview_leaves_task_execution_and_budget_untouched(self) -> None:
        task = self.context.task
        execution = self.context.execution
        allowance = self.context.allowance

        self.service.preview("task-1", RUN_AT)

        self.assertEqual(self.context.task, task)
        self.assertEqual(self.context.execution, execution)
        self.assertEqual(self.context.allowance, allowance)

    def test_preview_runs_no_task(self) -> None:
        self.service.preview("task-1", RUN_AT)

        self.assertEqual(self.runner.calls, [])

    def test_arming_still_requires_the_explicit_call(self) -> None:
        self.service.preview("task-1", RUN_AT)
        self.assertEqual(self.schedules.records, [])

        self.service.schedule("task-1", RUN_AT)

        self.assertEqual(len(self.schedules.records), 1)


class StatusShowsTheRecordedGrantTests(GrantVisibilityFixture):
    """Status describes the authority named by the stored schedule."""

    def test_status_shows_the_exact_grants_restrictions(self) -> None:
        self._restrict(frozenset({NO_EXTERNAL}))
        armed = self.service.schedule("task-1", RUN_AT)

        status = self.service.status("task-1")

        assert status is not None
        self.assertEqual(status.schedule, armed.schedule)
        self.assertEqual(status.grant_id, "grant-1")
        self.assertEqual(status.approved_restrictions_text, "no_external_source_access")

    def test_a_revoked_record_still_truthfully_describes_what_was_armed(self) -> None:
        self._restrict(frozenset({NO_EXTERNAL}))
        self.service.schedule("task-1", RUN_AT)
        [stored] = self.grants.records
        self.grants.records = [
            stored.revoked(RUN_AT, DeferredGrantAuthorizer.TRUSTED_LOCAL_OPERATOR)
        ]

        status = self.service.status("task-1")

        assert status is not None
        assert status.grant is not None
        self.assertFalse(status.grant.active)
        self.assertEqual(status.approved_restrictions_text, "no_external_source_access")

    def test_a_different_active_grant_is_never_substituted(self) -> None:
        self._restrict(frozenset({NO_EXTERNAL}))
        self.service.schedule("task-1", RUN_AT)
        [stored] = self.grants.records
        self.grants.records = [replace(stored, grant_id="grant-other")]

        status = self.service.status("task-1")

        assert status is not None
        self.assertEqual(status.grant_id, "grant-1")
        self.assertIsNone(status.grant)
        self.assertEqual(status.approved_restrictions_text, "unavailable")

    def test_reading_status_changes_nothing_and_runs_nothing(self) -> None:
        self.service.schedule("task-1", RUN_AT)
        before_schedules = list(self.schedules.records)
        before_grants = list(self.grants.records)
        before_task = self.context.task
        before_execution = self.context.execution
        before_allowance = self.context.allowance

        self.service.status("task-1")

        self.assertEqual(self.schedules.records, before_schedules)
        self.assertEqual(self.grants.records, before_grants)
        self.assertEqual(self.context.task, before_task)
        self.assertEqual(self.context.execution, before_execution)
        self.assertEqual(self.context.allowance, before_allowance)
        self.assertEqual(self.runner.calls, [])


class DesktopStatusSurfaceTests(GrantVisibilityFixture):
    def test_refresh_names_the_exact_grant_and_its_restrictions(self) -> None:
        from desktop.TkinterDesktopWindow import TkinterDesktopWindow

        self._restrict(frozenset({NO_EXTERNAL}))
        self.service.schedule("task-1", RUN_AT)
        view = self.service.status("task-1")
        window = object.__new__(TkinterDesktopWindow)
        window._controller = SimpleNamespace(
            one_shot_deferred_execution_status=lambda task_id: view
        )
        window._scheduler_task_id = Value("task-1")
        window._one_shot_deferred_status = Value()

        window._refresh_one_shot_deferred_execution()

        self.assertIn("Deferred grant: grant-1", window._one_shot_deferred_status.value)
        self.assertIn(
            "Approved restrictions: no_external_source_access",
            window._one_shot_deferred_status.value,
        )


class IneligibleGrantsStillNeverReachTheScreenTests(GrantVisibilityFixture):
    """Behaviour preserved, and worth stating: eligibility comes first."""

    def test_a_revoked_grant_refuses_before_any_rendering(self) -> None:
        from core.Exceptions import ResearchError

        [stored] = self.grants.records
        self.grants.records = [
            stored.revoked(RUN_AT, DeferredGrantAuthorizer.TRUSTED_LOCAL_OPERATOR)
        ]

        with self.assertRaises(ResearchError):
            self.service.preview("task-1", RUN_AT)

    def test_an_unrecorded_legacy_grant_refuses_before_any_rendering(self) -> None:
        """So case C cannot arise here: it is refused, not displayed."""
        from core.Exceptions import ResearchError

        [stored] = self.grants.records
        self.grants.records = [replace(stored, approved_restrictions=None)]

        with self.assertRaises(ResearchError):
            self.service.preview("task-1", RUN_AT)

    def test_no_grant_at_all_refuses(self) -> None:
        from core.Exceptions import ResearchError

        self.grants.records = []

        with self.assertRaises(ResearchError):
            self.service.preview("task-1", RUN_AT)


if __name__ == "__main__":
    unittest.main()
