"""What a plan would cost, shown to the person deciding whether to allow it.

Until now an approval said what may be done and said nothing about whether the
budget attached to it could pay for it. Those are different questions, and the
gap between them is quiet: a plan could be approved in full and then stop
partway through for want of a network operation nobody had counted.

So there is now one derivation — attempting each authored step exactly once,
summed from the same `cost_for` the executor charges — and one comparison
against the budget on offer. The comparison is shown before anybody confirms,
and an approval whose budget cannot cover a single clean pass is refused rather
than granted optimistically.

The thing being guarded against most carefully is the obvious shortcut. Knowing
what a plan needs must never become permission to have it: the requirement is
calculated, displayed, and compared, and at no point does it raise the budget to
fit. An insufficient plan is refused, not funded.

The number is a floor and never a forecast. It counts one attempt per authored
step — no retries, because nothing retries; no preparation, approval or start,
because those reach no operation; and no human decisions, because those are not
authored steps and never execute.
"""

from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from core.Exceptions import ResearchError
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchCapabilityCost import cost_for
from research.ResearchPlan import ResearchPlan
from research.ResearchPlanAuthorization import capabilities_of
from research.ResearchPlanBudgetRequirement import (
    ResearchPlanBudgetFit,
    required_advances,
    required_cost,
)
from research.ResearchPlanDigest import plan_digest
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from tests.research.test_curiosity_execution_advance import AdvanceFixture

NOW = datetime(2026, 9, 1, tzinfo=UTC)
DISCOVERY = ResearchPlanStepCapability.SOURCE_DISCOVERY
LOCAL = ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH
NONE = ResearchPlanStepCapability.NONE
#: Four discoveries need four network operations; the default budget approves
#: three. An ordinary authored plan, with no invented provider behind it.
UNAFFORDABLE = (LOCAL, DISCOVERY, DISCOVERY, DISCOVERY, DISCOVERY)


def plan_of(capabilities, plan_id: str = "plan-1") -> ResearchPlan:
    """Return one validated plan whose steps declare exactly these capabilities."""
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


class TheRequirementIsDerivedNotInventedTests(unittest.TestCase):
    def test_the_same_plan_costs_the_same_every_time(self) -> None:
        plan = plan_of((LOCAL, DISCOVERY))

        self.assertEqual(
            required_cost(plan), required_cost(plan_of((LOCAL, DISCOVERY)))
        )

    def test_the_order_of_steps_does_not_change_the_total(self) -> None:
        """Cost is a sum. Ordering is a plan's business, not arithmetic's."""
        forward = required_cost(plan_of((LOCAL, DISCOVERY)))

        backward = required_cost(plan_of((DISCOVERY, LOCAL)))

        self.assertEqual(forward, backward)

    def test_a_local_step_adds_no_network_cost(self) -> None:
        local_only = required_cost(plan_of((LOCAL, LOCAL, LOCAL)))

        self.assertEqual(local_only.network_operations, 0)

    def test_discovery_costs_exactly_what_the_registry_says(self) -> None:
        cost = required_cost(plan_of((DISCOVERY,)))

        self.assertEqual(cost, cost_for(DISCOVERY))

    def test_each_step_is_counted_once_and_not_twice(self) -> None:
        """No retry allowance hides inside the requirement; nothing retries."""
        cost = required_cost(plan_of((DISCOVERY, DISCOVERY, DISCOVERY)))

        self.assertEqual(
            cost.network_operations,
            3 * cost_for(DISCOVERY).network_operations,
        )

    def test_a_step_declaring_no_capability_costs_nothing(self) -> None:
        """Only authored, executable work counts toward the requirement."""
        with_none = required_cost(plan_of((LOCAL, DISCOVERY, NONE)))

        self.assertEqual(with_none, required_cost(plan_of((LOCAL, DISCOVERY))))

    def test_the_advance_count_is_the_authored_step_count(self) -> None:
        self.assertEqual(required_advances(plan_of((LOCAL, DISCOVERY))), 2)

    def test_a_plan_is_required_rather_than_assumed(self) -> None:
        with self.assertRaises(ResearchError):
            required_cost("not a plan")


class TheFitComparesTwoRealThingsTests(unittest.TestCase):
    def _fit(self, capabilities, budget=None) -> ResearchPlanBudgetFit:
        return ResearchPlanBudgetFit.of(
            plan_of(capabilities), budget or ResearchAutonomyBudget()
        )

    def test_a_plan_within_the_budget_fits(self) -> None:
        self.assertTrue(self._fit((LOCAL, DISCOVERY)).sufficient)

    def test_a_plan_needing_more_network_than_approved_does_not_fit(self) -> None:
        fit = self._fit(UNAFFORDABLE)

        self.assertFalse(fit.sufficient)
        self.assertEqual(
            fit.network_shortfall,
            required_cost(plan_of(UNAFFORDABLE)).network_operations
            - ResearchAutonomyBudget().max_network_operations,
        )

    def test_a_plan_needing_more_advances_than_approved_does_not_fit(self) -> None:
        """Every step needs an advance, even the ones that cost no network."""
        budget = ResearchAutonomyBudget()
        fit = self._fit(tuple(LOCAL for _ in range(budget.max_step_advances + 1)))

        self.assertFalse(fit.sufficient)
        self.assertEqual(fit.advance_shortfall, 1)
        self.assertEqual(fit.network_shortfall, 0)

    def test_the_shortfall_names_the_dimension_rather_than_a_sentence(self) -> None:
        fit = self._fit(UNAFFORDABLE)

        self.assertIsInstance(fit.network_shortfall, int)
        self.assertIsInstance(fit.advance_shortfall, int)
        self.assertIsInstance(fit.llm_shortfall, int)

    def test_the_fit_never_alters_the_budget_it_was_given(self) -> None:
        budget = ResearchAutonomyBudget()

        fit = self._fit(UNAFFORDABLE, budget)

        self.assertEqual(fit.budget, budget)

    def test_the_rendering_shows_required_beside_approved(self) -> None:
        rendered = "\n".join(self._fit((LOCAL, DISCOVERY)).lines())

        self.assertIn("Network operations required: 1", rendered)
        self.assertIn(
            f"approved: {ResearchAutonomyBudget().max_network_operations}", rendered
        )

    def test_the_rendering_never_calls_a_requirement_a_permission(self) -> None:
        sufficient = "\n".join(self._fit((LOCAL, DISCOVERY)).lines()).casefold()
        insufficient = "\n".join(self._fit(UNAFFORDABLE).lines()).casefold()

        self.assertIn("not a promise the plan will finish", sufficient)
        self.assertIn("not what a person has granted", insufficient)
        self.assertIn("insufficient", insufficient)


