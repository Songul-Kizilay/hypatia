"""The same budget question, asked about the plan Hypatia proposed for itself.

An operator-authored plan already let the person granting it choose the
authority. A Curiosity proposal did not, which made it the one place where
Hypatia's own suggestion was approved on terms nobody picked. That asymmetry is
the whole of this: same parser, same comparison, same refusals, applied to the
plan the system wrote rather than the one a person typed.

Reusing rather than reimplementing is the point, so the tests care as much about
what was *not* added as what was. There is one budget parser, one fit
calculation and one set of ceilings; a Curiosity-only copy of any of them would
be a second place for the rules to drift, and the last test here says so
directly.

Everything else is the familiar shape. Blank means "grant the usual", never
zero. Unreadable input refuses instead of falling back, because falling back
goes the permissive way. What was typed is persisted exactly — not the default
it replaced, and not the requirement it has to clear. And none of it runs
anything: choosing a budget and being refused one both reach no provider.
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

from brain.BrainRequest import BrainRequest
from cognition.CuriosityApplicationService import (
    CURIOSITY_AUTHORIZE_PROPOSAL_INTENT,
    CURIOSITY_PREPARE_PROPOSAL_INTENT,
)
from research.ResearchAutonomyBudget import (
    MAX_AUTONOMY_NETWORK_OPERATIONS,
    MAX_AUTONOMY_SECONDS,
    MAX_AUTONOMY_STEP_ADVANCES,
    ResearchAutonomyBudget,
)
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from tests.research.test_curiosity_execution_advance import AdvanceFixture

DEFAULT = ResearchAutonomyBudget()
#: What today's real proposal needs: a local search then one discovery.
REQUIRED_ADVANCES = 2
REQUIRED_NETWORK = 1


class CuriosityBudgetFixture(AdvanceFixture):
    """The real proposal chain, with the budget fields an operator can fill in."""

    def setUp(self) -> None:
        super().setUp()
        self.service.process_question_accept(
            self._request(
                "curiosity_question_accept",
                curiosity_question_id=self.question.question_id,
            )
        )

    def _prepare(self, **budget: str):
        return self.service.process_prepare_proposal(
            BrainRequest(
                message="Prepare",
                metadata={
                    "intent": CURIOSITY_PREPARE_PROPOSAL_INTENT,
                    "curiosity_question_id": self.question.question_id,
                    **budget,
                },
            )
        )

    def _authorize(self, **budget: str):
        digest = self._prepare().curiosity_proposal.digest
        return self.service.process_authorize_proposal(
            BrainRequest(
                message="Authorize",
                metadata={
                    "intent": CURIOSITY_AUTHORIZE_PROPOSAL_INTENT,
                    "curiosity_question_id": self.question.question_id,
                    "expected_plan_digest": digest,
                    **budget,
                },
            )
        )

    def _authorizations(self):
        return list(self.authorization_service.authorizations())


class TheDefaultStillAppliesWhenNobodyChoosesTests(CuriosityBudgetFixture):
    def test_blank_fields_grant_the_standing_default(self) -> None:
        response = self._authorize()

        self.assertEqual(response.research_plan_authorization.budget, DEFAULT)

    def test_omitted_fields_grant_the_standing_default(self) -> None:
        """Absent and blank mean the same thing: leave it alone."""
        response = self._authorize(max_network_operations="   ")

        self.assertEqual(response.research_plan_authorization.budget, DEFAULT)

    def test_the_real_proposal_fits_the_default(self) -> None:
        authorization = self._authorize().research_plan_authorization

        self.assertIsNotNone(authorization)
        self.assertEqual(authorization.budget, DEFAULT)


class TheOperatorMayGrantLessTests(CuriosityBudgetFixture):
    def test_exactly_what_the_plan_needs_is_enough(self) -> None:
        response = self._authorize(
            max_step_advances=str(REQUIRED_ADVANCES),
            max_network_operations=str(REQUIRED_NETWORK),
        )

        budget = response.research_plan_authorization.budget
        self.assertEqual(budget.max_step_advances, REQUIRED_ADVANCES)
        self.assertEqual(budget.max_network_operations, REQUIRED_NETWORK)

    def test_a_tighter_grant_is_not_replaced_by_the_default(self) -> None:
        response = self._authorize(
            max_step_advances=str(REQUIRED_ADVANCES),
            max_network_operations=str(REQUIRED_NETWORK),
        )

        budget = response.research_plan_authorization.budget
        self.assertNotEqual(budget, DEFAULT)
        self.assertLess(budget.max_network_operations, DEFAULT.max_network_operations)

    def test_a_generous_grant_is_not_reduced_to_the_requirement(self) -> None:
        """Granting ten grants ten, not the one the plan happens to need."""
        response = self._authorize(max_step_advances="10", max_network_operations="10")

        budget = response.research_plan_authorization.budget
        self.assertEqual(budget.max_network_operations, 10)

    def test_a_grant_at_the_ceiling_is_allowed(self) -> None:
        response = self._authorize(
            max_step_advances=str(MAX_AUTONOMY_STEP_ADVANCES),
            max_network_operations=str(MAX_AUTONOMY_NETWORK_OPERATIONS),
        )

        self.assertEqual(
            response.research_plan_authorization.budget.max_network_operations,
            MAX_AUTONOMY_NETWORK_OPERATIONS,
        )

    def test_seconds_may_be_granted_within_the_ceiling(self) -> None:
        response = self._authorize(max_seconds="120")

        self.assertEqual(response.research_plan_authorization.budget.max_seconds, 120)


class AnInsufficientGrantIsRefusedTests(CuriosityBudgetFixture):
    def _refused(self, **budget: str):
        response = self._authorize(**budget)
        self.assertIsNone(response.research_plan_authorization)
        return response

    def test_too_few_advances_refuses(self) -> None:
        self._refused(max_step_advances="1")

    def test_no_network_operations_refuses(self) -> None:
        self._refused(max_network_operations="0")

    def test_the_refusal_names_the_shortage(self) -> None:
        response = self._refused(max_network_operations="0")

        self.assertIn("Short by", response.message)

    def test_a_refusal_records_nothing(self) -> None:
        before = len(self._authorizations())

        self._refused(max_network_operations="0")

        self.assertEqual(len(self._authorizations()), before)

    def test_a_refusal_reaches_no_provider(self) -> None:
        self._refused(max_network_operations="0")

        self.assertEqual(self.operation.calls, [])

    def test_a_refusal_starts_no_execution(self) -> None:
        self._refused(max_network_operations="0")

        self.assertIsNone(self.execution_service.live_execution("plan-1"))


class MalformedInputRefusesRatherThanFallsBackTests(CuriosityBudgetFixture):
    def _refused(self, **budget: str):
        response = self._authorize(**budget)
        self.assertIsNone(response.research_plan_authorization)
        self.assertEqual(self.operation.calls, [])
        return response

    def test_unreadable_text_refuses(self) -> None:
        response = self._refused(max_network_operations="plenty")

        self.assertIn("whole number", response.message)

    def test_unreadable_text_does_not_grant_the_default(self) -> None:
        before = len(self._authorizations())

        self._refused(max_network_operations="plenty")

        self.assertEqual(len(self._authorizations()), before)

    def test_a_negative_grant_refuses(self) -> None:
        self._refused(max_network_operations="-1")

    def test_a_fractional_count_refuses(self) -> None:
        self._refused(max_step_advances="2.5")

    def test_an_unlimited_time_grant_refuses(self) -> None:
        self._refused(max_seconds="inf")

    def test_above_the_network_ceiling_refuses(self) -> None:
        self._refused(max_network_operations=str(MAX_AUTONOMY_NETWORK_OPERATIONS + 1))

    def test_above_the_advance_ceiling_refuses(self) -> None:
        self._refused(max_step_advances=str(MAX_AUTONOMY_STEP_ADVANCES + 1))

    def test_above_the_time_ceiling_refuses(self) -> None:
        self._refused(max_seconds=str(MAX_AUTONOMY_SECONDS + 1))

    def test_a_malformed_preview_refuses_without_a_proposal(self) -> None:
        response = self._prepare(max_network_operations="plenty")

        self.assertIsNone(response.curiosity_proposal)
        self.assertEqual(self.operation.calls, [])


class ThePreviewShowsWhatIsNeededBesideWhatIsGrantedTests(CuriosityBudgetFixture):
    def test_the_preview_reports_the_requirement(self) -> None:
        message = self._prepare().message

        self.assertIn(f"Network operations required: {REQUIRED_NETWORK}", message)
        self.assertIn(f"Steps requiring an advance: {REQUIRED_ADVANCES}", message)

    def test_the_preview_reports_what_would_be_granted(self) -> None:
        message = self._prepare(max_network_operations="2").message

        self.assertIn("approved: 2", message)

    def test_the_preview_reports_an_insufficient_grant(self) -> None:
        message = self._prepare(max_network_operations="0").message

        self.assertIn("INSUFFICIENT", message)
        self.assertIn("Short by 1 network operations", message)

    def test_the_preview_never_calls_the_requirement_a_permission(self) -> None:
        message = self._prepare().message.casefold()

        self.assertIn("not a promise the plan will finish", message)

    def test_the_preview_performs_nothing(self) -> None:
        self._prepare(max_network_operations="2")

        self.assertEqual(self.operation.calls, [])
        self.assertEqual(len(self._authorizations()), 0)

    def test_seconds_are_shown_as_granted_and_never_as_required(self) -> None:
        """No duration is derivable, so none is claimed."""
        message = self._prepare(max_seconds="120").message

        self.assertNotIn("Seconds required", message)
        self.assertNotIn("seconds required", message)


class NothingAboutThePlanChangesTests(CuriosityBudgetFixture):
    def test_the_digest_is_the_same_whatever_is_granted(self) -> None:
        plain = self._prepare().curiosity_proposal.digest

        generous = self._prepare(max_network_operations="9").curiosity_proposal.digest

        self.assertEqual(plain, generous)

    def test_the_approval_binds_the_exact_previewed_digest(self) -> None:
        digest = self._prepare().curiosity_proposal.digest

        response = self._authorize(max_network_operations="2")

        self.assertEqual(response.research_plan_authorization.plan_digest, digest)

    def test_capabilities_stay_exactly_those_the_plan_authors(self) -> None:
        response = self._authorize(max_network_operations="2")

        self.assertEqual(
            response.research_plan_authorization.capabilities,
            frozenset(
                {
                    ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH,
                    ResearchPlanStepCapability.SOURCE_DISCOVERY,
                }
            ),
        )

    def test_model_budget_does_not_add_capabilities_or_run_research(self) -> None:
        response = self._authorize(max_llm_operations="5")

        self.assertEqual(
            response.research_plan_authorization.budget.max_llm_operations,
            5,
        )
        self.assertEqual(
            response.research_plan_authorization.capabilities,
            frozenset(
                {
                    ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH,
                    ResearchPlanStepCapability.SOURCE_DISCOVERY,
                }
            ),
        )
        self.assertEqual(self.operation.calls, [])

    def test_authorizing_runs_no_research(self) -> None:
        self._authorize(max_network_operations="2")

        self.assertEqual(self.operation.calls, [])

    def test_a_different_budget_is_a_different_approval_record(self) -> None:
        """Nothing edits a granted budget; choosing again grants again."""
        first = self._authorize().research_plan_authorization

        second = self._authorize(
            max_step_advances="9", max_network_operations="9"
        ).research_plan_authorization

        self.assertNotEqual(first.authorization_id, second.authorization_id)
        self.assertEqual(first.budget, DEFAULT)
        self.assertNotEqual(second.budget, DEFAULT)


class OneBudgetImplementationTests(unittest.TestCase):
    """No Curiosity-only copy of the rules exists to drift from the original."""

    def test_only_one_module_parses_operator_budget_input(self) -> None:
        parsers = sorted(
            path.name
            for path in (SRC_DIR).rglob("*.py")
            if "def budget_from(" in path.read_text(encoding="utf-8")
        )

        self.assertEqual(parsers, ["ResearchAuthorizationBudgetChoice.py"])

    def test_only_one_module_derives_the_plan_requirement(self) -> None:
        derivations = sorted(
            path.name
            for path in (SRC_DIR).rglob("*.py")
            if "def required_cost(" in path.read_text(encoding="utf-8")
        )

        self.assertEqual(derivations, ["ResearchPlanBudgetRequirement.py"])

    def test_the_curiosity_service_reuses_the_shared_parser(self) -> None:
        source = (SRC_DIR / "cognition" / "CuriosityApplicationService.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("from research.ResearchAuthorizationBudgetChoice import", source)
        self.assertNotIn("def budget_from(", source)


if __name__ == "__main__":
    unittest.main()
