"""An approval that can be read back without re-deriving it from a hash.

The plan digest already covers a plan's typed restrictions, so an approval was
never able to cover a restriction the operator had not chosen. What it could not
do was say so. Anyone auditing a stored approval saw capabilities, a budget and
a 64-character digest, and had to rebuild the exact plan to learn whether it had
been approved under "no external source access".

So the record now names what the plan already says. This is deliberately
redundant, and the redundancy is the same shape the file already had: the
verifier has always cross-checked `capabilities`, which are equally digest-bound,
and refused when they disagreed. This adds one more derived field checked the
same way.

The important word is derived. It is built by `restrictions_of` from the exact
confirmed plan, never from a caller-supplied argument, and never from constraint
wording. Advisory text contributes nothing, in either direction.

It is also not authority. The verifier only ever turns a mismatch into a
refusal, so deleting the snapshot could not widen anything, and disagreeing with
the plan fails closed rather than being reconciled.

Deterministic. No network, no model, no writes.
"""

from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from core.Exceptions import ResearchError
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchPlan import ResearchPlan
from research.ResearchPlanAuthorization import (
    ResearchPlanAuthorization,
    capabilities_of,
    restrictions_of,
)
from research.ResearchPlanAuthorizationVerdict import (
    ResearchPlanAuthorizationVerdict,
)
from research.ResearchPlanAuthorizationVerifier import verify_plan_authorization
from research.ResearchPlanConstraint import ResearchPlanConstraint
from research.ResearchPlanDigest import plan_digest
from research.ResearchPlanRestriction import ResearchPlanRestriction
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepCapability import ResearchPlanStepCapability

NO_EXTERNAL = ResearchPlanRestriction.NO_EXTERNAL_SOURCE_ACCESS
MOMENT = datetime(2026, 9, 2, tzinfo=UTC)
RUN_ID = "run-1"


def build_plan(
    capability: ResearchPlanStepCapability = (
        ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH
    ),
    *,
    restriction: ResearchPlanRestriction | None = None,
    text: str = "Do not access external sources yet.",
    constrained: bool = True,
) -> ResearchPlan:
    """One plan with an exact capability and an exact constraint state."""
    return ResearchPlan(
        plan_id="plan-1",
        question="How should modern web applications defend against SSRF?",
        steps=(
            ResearchPlanStep(
                step_id="step-1",
                instruction="Search accepted local knowledge.",
                capability=capability,
            ),
        ),
        created_at=MOMENT,
        constraints=(
            (ResearchPlanConstraint(text=text, restriction=restriction),)
            if constrained
            else ()
        ),
    )


def authorize(plan: ResearchPlan) -> ResearchPlanAuthorization:
    """Approve exactly this plan through the only constructor callers use."""
    return ResearchPlanAuthorization.for_plan(
        authorization_id="approval-1",
        plan=plan,
        research_run_id=RUN_ID,
        budget=ResearchAutonomyBudget(),
        authorized_at=MOMENT,
        expires_at=MOMENT + timedelta(minutes=10),
    )


class TheSnapshotIsDerivedFromThePlanTests(unittest.TestCase):
    def test_an_unrestricted_plan_records_no_restriction(self) -> None:
        """Case A: nothing typed, nothing claimed."""
        authorization = authorize(build_plan(constrained=False))

        self.assertEqual(authorization.approved_restrictions, frozenset())

    def test_a_restricted_plan_records_exactly_that_restriction(self) -> None:
        """Case B: the one the operator chose, and only that one."""
        authorization = authorize(build_plan(restriction=NO_EXTERNAL))

        self.assertEqual(authorization.approved_restrictions, frozenset({NO_EXTERNAL}))

    def test_advisory_text_alone_records_no_restriction(self) -> None:
        """The v0.3.285 promise, still kept at the approval boundary."""
        authorization = authorize(
            build_plan(text="Do not access external sources.", restriction=None)
        )

        self.assertEqual(authorization.approved_restrictions, frozenset())

    def test_permissive_text_with_a_typed_restriction_still_records_it(self) -> None:
        authorization = authorize(
            build_plan(text="External sources are fine.", restriction=NO_EXTERNAL)
        )

        self.assertEqual(authorization.approved_restrictions, frozenset({NO_EXTERNAL}))

    def test_the_snapshot_equals_the_plans_own_restrictions(self) -> None:
        for restriction in (None, NO_EXTERNAL):
            with self.subTest(name=str(restriction)):
                plan = build_plan(restriction=restriction)

                self.assertEqual(
                    authorize(plan).approved_restrictions, restrictions_of(plan)
                )

    def test_the_factory_takes_no_restriction_argument(self) -> None:
        """It cannot be typed wider than the plan, because it is not passed in."""
        import inspect

        parameters = inspect.signature(ResearchPlanAuthorization.for_plan).parameters

        self.assertNotIn("approved_restrictions", parameters)
        self.assertNotIn("restrictions", parameters)

    def test_restrictions_of_refuses_anything_that_is_not_a_plan(self) -> None:
        with self.assertRaises(ResearchError):
            restrictions_of("plan-1")  # type: ignore[arg-type]


