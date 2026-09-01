"""Confirming grants the budget in front of you, against the plan you previewed.

Two things were being settled at once and only one of them should have been.
Preview decided the plan, which is right — that is what a person read and what
the digest names. It also froze the budget, which is not: the budget is a number
somebody types, and nothing about typing it later makes the plan a different
plan.

So confirming now reads the budget as it stands, checks it against the plan
Preview settled, and records that. A grant is refused for being too small or
unusable, never quietly replaced — not by the older figure that happened to
parse, not by the default, and not by what the plan turns out to need.

Plan identity is the thing held still throughout. The approval is built by
replacing one field on the previewed object, which cannot reach the digest or
the capabilities, so no amount of budget editing can turn one approved plan into
another. The tests below check that from both ends: the digest is unchanged, and
so are the steps behind it.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from research.ResearchAutonomyBudget import (
    MAX_AUTONOMY_NETWORK_OPERATIONS,
    ResearchAutonomyBudget,
)
from tests.integration.test_research_plan_authorization_flow import (
    STEPS,
    AuthorizationFixture,
)

DEFAULT = ResearchAutonomyBudget()


class ConfirmBindsCurrentBudgetTests(AuthorizationFixture):
    """Preview the plan, change the number, confirm."""

    def _previewed(self, service):
        response = self.preview(service)
        assert response.research_plan_authorization is not None
        return response.research_plan_authorization

    def _confirm(self, service, authorization_id: str, **budget: object):
        return service.process_confirm(
            self.request(
                "research_plan_authorization_confirm",
                authorization_id=authorization_id,
                research_run_id=self.run_id,
                research_plan_question=self.preview_request().metadata[
                    "research_plan_question"
                ],
                research_plan_steps=STEPS,
                **budget,
            )
        )

    def test_confirming_without_a_choice_keeps_the_standing_default(self) -> None:
        service = self.service()
        previewed = self._previewed(service)

        confirmed = self._confirm(service, previewed.authorization_id)

        self.assertEqual(confirmed.research_plan_authorization.budget, DEFAULT)

    def test_a_budget_chosen_after_preview_is_the_one_recorded(self) -> None:
        """Nobody has to preview again to approve a number they just changed."""
        service = self.service()
        previewed = self._previewed(service)

        confirmed = self._confirm(
            service,
            previewed.authorization_id,
            max_network_operations="2",
            max_step_advances="4",
        )

        budget = confirmed.research_plan_authorization.budget
        self.assertEqual(budget.max_network_operations, 2)
        self.assertEqual(budget.max_step_advances, 4)

    def test_the_previewed_budget_does_not_override_the_current_one(self) -> None:
        service = self.service()
        previewed = self._previewed(service)

        confirmed = self._confirm(
            service,
            previewed.authorization_id,
            max_network_operations="2",
            max_step_advances="4",
        )

        self.assertNotEqual(confirmed.research_plan_authorization.budget, DEFAULT)
        self.assertNotEqual(
            confirmed.research_plan_authorization.budget, previewed.budget
        )

    def test_a_higher_grant_within_the_ceiling_is_recorded(self) -> None:
        service = self.service()
        previewed = self._previewed(service)

        confirmed = self._confirm(
            service,
            previewed.authorization_id,
            max_network_operations=str(MAX_AUTONOMY_NETWORK_OPERATIONS),
            max_step_advances="10",
        )

        self.assertEqual(
            confirmed.research_plan_authorization.budget.max_network_operations,
            MAX_AUTONOMY_NETWORK_OPERATIONS,
        )

    def test_seconds_chosen_at_confirm_are_recorded(self) -> None:
        service = self.service()
        previewed = self._previewed(service)

        confirmed = self._confirm(
            service, previewed.authorization_id, max_seconds="120"
        )

        self.assertEqual(confirmed.research_plan_authorization.budget.max_seconds, 120)


class ChangingTheBudgetDoesNotChangeThePlanTests(ConfirmBindsCurrentBudgetTests):
    def test_the_digest_is_the_previewed_digest(self) -> None:
        service = self.service()
        previewed = self._previewed(service)

        confirmed = self._confirm(
            service,
            previewed.authorization_id,
            max_network_operations="2",
            max_step_advances="4",
        )

        self.assertEqual(
            confirmed.research_plan_authorization.plan_digest, previewed.plan_digest
        )

    def test_the_capabilities_are_the_previewed_capabilities(self) -> None:
        service = self.service()
        previewed = self._previewed(service)

        confirmed = self._confirm(
            service,
            previewed.authorization_id,
            max_network_operations="2",
            max_step_advances="4",
        )

        self.assertEqual(
            confirmed.research_plan_authorization.capabilities, previewed.capabilities
        )

    def test_the_identity_is_the_previewed_identity(self) -> None:
        """One human confirmation, one record, keeping the identity shown."""
        service = self.service()
        previewed = self._previewed(service)

        confirmed = self._confirm(
            service, previewed.authorization_id, max_network_operations="2"
        )

        self.assertEqual(
            confirmed.research_plan_authorization.authorization_id,
            previewed.authorization_id,
        )

    def test_only_the_budget_differs_from_the_previewed_approval(self) -> None:
        from dataclasses import replace

        service = self.service()
        previewed = self._previewed(service)

        confirmed = self._confirm(
            service, previewed.authorization_id, max_network_operations="2"
        ).research_plan_authorization

        self.assertEqual(replace(confirmed, budget=previewed.budget), previewed)


class AnUnusableOrTooSmallGrantIsRefusedTests(ConfirmBindsCurrentBudgetTests):
    def _refused(self, **budget: object):
        service = self.service()
        previewed = self._previewed(service)
        response = self._confirm(service, previewed.authorization_id, **budget)
        self.assertIsNone(response.research_plan_authorization)
        self.assertEqual(list(service.authorizations()), [])
        return response

    def test_a_grant_too_small_for_the_plan_refuses(self) -> None:
        response = self._refused(max_network_operations="0")

        self.assertIn("Short by", response.message)

    def test_too_few_advances_refuses(self) -> None:
        self._refused(max_step_advances="1")

    def test_unreadable_input_refuses(self) -> None:
        response = self._refused(max_network_operations="plenty")

        self.assertIn("whole number", response.message)

    def test_unreadable_input_is_not_rescued_by_the_previewed_budget(self) -> None:
        """The older figure parsed; that is no reason to grant it now."""
        service = self.service()
        previewed = self._previewed(service)

        self._confirm(
            service, previewed.authorization_id, max_network_operations="plenty"
        )

        self.assertEqual(list(service.authorizations()), [])

    def test_a_negative_grant_refuses(self) -> None:
        self._refused(max_network_operations="-1")

    def test_a_fractional_grant_refuses(self) -> None:
        self._refused(max_step_advances="2.5")

    def test_an_above_ceiling_grant_refuses(self) -> None:
        self._refused(max_network_operations=str(MAX_AUTONOMY_NETWORK_OPERATIONS + 1))

    def test_an_unlimited_time_grant_refuses(self) -> None:
        self._refused(max_seconds="inf")

    def test_a_refused_grant_leaves_the_preview_standing(self) -> None:
        """The plan is still the plan; only the number was wrong."""
        service = self.service()
        previewed = self._previewed(service)
        self._confirm(service, previewed.authorization_id, max_network_operations="0")

        recovered = self._confirm(
            service, previewed.authorization_id, max_network_operations="2"
        )

        self.assertIsNotNone(recovered.research_plan_authorization)
        self.assertEqual(
            recovered.research_plan_authorization.budget.max_network_operations, 2
        )

    def test_the_requirement_never_becomes_the_grant(self) -> None:
        service = self.service()
        previewed = self._previewed(service)

        confirmed = self._confirm(
            service, previewed.authorization_id, max_network_operations="9"
        )

        self.assertEqual(
            confirmed.research_plan_authorization.budget.max_network_operations, 9
        )


if __name__ == "__main__":
    unittest.main()
