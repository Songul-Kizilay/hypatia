"""A restriction somebody chose, applied to capabilities somebody declared.

Constraint text has been advisory since v0.3.285. "Do not access external
sources" was bound into the plan's identity and shown at approval, and it
stopped nothing, because acting on it would mean deciding what an English
sentence means.

So enforcement never comes from the words. It comes from a typed value the
operator selects, and it is applied to the capabilities the steps already
declare. The same sentence, left advisory, still blocks nothing at all — that
pair of cases is the whole point and both are tested here.

What counts as external is not a judgement either. `ResearchCapabilityCost`
already declares which capabilities spend a network operation, and autonomy
enforces network budgets from it, so the restriction asks that table rather
than keeping a list of its own that could drift away from it.

The restriction can only refuse. It is not a way to make a plan smaller: a
contradictory plan comes back as authored, with no step dropped, no capability
lowered and no provider quietly swapped for a local one.

Deterministic. No network, no model, no writes.
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

from core.Exceptions import ResearchError
from research.ResearchCapabilityCost import cost_for
from research.ResearchDisclosure import ResearchDisclosure
from research.ResearchPlanConstraint import ResearchPlanConstraint
from research.ResearchPlanDigest import (
    CANONICAL_SCHEMA,
    canonical_plan_bytes,
    plan_digest,
)
from research.ResearchPlanRestriction import ResearchPlanRestriction
from research.ResearchPlanRestrictionConflict import plan_restriction_conflicts
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.SemanticComparisonRequest import SemanticComparisonRequest
from research.SemanticComparisonStepBinding import SemanticComparisonStepBinding
from research.SemanticEvidenceStepBinding import SemanticEvidenceStepBinding
from tests.research.test_plan_constraints import (
    LEGACY_BYTES,
    LEGACY_DIGEST,
    MOMENT,
    SSRF_CONSTRAINT,
    SSRF_QUESTION,
    plan,
)
from tests.research.test_semantic_comparison_proposal import evidence

NO_EXTERNAL = ResearchPlanRestriction.NO_EXTERNAL_SOURCE_ACCESS

#: The capabilities that actually reach the network, taken from the declared
#: cost table rather than written out by hand here.
NETWORK_CAPABILITIES = tuple(
    capability
    for capability in ResearchPlanStepCapability
    if cost_for(capability).network_operations > 0
)
LOCAL_CAPABILITIES = tuple(
    capability
    for capability in ResearchPlanStepCapability
    if cost_for(capability).network_operations == 0
)


def restricted_plan(
    capability: ResearchPlanStepCapability,
    *,
    restriction: ResearchPlanRestriction | None = NO_EXTERNAL,
    instruction: str = "Discover supporting literature through Crossref.",
):
    """One step with an exact declared capability, plus one constraint."""
    from research.ResearchPlan import ResearchPlan

    return ResearchPlan(
        plan_id="plan-1",
        question=SSRF_QUESTION,
        steps=(
            ResearchPlanStep(
                step_id="step-1",
                instruction=instruction,
                capability=capability,
                semantic_comparison_binding=(
                    SemanticComparisonStepBinding(
                        SemanticComparisonRequest(
                            "run-1",
                            SSRF_QUESTION,
                            (
                                evidence(0, "First excerpt"),
                                evidence(1, "Second excerpt"),
                            ),
                        ),
                        "http://127.0.0.1/model",
                        "test",
                        ResearchDisclosure.LOCAL_ONLY,
                    )
                    if capability
                    is ResearchPlanStepCapability.SEMANTIC_EVIDENCE_COMPARISON
                    else None
                ),
                semantic_evidence_binding=(
                    SemanticEvidenceStepBinding(
                        "a" * 64, "http://127.0.0.1/model", "test"
                    )
                    if capability
                    is ResearchPlanStepCapability.SEMANTIC_EVIDENCE_PROPOSAL
                    else None
                ),
            ),
        ),
        created_at=MOMENT,
        constraints=(
            ResearchPlanConstraint(text=SSRF_CONSTRAINT, restriction=restriction),
        ),
    )


class TheBlockedSetComesFromDeclaredCostTests(unittest.TestCase):
    """No provider names, no keywords: the network cost table decides."""

    def test_the_network_capabilities_include_the_explicit_model_step(self) -> None:
        self.assertEqual(
            set(NETWORK_CAPABILITIES),
            {
                ResearchPlanStepCapability.SOURCE_DISCOVERY,
                ResearchPlanStepCapability.SOURCE_FETCH,
                ResearchPlanStepCapability.SOURCE_ACCEPT,
                ResearchPlanStepCapability.SEMANTIC_EVIDENCE_PROPOSAL,
                ResearchPlanStepCapability.SEMANTIC_EVIDENCE_COMPARISON,
            },
        )

    def test_every_network_capability_is_forbidden(self) -> None:
        for capability in NETWORK_CAPABILITIES:
            with self.subTest(name=capability.value):
                self.assertTrue(NO_EXTERNAL.forbids(capability))

    def test_no_local_capability_is_forbidden(self) -> None:
        for capability in LOCAL_CAPABILITIES:
            with self.subTest(name=capability.value):
                self.assertFalse(NO_EXTERNAL.forbids(capability))

    def test_local_knowledge_search_is_allowed(self) -> None:
        self.assertFalse(
            NO_EXTERNAL.forbids(ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH)
        )

    def test_a_new_network_capability_would_be_forbidden_automatically(self) -> None:
        """The reason this reads the cost table instead of naming capabilities."""
        for capability in ResearchPlanStepCapability:
            with self.subTest(name=capability.value):
                self.assertEqual(
                    NO_EXTERNAL.forbids(capability),
                    cost_for(capability).network_operations > 0,
                )


class FreeTextEnforcesNothingTests(unittest.TestCase):
    """The v0.3.285 promise, kept."""

    def test_the_same_sentence_left_advisory_blocks_nothing(self) -> None:
        advisory = restricted_plan(
            ResearchPlanStepCapability.SOURCE_DISCOVERY, restriction=None
        )

        self.assertEqual(plan_restriction_conflicts(advisory), ())

    def test_the_same_sentence_typed_blocks_the_same_plan(self) -> None:
        enforced = restricted_plan(ResearchPlanStepCapability.SOURCE_DISCOVERY)

        self.assertTrue(plan_restriction_conflicts(enforced))

    def test_wording_that_sounds_permissive_still_enforces_when_typed(self) -> None:
        """Proof the text is not consulted in either direction."""
        permissive = restricted_plan(ResearchPlanStepCapability.SOURCE_DISCOVERY)
        rewritten = ResearchPlanConstraint(
            text="External sources are entirely fine.", restriction=NO_EXTERNAL
        )

        from dataclasses import replace

        self.assertTrue(
            plan_restriction_conflicts(replace(permissive, constraints=(rewritten,)))
        )

    def test_a_constraint_defaults_to_advisory(self) -> None:
        self.assertIsNone(ResearchPlanConstraint(text=SSRF_CONSTRAINT).restriction)

    def test_an_invalid_restriction_value_is_refused(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchPlanConstraint(
                text=SSRF_CONSTRAINT,
                restriction="no_external_source_access",  # type: ignore[arg-type]
            )


class TheConflictNamesExactlyWhatClashesTests(unittest.TestCase):
    def test_the_exact_step_is_reported(self) -> None:
        [conflict] = plan_restriction_conflicts(
            restricted_plan(ResearchPlanStepCapability.SOURCE_DISCOVERY)
        )

        self.assertEqual(conflict.step_id, "step-1")

    def test_the_exact_capability_is_reported(self) -> None:
        [conflict] = plan_restriction_conflicts(
            restricted_plan(ResearchPlanStepCapability.SOURCE_FETCH)
        )

        self.assertIs(conflict.capability, ResearchPlanStepCapability.SOURCE_FETCH)

    def test_the_exact_restriction_is_reported(self) -> None:
        [conflict] = plan_restriction_conflicts(
            restricted_plan(ResearchPlanStepCapability.SOURCE_ACCEPT)
        )

        self.assertIs(conflict.restriction, NO_EXTERNAL)

    def test_the_summary_names_all_three(self) -> None:
        [conflict] = plan_restriction_conflicts(
            restricted_plan(ResearchPlanStepCapability.SOURCE_DISCOVERY)
        )
        summary = conflict.summary()

        self.assertIn("step-1", summary)
        self.assertIn("source_discovery", summary)
        self.assertIn("no_external_source_access", summary)

    def test_the_validator_changes_nothing(self) -> None:
        """Pure: the plan that goes in is the plan that comes back out."""
        contradictory = restricted_plan(ResearchPlanStepCapability.SOURCE_DISCOVERY)
        before = canonical_plan_bytes(contradictory)

        plan_restriction_conflicts(contradictory)

        self.assertEqual(canonical_plan_bytes(contradictory), before)
        self.assertEqual(len(contradictory.steps), 1)
        self.assertIs(
            contradictory.steps[0].capability,
            ResearchPlanStepCapability.SOURCE_DISCOVERY,
        )


class ALocalOnlyPlanIsAllowedTests(unittest.TestCase):
    """This must not become a switch that blocks all research."""

    def test_a_local_knowledge_plan_under_the_restriction_is_valid(self) -> None:
        local = restricted_plan(
            ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH,
            instruction="Search accepted local knowledge for SSRF defenses.",
        )

        self.assertEqual(plan_restriction_conflicts(local), ())

    def test_every_local_capability_is_allowed_under_the_restriction(self) -> None:
        for capability in LOCAL_CAPABILITIES:
            with self.subTest(name=capability.value):
                self.assertEqual(
                    plan_restriction_conflicts(restricted_plan(capability)), ()
                )

    def test_an_unrestricted_plan_never_conflicts(self) -> None:
        for capability in ResearchPlanStepCapability:
            with self.subTest(name=capability.value):
                self.assertEqual(
                    plan_restriction_conflicts(plan("Review.")),
                    (),
                )


class TheRestrictionEntersPlanIdentityTests(unittest.TestCase):
    def test_typing_a_restriction_changes_the_digest(self) -> None:
        advisory = restricted_plan(
            ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH, restriction=None
        )
        enforced = restricted_plan(ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH)

        self.assertNotEqual(plan_digest(advisory), plan_digest(enforced))

    def test_the_restriction_value_appears_in_the_bytes(self) -> None:
        enforced = restricted_plan(ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH)

        self.assertIn(b"no_external_source_access", canonical_plan_bytes(enforced))

    def test_a_step_only_plan_still_produces_the_historical_bytes(self) -> None:
        """The v2 compatibility invariant is untouched by any of this."""
        self.assertEqual(
            canonical_plan_bytes(plan("Evaluate redirect handling.")),
            LEGACY_BYTES,
        )

    def test_a_step_only_plan_still_produces_the_historical_digest(self) -> None:
        self.assertEqual(
            plan_digest(plan("Evaluate redirect handling.")),
            LEGACY_DIGEST,
        )

    def test_a_step_only_plan_still_declares_the_v2_schema(self) -> None:
        self.assertIn(CANONICAL_SCHEMA.encode(), canonical_plan_bytes(plan("Review.")))


class TheRestrictionGrantsNothingTests(unittest.TestCase):
    """It may only reduce. Effective authority stays <= declared authority."""

    def test_it_adds_no_capability_to_any_step(self) -> None:
        bare = plan("Review.")
        enforced = restricted_plan(
            ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH,
            instruction="Review.",
        )

        self.assertEqual(
            [step.capability for step in bare.steps],
            [step.capability for step in enforced.steps],
        )

    def test_it_changes_no_declared_cost(self) -> None:
        for capability in ResearchPlanStepCapability:
            with self.subTest(name=capability.value):
                before = cost_for(capability)

                NO_EXTERNAL.forbids(capability)

                self.assertEqual(cost_for(capability), before)

    def test_the_restriction_vocabulary_has_exactly_one_member(self) -> None:
        """One truthful rule, not a policy engine."""
        self.assertEqual(list(ResearchPlanRestriction), [NO_EXTERNAL])

    def test_nothing_maps_a_restriction_to_a_capability_grant(self) -> None:
        """Read the code, not the prose.

        The module docstring explains that this grants nothing and that the
        cost table keeps budgets and restrictions in agreement, so scanning the
        whole file finds those words inside the sentences ruling them out.
        """
        import ast

        source = (SRC_DIR / "research" / "ResearchPlanRestriction.py").read_text(
            encoding="utf-8"
        )
        module = ast.parse(source)
        for node in ast.walk(module):
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                node.value.value = ""
        code = ast.unparse(module).casefold()

        for forbidden in ("grant", "allow_capability", "add_capability", "budget"):
            with self.subTest(name=forbidden):
                self.assertNotIn(forbidden, code)


if __name__ == "__main__":
    unittest.main()