class AMismatchFailsClosedTests(unittest.TestCase):
    """Neither direction is reconciled, and neither widens anything."""

    def _verdict(self, plan: ResearchPlan, authorization) -> object:
        return verify_plan_authorization(authorization, plan, RUN_ID, MOMENT)

    def test_a_matching_pair_verifies(self) -> None:
        plan = build_plan(restriction=NO_EXTERNAL)

        self.assertIs(
            self._verdict(plan, authorize(plan)),
            ResearchPlanAuthorizationVerdict.VALID,
        )

    def test_a_snapshot_that_dropped_the_restriction_is_refused(self) -> None:
        """Approved restricted, stored as unrestricted: the dangerous direction."""
        plan = build_plan(restriction=NO_EXTERNAL)
        tampered = replace(authorize(plan), approved_restrictions=frozenset())

        self.assertIs(
            self._verdict(plan, tampered),
            ResearchPlanAuthorizationVerdict.RESTRICTION_MISMATCH,
        )

    def test_a_snapshot_that_invented_a_restriction_is_refused(self) -> None:
        """The other direction is refused too, rather than treated as harmless."""
        plan = build_plan(restriction=None)
        tampered = replace(
            authorize(plan), approved_restrictions=frozenset({NO_EXTERNAL})
        )

        self.assertIs(
            self._verdict(plan, tampered),
            ResearchPlanAuthorizationVerdict.RESTRICTION_MISMATCH,
        )

    def test_a_mismatch_does_not_authorize(self) -> None:
        plan = build_plan(restriction=NO_EXTERNAL)
        tampered = replace(authorize(plan), approved_restrictions=frozenset())

        self.assertFalse(self._verdict(plan, tampered).authorizes)

    def test_nothing_repairs_either_side(self) -> None:
        plan = build_plan(restriction=NO_EXTERNAL)
        tampered = replace(authorize(plan), approved_restrictions=frozenset())

        self._verdict(plan, tampered)

        self.assertEqual(restrictions_of(plan), frozenset({NO_EXTERNAL}))
        self.assertEqual(tampered.approved_restrictions, frozenset())

    def test_the_restriction_verdict_is_its_own_answer(self) -> None:
        """Not folded into the digest or capability verdicts."""
        self.assertIn(
            "restriction_mismatch",
            [verdict.value for verdict in ResearchPlanAuthorizationVerdict],
        )

    def test_only_valid_authorizes(self) -> None:
        authorizing = [
            verdict
            for verdict in ResearchPlanAuthorizationVerdict
            if verdict.authorizes
        ]

        self.assertEqual(authorizing, [ResearchPlanAuthorizationVerdict.VALID])


class TheSnapshotGrantsNothingTests(unittest.TestCase):
    def test_it_adds_no_capability(self) -> None:
        plan = build_plan(restriction=NO_EXTERNAL)

        self.assertEqual(authorize(plan).capabilities, capabilities_of(plan))

    def test_it_changes_no_budget(self) -> None:
        plan = build_plan(restriction=NO_EXTERNAL)
        budget = ResearchAutonomyBudget()

        self.assertEqual(authorize(plan).budget, budget)

    def test_it_does_not_change_the_plan_digest(self) -> None:
        """Audit evidence lives beside the plan, never inside its identity."""
        plan = build_plan(restriction=NO_EXTERNAL)
        before = plan_digest(plan)

        authorize(plan)

        self.assertEqual(plan_digest(plan), before)

    def test_the_digest_still_covers_the_restriction_itself(self) -> None:
        self.assertNotEqual(
            plan_digest(build_plan(restriction=None)),
            plan_digest(build_plan(restriction=NO_EXTERNAL)),
        )

    def test_an_empty_snapshot_never_widens_a_restricted_plan(self) -> None:
        """Deleting the evidence cannot make execution more permissive."""
        plan = build_plan(
            ResearchPlanStepCapability.SOURCE_DISCOVERY, restriction=NO_EXTERNAL
        )
        from research.ResearchPlanRestrictionConflict import (
            plan_restriction_conflicts,
        )

        stripped = replace(authorize(plan), approved_restrictions=frozenset())

        self.assertTrue(plan_restriction_conflicts(plan))
        self.assertFalse(
            verify_plan_authorization(stripped, plan, RUN_ID, MOMENT).authorizes
        )


