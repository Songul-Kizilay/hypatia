"""The budget on an approval is authority, so a person has to have typed it.

Until now the figure was a constant. It was an honest constant — the previous
milestone made sure a plan that could not be paid for was refused — but nobody
could change it, so an operator faced with a plan needing more had no move
except to make the plan smaller, and one needing far less still granted the full
default.

Now they choose, and almost everything here is about the ways choosing could go
wrong. A blank field means "leave that bound alone", never zero. An unreadable
field refuses the approval rather than falling back to a default, because the
fallback direction is the permissive one and "it did not parse, so we used the
usual" is how authority leaks. Nothing above the ceilings the budget already
enforces gets through, and no value meaning "no limit" — infinity, a fraction
rounded up, a boolean that Python would read as one — is accepted.

The system still never picks. It can say what a plan would need and refuse a
grant too small to cover it, but the number it refuses against is the operator's
and is persisted exactly as given: not the default, and pointedly not the
requirement.
"""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from core.Exceptions import ResearchError
from research.ResearchAuthorizationBudgetChoice import budget_from
from research.ResearchAutonomyBudget import (
    MAX_AUTONOMY_NETWORK_OPERATIONS,
    MAX_AUTONOMY_SECONDS,
    MAX_AUTONOMY_STEP_ADVANCES,
    ResearchAutonomyBudget,
)
from research.ResearchPlan import ResearchPlan
from research.ResearchPlanDigest import plan_digest
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from tests.research.test_curiosity_execution_advance import AdvanceFixture

NOW = datetime(2026, 9, 1, tzinfo=UTC)
DISCOVERY = ResearchPlanStepCapability.SOURCE_DISCOVERY
LOCAL = ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH
DEFAULT = ResearchAutonomyBudget()


def plan_of(capabilities, plan_id: str = "plan-1") -> ResearchPlan:
    """Return one validated plan declaring exactly these capabilities."""
    return ResearchPlan(
        plan_id=plan_id,
        question="Can the middleware authorization check be bypassed?",
        steps=tuple(
            ResearchPlanStep(
                step_id=f"step-{index}",
                instruction=f"Carry out authored work {index}.",
                capability=capability,
            )
            for index, capability in enumerate(capabilities, start=1)
        ),
        created_at=NOW,
    )


class ReadingWhatTheOperatorTypedTests(unittest.TestCase):
    def test_an_empty_form_grants_the_standing_default(self) -> None:
        self.assertEqual(budget_from({}), DEFAULT)

    def test_a_blank_field_leaves_that_bound_alone(self) -> None:
        """Blank is not zero. Zero would be a real and very tight answer."""
        chosen = budget_from({"max_network_operations": "   "})

        self.assertEqual(chosen, DEFAULT)

    def test_a_chosen_value_is_taken_exactly(self) -> None:
        chosen = budget_from({"max_network_operations": "2"})

        self.assertEqual(chosen.max_network_operations, 2)

    def test_untouched_dimensions_keep_their_defaults(self) -> None:
        chosen = budget_from({"max_network_operations": "2"})

        self.assertEqual(chosen.max_step_advances, DEFAULT.max_step_advances)
        self.assertEqual(chosen.max_seconds, DEFAULT.max_seconds)

    def test_zero_is_accepted_as_a_real_and_tight_answer(self) -> None:
        chosen = budget_from({"max_network_operations": "0"})

        self.assertEqual(chosen.max_network_operations, 0)

    def test_model_operations_require_an_explicit_bounded_choice(self) -> None:
        chosen = budget_from({"max_llm_operations": "5"})

        self.assertEqual(chosen.max_llm_operations, 5)
        self.assertEqual(budget_from({}).max_llm_operations, 0)
        for value in (True, "bad", -1, 26, 1.5):
            with self.assertRaises(ResearchError):
                budget_from({"max_llm_operations": value})