class AuthorizationRefusesWhatItCannotPayForTests(AdvanceFixture):
    """The approval boundary, exercised through the real service."""

    def _record(self, capabilities):
        return self.authorization_service.record_for_plan(
            plan_of(capabilities, plan_id="plan-under-test"),
            self.run_id,
        )

    def test_an_affordable_plan_may_be_approved(self) -> None:
        authorization = self._record((LOCAL, DISCOVERY))

        self.assertIsNotNone(authorization)

    def test_an_unaffordable_plan_is_refused(self) -> None:
        with self.assertRaises(ResearchError):
            self._record(UNAFFORDABLE)

    def test_the_refusal_names_the_shortage(self) -> None:
        with self.assertRaises(ResearchError) as refusal:
            self._record(UNAFFORDABLE)

        self.assertIn("Short by", str(refusal.exception))

    def test_a_refusal_records_no_authorization(self) -> None:
        before = len(list(self.authorization_service.authorizations()))

        with self.assertRaises(ResearchError):
            self._record(UNAFFORDABLE)

        self.assertEqual(len(list(self.authorization_service.authorizations())), before)

    def test_a_refusal_reaches_no_provider(self) -> None:
        with self.assertRaises(ResearchError):
            self._record(UNAFFORDABLE)

        self.assertEqual(self.operation.calls, [])

    def test_a_refusal_starts_no_execution(self) -> None:
        with self.assertRaises(ResearchError):
            self._record(UNAFFORDABLE)

        self.assertIsNone(self.execution_service.live_execution("plan-under-test"))

    def test_approval_does_not_resize_the_budget_to_the_plan(self) -> None:
        """The requirement is calculated, never converted into permission."""
        authorization = self._record((LOCAL, DISCOVERY))

        self.assertEqual(authorization.budget, ResearchAutonomyBudget())

    def test_the_digest_is_still_what_the_approval_is_bound_to(self) -> None:
        plan = plan_of((LOCAL, DISCOVERY), plan_id="plan-under-test")

        authorization = self.authorization_service.record_for_plan(plan, self.run_id)

        self.assertEqual(authorization.plan_digest, plan_digest(plan))

    def test_capabilities_are_still_exactly_those_authored(self) -> None:
        plan = plan_of((LOCAL, DISCOVERY), plan_id="plan-under-test")

        authorization = self.authorization_service.record_for_plan(plan, self.run_id)

        self.assertEqual(authorization.capabilities, capabilities_of(plan))

    def test_changing_the_cost_changes_the_digest(self) -> None:
        """A cheaper plan is a different plan, and needs its own approval."""
        cheap = plan_of((LOCAL, DISCOVERY), plan_id="plan-under-test")
        dearer = replace(
            cheap,
            steps=cheap.steps
            + (
                ResearchPlanStep(
                    step_id="step-3",
                    instruction="Discover further candidate sources.",
                    capability=DISCOVERY,
                ),
            ),
        )

        self.assertNotEqual(plan_digest(cheap), plan_digest(dearer))
        self.assertNotEqual(required_cost(cheap), required_cost(dearer))

    def test_the_service_reports_the_fit_without_approving_anything(self) -> None:
        before = len(list(self.authorization_service.authorizations()))

        fit = self.authorization_service.budget_fit_for(plan_of(UNAFFORDABLE))

        self.assertFalse(fit.sufficient)
        self.assertEqual(len(list(self.authorization_service.authorizations())), before)


class TheRealCuriosityPlanFitsTodayTests(AdvanceFixture):
    """Pinned deliberately: today's real proposals are inside the default budget.

    Two providers exist, so the largest proposal Hypatia can currently author is
    a local search plus one discovery per provider. That fits, and this records
    the fact rather than leaving a future reader to assume the refusal path is
    unreachable in practice. It is reachable — by a larger authored plan, which
    the tests above use — just not by anything Curiosity writes today.
    """

    def test_the_real_proposal_fits_the_default_budget(self) -> None:
        started = self._started()

        plan = self.execution_service.live_plan(started.plan_id)

        fit = self.authorization_service.budget_fit_for(plan)
        self.assertTrue(fit.sufficient)
        self.assertEqual(fit.required.network_operations, 1)
        self.assertEqual(fit.required_advances, 2)

    def test_the_widest_proposal_shape_available_today_still_fits(self) -> None:
        """Local search plus one discovery for each provider that exists."""
        from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName

        widest = plan_of(
            (LOCAL,) + tuple(DISCOVERY for _ in ResearchDiscoveryProviderName)
        )

        self.assertTrue(self.authorization_service.budget_fit_for(widest).sufficient)


if __name__ == "__main__":
    unittest.main()