class TheRecordValidatesItsOwnFieldTests(unittest.TestCase):
    def test_a_non_frozenset_snapshot_is_refused(self) -> None:
        plan = build_plan(restriction=NO_EXTERNAL)

        with self.assertRaises(ResearchError):
            replace(authorize(plan), approved_restrictions=[NO_EXTERNAL])

    def test_an_untyped_snapshot_entry_is_refused(self) -> None:
        plan = build_plan(restriction=NO_EXTERNAL)

        with self.assertRaises(ResearchError):
            replace(
                authorize(plan),
                approved_restrictions=frozenset({"no_external_source_access"}),
            )

    def test_the_default_is_empty_not_absent(self) -> None:
        authorization = ResearchPlanAuthorization(
            authorization_id="approval-1",
            plan_digest=plan_digest(build_plan()),
            research_run_id=RUN_ID,
            capabilities=frozenset({ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH}),
            budget=ResearchAutonomyBudget(),
            authorized_at=MOMENT,
            expires_at=MOMENT + timedelta(minutes=10),
        )

        self.assertEqual(authorization.approved_restrictions, frozenset())


class ExistingAuthorizationSemanticsAreUnchangedTests(unittest.TestCase):
    def test_the_validity_ceiling_is_unchanged(self) -> None:
        from research.ResearchAutonomyBudget import MAX_AUTONOMY_SECONDS
        from research.ResearchPlanAuthorization import (
            MAX_AUTHORIZATION_VALIDITY_SECONDS,
        )

        self.assertEqual(MAX_AUTHORIZATION_VALIDITY_SECONDS, MAX_AUTONOMY_SECONDS)

    def test_expiry_still_refuses(self) -> None:
        plan = build_plan(restriction=NO_EXTERNAL)
        authorization = authorize(plan)

        verdict = verify_plan_authorization(
            authorization, plan, RUN_ID, MOMENT + timedelta(hours=2)
        )

        self.assertIs(verdict, ResearchPlanAuthorizationVerdict.EXPIRED)

    def test_a_consumed_approval_is_still_spent(self) -> None:
        from research.ResearchPlanAuthorizationConsumption import (
            ResearchPlanAuthorizationConsumption,
        )

        plan = build_plan(restriction=NO_EXTERNAL)
        consumed = replace(
            authorize(plan),
            consumption=ResearchPlanAuthorizationConsumption(
                execution_id="plan-1", consumed_at=MOMENT
            ),
        )

        self.assertIs(
            verify_plan_authorization(consumed, plan, RUN_ID, MOMENT),
            ResearchPlanAuthorizationVerdict.ALREADY_CONSUMED,
        )

    def test_a_stale_plan_is_still_refused_by_digest(self) -> None:
        approved = authorize(build_plan(restriction=NO_EXTERNAL))
        edited = build_plan(
            restriction=NO_EXTERNAL, text="A different constraint entirely."
        )

        self.assertIs(
            verify_plan_authorization(approved, edited, RUN_ID, MOMENT),
            ResearchPlanAuthorizationVerdict.DIGEST_MISMATCH,
        )

    def test_human_provenance_is_unchanged(self) -> None:
        from research.ResearchAuthorizer import ResearchAuthorizer

        self.assertIs(authorize(build_plan()).authorized_by, ResearchAuthorizer.HUMAN)