class RefusingRatherThanFallingBackTests(unittest.TestCase):
    def _refused(self, metadata) -> None:
        with self.assertRaises(ResearchError):
            budget_from(metadata)

    def test_unreadable_text_is_refused(self) -> None:
        self._refused({"max_network_operations": "as much as it takes"})

    def test_unreadable_text_does_not_become_the_default(self) -> None:
        """The dangerous direction is permissive, so there is no fallback."""
        try:
            budget_from({"max_network_operations": "lots"})
        except ResearchError:
            return
        self.fail("an unreadable budget must refuse rather than default")

    def test_a_negative_count_is_refused(self) -> None:
        self._refused({"max_network_operations": "-1"})

    def test_a_fraction_is_refused_rather_than_rounded(self) -> None:
        self._refused({"max_network_operations": "2.5"})

    def test_a_float_count_is_refused(self) -> None:
        self._refused({"max_step_advances": 2.0})

    def test_a_boolean_is_refused(self) -> None:
        """Python would read True as one; an approval must not accept that."""
        self._refused({"max_step_advances": True})

    def test_an_infinite_time_budget_is_refused(self) -> None:
        self._refused({"max_seconds": "inf"})

    def test_a_not_a_number_time_budget_is_refused(self) -> None:
        self._refused({"max_seconds": float("nan")})

    def test_none_is_refused_rather_than_meaning_unlimited(self) -> None:
        self._refused({"max_network_operations": None})

    def test_above_the_ceiling_is_refused(self) -> None:
        self._refused(
            {"max_network_operations": str(MAX_AUTONOMY_NETWORK_OPERATIONS + 1)}
        )

    def test_above_the_advance_ceiling_is_refused(self) -> None:
        self._refused({"max_step_advances": str(MAX_AUTONOMY_STEP_ADVANCES + 1)})

    def test_above_the_time_ceiling_is_refused(self) -> None:
        self._refused({"max_seconds": str(MAX_AUTONOMY_SECONDS + 1)})

    def test_the_ceiling_itself_is_allowed(self) -> None:
        chosen = budget_from(
            {"max_network_operations": str(MAX_AUTONOMY_NETWORK_OPERATIONS)}
        )

        self.assertEqual(chosen.max_network_operations, MAX_AUTONOMY_NETWORK_OPERATIONS)


