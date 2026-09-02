"""Some authored lines are conditions on a plan, not work inside it.

The case that prompted this was real. Someone wrote ten SSRF research steps and
then, as an eleventh line, "Do not execute research or access external sources
yet." The preview dutifully reported eleven steps, because the only place to put
an authored line was the ordered instruction list. A sentence forbidding
execution had become an executable step.

So constraints are now their own thing: approved plan content, bound into the
digest, and structurally incapable of becoming execution work. They carry no
capability, no source selection, and no step identity.

The hard part was not the model but the identity. The digest walks every
dataclass field, so simply adding one would have changed the digest of every
plan that has no constraints at all — silently invalidating approvals and
deferred grants made before this milestone. The bytes below are the real ones
v0.3.284 produced, captured before the change, and they are asserted verbatim.

The schema is therefore chosen by what a plan contains rather than by when it
was written, which is the only thing that could work here: a ResearchPlan is
built in exactly one place from a live draft and is never restored from disk,
so there is no older plan object to carry a version on. A plan with no
constraints encodes as it always did; the first constraint moves it to v3.

Deterministic throughout. No network, no model, no writes.
"""

from __future__ import annotations

import sys
import unittest
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from core.Exceptions import ResearchError
from research.ResearchPlan import ResearchPlan
from research.ResearchPlanConstraint import ResearchPlanConstraint
from research.ResearchPlanDigest import (
    CANONICAL_SCHEMA,
    CANONICAL_SCHEMA_WITH_CONSTRAINTS,
    canonical_plan_bytes,
    plan_digest,
)
from research.ResearchPlanDraftService import ResearchPlanDraftService
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepCapability import ResearchPlanStepCapability

MOMENT = datetime(2026, 1, 1, tzinfo=UTC)

#: Captured from v0.3.284 before constraints existed. This is the historical
#: artifact: not a dataclass rebuilt with an empty tuple, but the exact bytes
#: the previous release hashed. If a step-only plan ever stops producing these,
#: every approval and deferred grant made before this milestone stops matching.
LEGACY_BYTES = (
    b"p:608:s:31:hypatia:research-plan-digest:v2d:566:s:12:ResearchPlan"
    b"s:8:questions:55:How should modern web applications defend against SSRF?"
    b"s:5:stepst:462:d:456:s:16:ResearchPlanSteps:7:step_ids:6:step-1"
    b"s:11:instructions:27:Evaluate redirect handling."
    b"s:28:selected_source_document_idst:0:s:10:capability"
    b"e:58:s:26:ResearchPlanStepCapabilitys:22:local_knowledge_search"
    b"s:21:authorized_source_urls:0:s:18:discovery_providern:0:"
    b"s:22:evidence_authorizationn:0:s:24:assessment_authorizationn:0:"
    b"s:19:claim_authorizationn:0:s:27:contradiction_authorizationn:0:"
    b"s:24:comparison_authorizationn:0:s:24:completion_authorizationn:0:"
)
LEGACY_DIGEST = "15da4930ac93770aa7ddd768fa50c1a4192824f1c4a178059c08f023eaedae89"

SSRF_QUESTION = "How should modern web applications defend against SSRF?"
SSRF_STEPS = (
    "Identify the main SSRF trust-boundary failures.",
    "Evaluate defenses for URL parsing and canonicalization.",
    "Evaluate DNS resolution and IP-address validation defenses.",
    "Evaluate redirect handling.",
    "Evaluate protocol and scheme restrictions.",
    "Evaluate network egress controls and cloud metadata protections.",
    "Compare allowlist and denylist approaches.",
    "Identify common SSRF defense bypass classes.",
    "Separate documented facts from hypotheses and unknowns.",
    "State what evidence would be needed to evaluate each defense.",
)
SSRF_CONSTRAINT = "Do not execute research or access external sources yet."


def plan(
    *instructions: str,
    constraints: tuple[str, ...] = (),
    question: str = SSRF_QUESTION,
) -> ResearchPlan:
    """Build one plan directly, bypassing the draft service's identifiers."""
    return ResearchPlan(
        plan_id="plan-golden",
        question=question,
        steps=tuple(
            ResearchPlanStep(
                step_id=f"step-{index}",
                instruction=instruction,
                capability=ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH,
            )
            for index, instruction in enumerate(instructions, start=1)
        ),
        created_at=MOMENT,
        constraints=tuple(ResearchPlanConstraint(text=text) for text in constraints),
    )