class TheApprovalPathRecordsItEndToEndTests(unittest.TestCase):
    """Through the real service, store and renderer."""

    def setUp(self) -> None:
        from tempfile import TemporaryDirectory

        from brain.BrainRequest import BrainRequest
        from cognition.ResearchPlanAuthorizationApplicationService import (
            ResearchPlanAuthorizationApplicationService,
        )
        from research.JsonFileResearchPlanAuthorizationStore import (
            JsonFileResearchPlanAuthorizationStore,
        )
        from research.JsonFileResearchRunStore import JsonFileResearchRunStore
        from research.ResearchRunManager import ResearchRunManager
        from response.ResponseComposer import ResponseComposer

        self._request = BrainRequest
        self._directory = TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        root = Path(self._directory.name)
        self.store_path = root / "authorizations.json"
        self.store = JsonFileResearchPlanAuthorizationStore(self.store_path)
        runs = ResearchRunManager(JsonFileResearchRunStore(root / "runs.json"))
        runs.load()
        self.run = runs.create("How should applications defend against SSRF?")
        self.service = ResearchPlanAuthorizationApplicationService(
            runs, ResponseComposer(), authorization_store=self.store
        )

    def _metadata(self, capability: str, restriction, intent: str, **extra):
        return self._request(
            message="approve",
            metadata={
                "intent": intent,
                "research_run_id": self.run.run_id,
                "research_plan_question": (
                    "How should applications defend against SSRF?"
                ),
                "research_plan_steps": (("Search local knowledge.", (), capability),),
                "research_plan_constraints": ("Do not access external sources yet.",),
                "research_plan_restriction": restriction,
                **extra,
            },
        )

    def _approve(self, capability: str, restriction):
        previewed = self.service.process_preview(
            self._metadata(
                capability, restriction, "research_plan_authorization_preview"
            )
        )
        authorization = previewed.research_plan_authorization
        if authorization is None:
            return previewed, None
        confirmed = self.service.process_confirm(
            self._metadata(
                capability,
                restriction,
                "research_plan_authorization_confirm",
                authorization_id=authorization.authorization_id,
            )
        )
        return previewed, confirmed

    def test_case_a_an_unrestricted_approval_records_none(self) -> None:
        _previewed, confirmed = self._approve("local_knowledge_search", None)

        assert confirmed is not None
        [recorded] = self.service.authorizations()
        self.assertEqual(recorded.approved_restrictions, frozenset())

    def test_case_b_a_restricted_local_approval_records_the_restriction(
        self,
    ) -> None:
        _previewed, confirmed = self._approve("local_knowledge_search", NO_EXTERNAL)

        assert confirmed is not None
        [recorded] = self.service.authorizations()
        self.assertEqual(recorded.approved_restrictions, frozenset({NO_EXTERNAL}))

    def test_case_c_a_contradictory_plan_records_no_authorization_at_all(
        self,
    ) -> None:
        """So no misleading snapshot can exist for a plan nobody could run."""
        previewed, _confirmed = self._approve("source_discovery", NO_EXTERNAL)

        self.assertIn("contradicts itself", previewed.message)
        self.assertEqual(self.service.authorizations(), ())

    def test_the_recorded_restriction_survives_a_reload(self) -> None:
        self._approve("local_knowledge_search", NO_EXTERNAL)

        [reloaded] = self.store.load()

        self.assertEqual(reloaded.approved_restrictions, frozenset({NO_EXTERNAL}))

    def test_a_legacy_record_without_the_field_loads_as_unrestricted(self) -> None:
        """Truthful: nothing could record a restriction when it was written."""
        import json

        self._approve("local_knowledge_search", NO_EXTERNAL)
        document = json.loads(self.store_path.read_text(encoding="utf-8"))
        for entry in document["authorizations"]:
            entry.pop("approved_restrictions")
        document["schema_version"] = 2
        self.store_path.write_text(json.dumps(document), encoding="utf-8")

        [reloaded] = self.store.load()

        self.assertEqual(reloaded.approved_restrictions, frozenset())

    def test_the_approval_is_readable_without_the_digest(self) -> None:
        _previewed, confirmed = self._approve("local_knowledge_search", NO_EXTERNAL)

        assert confirmed is not None
        self.assertIn(
            "Approved restrictions: no_external_source_access", confirmed.message
        )

    def test_an_unrestricted_approval_says_none_rather_than_nothing(self) -> None:
        _previewed, confirmed = self._approve("local_knowledge_search", None)

        assert confirmed is not None
        self.assertIn("Approved restrictions: none", confirmed.message)

    def test_previewing_records_nothing(self) -> None:
        self.service.process_preview(
            self._metadata(
                "local_knowledge_search",
                NO_EXTERNAL,
                "research_plan_authorization_preview",
            )
        )

        self.assertEqual(self.service.authorizations(), ())
        self.assertFalse(self.store_path.exists())


if __name__ == "__main__":
    unittest.main()