class TheApprovalKeepsExactlyWhatWasChosenTests(AdvanceFixture):
    """Driven through the real authorization service."""

    def _record(self, capabilities, budget=None, plan_id="plan-under-test"):
        return self.authorization_service.record_for_plan(
            plan_of(capabilities, plan_id=plan_id),
            self.run_id,
            budget=budget,
        )

    def test_no_choice_keeps_the_standing_default(self) -> None:
        authorization = self._record((LOCAL, DISCOVERY))

        self.assertEqual(authorization.budget, DEFAULT)

    def test_a_smaller_but_sufficient_budget_is_allowed(self) -> None:
        """The plan needs one network operation; granting exactly one is enough."""
        chosen = budget_from({"max_network_operations": "1", "max_step_advances": "2"})

        authorization = self._record((LOCAL, DISCOVERY), chosen)

        self.assertIsNotNone(authorization)
        self.assertEqual(authorization.budget.max_network_operations, 1)

    def test_a_smaller_budget_is_not_replaced_by_the_default(self) -> None:
        chosen = budget_from({"max_network_operations": "1", "max_step_advances": "2"})

        authorization = self._record((LOCAL, DISCOVERY), chosen)

        self.assertNotEqual(authorization.budget, DEFAULT)
        self.assertEqual(authorization.budget, chosen)

    def test_a_larger_budget_within_the_ceiling_is_allowed(self) -> None:
        chosen = budget_from(
            {"max_network_operations": "10", "max_step_advances": "10"}
        )

        authorization = self._record((LOCAL, DISCOVERY), chosen)

        self.assertEqual(authorization.budget.max_network_operations, 10)

    def test_an_insufficient_budget_is_still_refused(self) -> None:
        chosen = budget_from({"max_network_operations": "0"})

        with self.assertRaises(ResearchError):
            self._record((LOCAL, DISCOVERY), chosen)

    def test_an_insufficient_choice_records_nothing(self) -> None:
        before = len(list(self.authorization_service.authorizations()))
        chosen = budget_from({"max_step_advances": "1"})

        with self.assertRaises(ResearchError):
            self._record((LOCAL, DISCOVERY), chosen)

        self.assertEqual(len(list(self.authorization_service.authorizations())), before)

    def test_the_chosen_budget_is_not_replaced_by_the_requirement(self) -> None:
        """Granting ten when one is needed grants ten, not one."""
        chosen = budget_from(
            {"max_network_operations": "10", "max_step_advances": "10"}
        )

        authorization = self._record((LOCAL, DISCOVERY), chosen)

        self.assertEqual(authorization.budget.max_network_operations, 10)

    def test_the_digest_is_still_the_plan_identity(self) -> None:
        plan = plan_of((LOCAL, DISCOVERY), plan_id="plan-under-test")
        chosen = budget_from({"max_network_operations": "2", "max_step_advances": "2"})

        authorization = self.authorization_service.record_for_plan(
            plan, self.run_id, budget=chosen
        )

        self.assertEqual(authorization.plan_digest, plan_digest(plan))

    def test_choosing_a_budget_changes_neither_plan_nor_capabilities(self) -> None:
        plain = self._record((LOCAL, DISCOVERY), plan_id="plan-a")
        chosen = budget_from({"max_network_operations": "9", "max_step_advances": "9"})

        generous = self._record((LOCAL, DISCOVERY), chosen, plan_id="plan-b")

        self.assertEqual(plain.capabilities, generous.capabilities)
        self.assertEqual(plain.plan_digest, generous.plan_digest)

    def test_a_second_budget_needs_its_own_approval_record(self) -> None:
        """Nothing edits a granted budget; a different one is a different record."""
        first = self._record((LOCAL, DISCOVERY), plan_id="plan-a")
        chosen = budget_from({"max_network_operations": "9", "max_step_advances": "9"})

        second = self._record((LOCAL, DISCOVERY), chosen, plan_id="plan-b")

        self.assertNotEqual(first.authorization_id, second.authorization_id)
        self.assertEqual(first.budget, DEFAULT)
        self.assertNotEqual(second.budget, DEFAULT)

    def test_choosing_and_approving_performs_no_research(self) -> None:
        chosen = budget_from({"max_network_operations": "9", "max_step_advances": "9"})

        self._record((LOCAL, DISCOVERY), chosen)

        self.assertEqual(self.operation.calls, [])
        self.assertIsNone(self.execution_service.live_execution("plan-under-test"))

    def test_the_fit_is_computed_against_the_chosen_budget(self) -> None:
        chosen = budget_from({"max_network_operations": "0"})

        fit = self.authorization_service.budget_fit_for(
            (plan_of((LOCAL, DISCOVERY))), chosen
        )

        self.assertFalse(fit.sufficient)
        self.assertEqual(fit.network_shortfall, 1)
        self.assertEqual(self.operation.calls, [])


class TheRealProposalCanBeGrantedLessTests(AdvanceFixture):
    """A real curiosity plan, approved with exactly what it needs and no more."""

    def test_the_real_proposal_still_fits_the_default(self) -> None:
        started = self._started()

        plan = self.execution_service.live_plan(started.plan_id)

        self.assertTrue(self.authorization_service.budget_fit_for(plan).sufficient)

    def test_the_real_proposal_fits_a_deliberately_tight_grant(self) -> None:
        started = self._started()
        plan = self.execution_service.live_plan(started.plan_id)
        tight = budget_from({"max_network_operations": "1", "max_step_advances": "2"})

        fit = self.authorization_service.budget_fit_for(plan, tight)

        self.assertTrue(fit.sufficient)
        self.assertLess(tight.max_network_operations, DEFAULT.max_network_operations)

    def test_one_operation_short_refuses_the_real_proposal(self) -> None:
        started = self._started()
        plan = self.execution_service.live_plan(started.plan_id)
        short = budget_from({"max_network_operations": "0"})

        self.assertFalse(
            self.authorization_service.budget_fit_for(plan, short).sufficient
        )


if __name__ == "__main__":
    unittest.main()