class LegacyPlansKeepTheirIdentityTests(unittest.TestCase):
    """The compatibility invariant, asserted against real captured bytes."""

    def test_a_step_only_plan_still_produces_the_historical_bytes(self) -> None:
        self.assertEqual(
            canonical_plan_bytes(plan("Evaluate redirect handling.")),
            LEGACY_BYTES,
        )

    def test_a_step_only_plan_still_produces_the_historical_digest(self) -> None:
        self.assertEqual(
            plan_digest(plan("Evaluate redirect handling.")),
            LEGACY_DIGEST,
        )

    def test_the_empty_constraint_tuple_is_not_encoded_at_all(self) -> None:
        """Present-but-empty would still have changed every historical digest."""
        self.assertNotIn(b"constraints", canonical_plan_bytes(plan("Review.")))

    def test_a_step_only_plan_still_declares_the_v2_schema(self) -> None:
        self.assertIn(CANONICAL_SCHEMA.encode(), canonical_plan_bytes(plan("Review.")))

    def test_an_approval_made_before_constraints_still_verifies(self) -> None:
        """The practical consequence: old bindings still match the same plan."""
        remembered = LEGACY_DIGEST

        self.assertEqual(plan_digest(plan("Evaluate redirect handling.")), remembered)


class ConstraintsEnterThePlanIdentityTests(unittest.TestCase):
    def test_a_constrained_plan_declares_the_v3_schema(self) -> None:
        encoded = canonical_plan_bytes(plan("Review.", constraints=("Do not fetch.",)))

        self.assertIn(CANONICAL_SCHEMA_WITH_CONSTRAINTS.encode(), encoded)

    def test_adding_a_constraint_changes_the_digest(self) -> None:
        self.assertNotEqual(
            plan_digest(plan("Review.")),
            plan_digest(plan("Review.", constraints=("Do not fetch.",))),
        )

    def test_changing_constraint_text_changes_the_digest(self) -> None:
        self.assertNotEqual(
            plan_digest(plan("Review.", constraints=("Do not fetch.",))),
            plan_digest(plan("Review.", constraints=("You may fetch.",))),
        )

    def test_removing_the_last_constraint_returns_the_original_digest(self) -> None:
        self.assertEqual(
            plan_digest(plan("Review.")),
            plan_digest(plan("Review.", constraints=())),
        )

    def test_constraint_order_is_part_of_the_identity(self) -> None:
        self.assertNotEqual(
            plan_digest(plan("Review.", constraints=("First.", "Second."))),
            plan_digest(plan("Review.", constraints=("Second.", "First."))),
        )

    def test_the_constrained_text_actually_appears_in_the_bytes(self) -> None:
        encoded = canonical_plan_bytes(
            plan("Review.", constraints=("Do not access external sources yet.",))
        )

        self.assertIn(b"Do not access external sources yet.", encoded)

    def test_a_v2_and_a_v3_plan_can_never_collide(self) -> None:
        """Different schema strings, so no constraint set can imitate none."""
        self.assertNotEqual(CANONICAL_SCHEMA, CANONICAL_SCHEMA_WITH_CONSTRAINTS)


class ConstraintsAreNotStepsTests(unittest.TestCase):
    def test_a_constraint_is_not_a_plan_step(self) -> None:
        constrained = plan("Review.", constraints=("Do not fetch.",))

        self.assertNotIsInstance(constrained.constraints[0], ResearchPlanStep)

    def test_constraints_add_no_steps(self) -> None:
        constrained = plan("Review.", constraints=("A.", "B.", "C."))

        self.assertEqual(len(constrained.steps), 1)

    def test_a_constraint_carries_no_capability(self) -> None:
        constraint = ResearchPlanConstraint(text="Use NVD only.")

        for forbidden in ("capability", "selected_source_document_ids", "step_id"):
            with self.subTest(name=forbidden):
                self.assertFalse(hasattr(constraint, forbidden))

    def test_constraints_do_not_change_declared_capabilities(self) -> None:
        bare = plan("Review.")
        constrained = plan(
            "Review.", constraints=("Do not access external sources yet.",)
        )

        self.assertEqual(
            [step.capability for step in bare.steps],
            [step.capability for step in constrained.steps],
        )

    def test_constraints_select_no_sources(self) -> None:
        constrained = plan("Review.", constraints=("Use NVD only.",))

        self.assertEqual(constrained.selected_source_document_ids, ())

    def test_a_constraint_is_immutable(self) -> None:
        constraint = ResearchPlanConstraint(text="Do not fetch.")

        with self.assertRaises(FrozenInstanceError):
            constraint.text = "You may fetch."  # type: ignore[misc]


class ConstraintsAreBoundedTests(unittest.TestCase):
    def test_empty_constraint_text_is_refused(self) -> None:
        for blank in ("", "   "):
            with self.subTest(name=repr(blank)):
                with self.assertRaises(ResearchError):
                    ResearchPlanConstraint(text=blank)

    def test_overlong_constraint_text_is_refused(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchPlanConstraint(text="x" * 2_001)

    def test_too_many_constraints_are_refused(self) -> None:
        with self.assertRaises(ResearchError):
            plan("Review.", constraints=tuple(f"C{n}." for n in range(21)))

    def test_a_non_constraint_value_is_refused(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchPlan(
                plan_id="plan-1",
                question=SSRF_QUESTION,
                steps=plan("Review.").steps,
                created_at=MOMENT,
                constraints=("just a string",),  # type: ignore[arg-type]
            )

    def test_constraint_text_is_normalized_not_rejected(self) -> None:
        self.assertEqual(
            ResearchPlanConstraint(text="  Do not fetch.  ").text, "Do not fetch."
        )


class TheDraftServiceKeepsThemApartTests(unittest.TestCase):
    """The authoring path: two fields in, two concepts out."""

    def setUp(self) -> None:
        self.service = ResearchPlanDraftService(
            clock=lambda: MOMENT,
            id_factory=lambda: "plan-1",
        )

    def test_the_ssrf_case_previews_as_ten_steps_and_one_constraint(self) -> None:
        """The exact case that produced "Steps: 11"."""
        preview = self.service.preview(
            SSRF_QUESTION,
            tuple((instruction, ()) for instruction in SSRF_STEPS),
            (SSRF_CONSTRAINT,),
        )

        assert preview.plan is not None
        self.assertEqual(len(preview.plan.steps), 10)
        self.assertEqual(len(preview.plan.constraints), 1)

    def test_the_constraint_never_becomes_step_eleven(self) -> None:
        preview = self.service.preview(
            SSRF_QUESTION,
            tuple((instruction, ()) for instruction in SSRF_STEPS),
            (SSRF_CONSTRAINT,),
        )

        assert preview.plan is not None
        self.assertNotIn(
            SSRF_CONSTRAINT,
            [step.instruction for step in preview.plan.steps],
        )
        self.assertEqual(
            [step.step_id for step in preview.plan.steps][-1],
            "step-10",
        )

    def test_a_step_only_draft_still_works(self) -> None:
        preview = self.service.preview(SSRF_QUESTION, (("Review.", ()),))

        assert preview.plan is not None
        self.assertEqual(preview.plan.constraints, ())

    def test_blank_constraint_lines_are_refused_not_silently_kept(self) -> None:
        preview = self.service.preview(SSRF_QUESTION, (("Review.", ()),), ("   ",))

        self.assertFalse(preview.allowed)

    def test_exact_authored_order_is_preserved(self) -> None:
        preview = self.service.preview(
            SSRF_QUESTION,
            (("Review.", ()),),
            ("First.", "Second."),
        )

        assert preview.plan is not None
        self.assertEqual(
            [constraint.text for constraint in preview.plan.constraints],
            ["First.", "Second."],
        )


class SourcesStayAlignedToStepsTests(unittest.TestCase):
    """Constraints occupy no position in the step/source pairing."""

    def setUp(self) -> None:
        self.service = ResearchPlanDraftService(
            clock=lambda: MOMENT,
            id_factory=lambda: "plan-1",
        )

    def _preview(self, constraints: tuple[str, ...]):
        return self.service.preview(
            SSRF_QUESTION,
            (
                ("Review parsing.", ("document-1",)),
                ("Review DNS.", ("document-2",)),
                ("Review redirects.", ("document-3",)),
            ),
            constraints,
        )

    def test_sources_bind_to_the_same_steps_with_and_without_constraints(
        self,
    ) -> None:
        without = self._preview(())
        with_constraints = self._preview(("Do not fetch.", "Use NVD only."))

        assert without.plan is not None and with_constraints.plan is not None
        self.assertEqual(
            [step.selected_source_document_ids for step in without.plan.steps],
            [step.selected_source_document_ids for step in with_constraints.plan.steps],
        )

    def test_each_source_stays_on_its_own_step(self) -> None:
        preview = self._preview(("Do not fetch.",))

        assert preview.plan is not None
        self.assertEqual(
            [
                (step.step_id, step.selected_source_document_ids)
                for step in preview.plan.steps
            ],
            [
                ("step-1", ("document-1",)),
                ("step-2", ("document-2",)),
                ("step-3", ("document-3",)),
            ],
        )

    def test_constraints_consume_no_source_positions(self) -> None:
        preview = self._preview(("A.", "B.", "C.", "D."))

        assert preview.plan is not None
        self.assertEqual(len(preview.plan.selected_source_document_ids), 3)


if __name__ == "__main__":
    unittest.main()
