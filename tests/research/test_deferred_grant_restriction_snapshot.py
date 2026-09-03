"""A grant that can say what it was granted under.

Deferred grants are the longer-lived authority here. An approval expires within
the hour and is spent at Start; a grant persists, survives restart, and exists
precisely so that something may run later without a person present. It named a
plan digest and nothing else, so auditing one meant rebuilding the exact plan to
learn whether it had been granted over a plan that forbids external sources.

It now records that, derived by the same `restrictions_of` the authorization
snapshot uses — one meaning of "this plan's restrictions", not two that could
drift apart.

The interesting part is the grants that already exist. Typed restrictions
arrived in v0.3.286 and grants have been persisted since well before that, so a
stored grant may perfectly well cover a restricted plan while its record says
nothing. Loading that as "approved no restrictions" would be inventing history
in the permissive direction, so `None` means unrecorded and is a different thing
from an empty set. Unrecorded is not eligible: the operator can look at the
grant and make it again if they still mean it.

Deterministic. No network, no model, no execution.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from core.Exceptions import ResearchError
from research.DeferredExecutionEligibility import deferred_execution_decision
from research.DeferredExecutionGrant import DeferredExecutionGrant
from research.JsonFileDeferredExecutionGrantStore import (
    JsonFileDeferredExecutionGrantStore,
)
from research.ResearchPlanAuthorization import capabilities_of, restrictions_of
from research.ResearchPlanDigest import plan_digest
from research.ResearchPlanRestriction import ResearchPlanRestriction
from tests.research.test_deferred_execution_grants import (
    NOW,
    Context,
    grant_for,
)

NO_EXTERNAL = ResearchPlanRestriction.NO_EXTERNAL_SOURCE_ACCESS


def restricted_context() -> Context:
    """The same fixture over a plan whose constraint is typed, not advisory."""
    from dataclasses import replace as _replace

    from research.ResearchPlanConstraint import ResearchPlanConstraint
    from research.ResearchPlanExecutionState import ResearchPlanExecutionState

    context = Context()
    context.plan = _replace(
        context.plan,
        constraints=(
            ResearchPlanConstraint(
                text="Do not access external sources.", restriction=NO_EXTERNAL
            ),
        ),
    )
    context.execution = ResearchPlanExecutionState.prepare(context.plan).start()
    return context


def schema_one_document(context: Context) -> dict:
    """Reproduce the exact grant document v0.3.287 and earlier wrote.

    Hand-written rather than serialized: the point of a legacy fixture is that
    the current writer cannot have produced it. Taking today's output and
    deleting a key proves only that the reader tolerates a missing key, which
    is a different and much weaker claim.

    The field set is schema 1 exactly - the ten keys the store wrote before
    `approved_restrictions` existed - and `schema_version` says 1 to match.
    The digest, capabilities and budget refer to the caller's plan and task so
    the record is genuinely about them; a legacy grant naming some other plan
    would be refused for a mismatch long before restrictions were considered,
    and would prove nothing about how an unrecorded snapshot is read.
    """
    budget = context.task.budget
    return {
        "schema_version": 1,
        "grants": [
            {
                "grant_id": "grant-1",
                "task_id": context.task.task_id,
                "execution_id": context.task.execution_id,
                "plan_digest": plan_digest(context.plan),
                "capabilities": sorted(
                    value.value for value in capabilities_of(context.plan)
                ),
                "task_budget": {
                    "max_step_advances": budget.max_step_advances,
                    "max_network_operations": budget.max_network_operations,
                    "max_llm_operations": budget.max_llm_operations,
                    "max_seconds": budget.max_seconds,
                },
                "granted_at": NOW.isoformat(),
                "granted_by": "trusted_local_operator",
                "revoked_at": None,
                "revoked_by": None,
            }
        ],
    }


def decide(context: Context, grant: DeferredExecutionGrant | None):
    """Ask the pure decision exactly as a future timer would."""
    return deferred_execution_decision(
        context.task,
        context.execution,
        context.plan,
        context.allowance,
        grant,
    )


class ANewGrantRecordsWhatThePlanSaysTests(unittest.TestCase):
    def test_case_a_an_unrestricted_plan_records_an_empty_set(self) -> None:
        context = Context()

        grant = grant_for(context)

        self.assertEqual(grant.approved_restrictions, frozenset())

    def test_case_a_an_unrestricted_grant_is_eligible(self) -> None:
        context = Context()

        self.assertTrue(decide(context, grant_for(context)).allowed)

    def test_the_snapshot_equals_the_plans_own_restrictions(self) -> None:
        context = Context()

        self.assertEqual(
            grant_for(context).approved_restrictions, restrictions_of(context.plan)
        )

    def test_an_empty_set_is_a_recorded_answer(self) -> None:
        """Distinct from a grant that never recorded one at all."""
        context = Context()

        self.assertTrue(grant_for(context).records_restrictions)


class AMismatchIsRefusedInBothDirectionsTests(unittest.TestCase):
    def test_case_c_a_dropped_restriction_is_ineligible(self) -> None:
        """Recorded as unrestricted while the plan restricts: the dangerous way.

        This needs a genuinely restricted plan. Reusing the unrestricted
        fixture would only re-test the opposite direction while looking like
        it covered this one.
        """
        context = restricted_context()
        tampered = replace(grant_for(context), approved_restrictions=frozenset())

        decision = decide(context, tampered)

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "restriction_mismatch")

    def test_case_b_a_restricted_plan_grants_and_is_eligible(self) -> None:
        context = restricted_context()

        granted = grant_for(context)

        self.assertEqual(granted.approved_restrictions, frozenset({NO_EXTERNAL}))
        self.assertTrue(decide(context, granted).allowed)

    def test_case_d_an_invented_restriction_is_ineligible(self) -> None:
        context = Context()
        tampered = replace(
            grant_for(context), approved_restrictions=frozenset({NO_EXTERNAL})
        )

        self.assertFalse(decide(context, tampered).allowed)

    def test_a_mismatch_names_its_own_reason(self) -> None:
        """Not folded into the digest or capability answer."""
        context = Context()
        tampered = replace(
            grant_for(context), approved_restrictions=frozenset({NO_EXTERNAL})
        )

        self.assertNotIn(
            decide(context, tampered).reason,
            ("plan_digest_mismatch", "capability_mismatch"),
        )

    def test_nothing_is_repaired_on_either_side(self) -> None:
        context = Context()
        tampered = replace(
            grant_for(context), approved_restrictions=frozenset({NO_EXTERNAL})
        )

        decide(context, tampered)

        self.assertEqual(restrictions_of(context.plan), frozenset())
        self.assertEqual(tampered.approved_restrictions, frozenset({NO_EXTERNAL}))


class AnUnrecordedGrantIsNotEligibleTests(unittest.TestCase):
    """The compatibility rule, and the reason for it."""

    def test_an_unrecorded_grant_is_refused(self) -> None:
        context = Context()
        legacy = replace(grant_for(context), approved_restrictions=None)

        decision = decide(context, legacy)

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "restrictions_unrecorded")

    def test_unrecorded_is_not_the_same_as_empty(self) -> None:
        context = Context()
        legacy = replace(grant_for(context), approved_restrictions=None)

        self.assertFalse(legacy.records_restrictions)
        self.assertTrue(grant_for(context).records_restrictions)

    def test_an_unrecorded_grant_is_refused_even_over_an_unrestricted_plan(
        self,
    ) -> None:
        """Being probably harmless is not the same as being known."""
        context = Context()
        legacy = replace(grant_for(context), approved_restrictions=None)

        self.assertEqual(restrictions_of(context.plan), frozenset())
        self.assertFalse(decide(context, legacy).allowed)

    def test_refusal_reaches_no_provider_and_spends_nothing(self) -> None:
        context = Context()
        before = context.allowance
        legacy = replace(grant_for(context), approved_restrictions=None)

        decide(context, legacy)

        self.assertEqual(context.allowance, before)


class TheSnapshotGrantsNothingTests(unittest.TestCase):
    """Driven through the real service, not the fixture helper.

    `grant_for` mirrors what the service records by convention, so asserting
    against it proves the helper is consistent with itself. A regression in
    TrustedDeferredExecutionControlService.grant would leave every one of
    these green. The grant under test is therefore the one the service mints.
    """

    def _granted(self, context: Context):
        from cognition.TrustedDeferredExecutionControlService import (
            TrustedDeferredExecutionControlService,
        )

        with tempfile.TemporaryDirectory() as directory:
            view = TrustedDeferredExecutionControlService(
                context,
                JsonFileDeferredExecutionGrantStore(Path(directory) / "grants.json"),
                clock=lambda: NOW,
                id_factory=lambda: "grant-1",
            ).grant("task-1")
        assert view.grant is not None
        return view.grant

    def test_it_adds_no_capability(self) -> None:
        context = Context()

        self.assertEqual(
            self._granted(context).capabilities, capabilities_of(context.plan)
        )

    def test_it_changes_no_task_budget(self) -> None:
        context = Context()

        self.assertEqual(self._granted(context).task_budget, context.task.budget)

    def test_it_does_not_change_the_plan_digest(self) -> None:
        context = Context()
        before = plan_digest(context.plan)

        self._granted(context)

        self.assertEqual(plan_digest(context.plan), before)

    def test_granting_a_restricted_plan_still_adds_no_capability(self) -> None:
        """The case where the snapshot is non-empty is the one worth checking."""
        context = restricted_context()

        granted = self._granted(context)

        self.assertEqual(granted.capabilities, capabilities_of(context.plan))
        self.assertEqual(granted.task_budget, context.task.budget)

    def test_removing_the_snapshot_cannot_widen_anything(self) -> None:
        """Deleting the evidence makes the grant less usable, never more."""
        context = Context()

        self.assertTrue(decide(context, grant_for(context)).allowed)
        self.assertFalse(
            decide(
                context, replace(grant_for(context), approved_restrictions=None)
            ).allowed
        )

    def test_a_revoked_grant_stays_refused(self) -> None:
        from research.DeferredGrantAuthorizer import DeferredGrantAuthorizer

        context = Context()
        revoked = grant_for(context).revoked(
            NOW, DeferredGrantAuthorizer.TRUSTED_LOCAL_OPERATOR
        )

        decision = decide(context, revoked)

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "manual_only")


class TheRecordValidatesItsOwnFieldTests(unittest.TestCase):
    def test_a_non_frozenset_snapshot_is_refused(self) -> None:
        context = Context()

        with self.assertRaises(ResearchError):
            replace(grant_for(context), approved_restrictions=[NO_EXTERNAL])

    def test_an_untyped_snapshot_entry_is_refused(self) -> None:
        context = Context()

        with self.assertRaises(ResearchError):
            replace(
                grant_for(context),
                approved_restrictions=frozenset({"no_external_source_access"}),
            )


class PersistenceTellsTheTruthTests(unittest.TestCase):
    def _store(self, directory: str) -> JsonFileDeferredExecutionGrantStore:
        return JsonFileDeferredExecutionGrantStore(Path(directory) / "grants.json")

    def test_a_new_grant_round_trips_its_snapshot(self) -> None:
        context = Context()
        granted = replace(
            grant_for(context), approved_restrictions=frozenset({NO_EXTERNAL})
        )
        with tempfile.TemporaryDirectory() as directory:
            store = self._store(directory)
            store.save([granted])

            [restored] = self._store(directory).load()

        self.assertEqual(restored.approved_restrictions, frozenset({NO_EXTERNAL}))

    def test_a_recorded_empty_set_round_trips_as_recorded(self) -> None:
        context = Context()
        with tempfile.TemporaryDirectory() as directory:
            store = self._store(directory)
            store.save([grant_for(context)])

            [restored] = self._store(directory).load()

        self.assertEqual(restored.approved_restrictions, frozenset())
        self.assertTrue(restored.records_restrictions)

    def test_a_genuine_schema_one_record_loads_as_unrecorded(self) -> None:
        """A document the current writer could not have produced."""
        context = Context()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "grants.json"
            path.write_text(json.dumps(schema_one_document(context)), encoding="utf-8")

            [restored] = JsonFileDeferredExecutionGrantStore(path).load()

        self.assertIsNone(restored.approved_restrictions)
        self.assertFalse(restored.records_restrictions)

    def test_the_legacy_fixture_really_lacks_the_field(self) -> None:
        """Otherwise the test above would pass for the wrong reason."""
        [entry] = schema_one_document(Context())["grants"]

        self.assertNotIn("approved_restrictions", entry)
        self.assertEqual(schema_one_document(Context())["schema_version"], 1)

    def test_a_restored_legacy_grant_is_not_eligible(self) -> None:
        """And refused for being unrecorded, not for some earlier mismatch."""
        context = Context()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "grants.json"
            path.write_text(json.dumps(schema_one_document(context)), encoding="utf-8")

            [restored] = JsonFileDeferredExecutionGrantStore(path).load()

        decision = decide(context, restored)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "restrictions_unrecorded")

    def test_an_unknown_future_schema_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "grants.json"
            path.write_text('{"schema_version": 3, "grants": []}', encoding="utf-8")

            with self.assertRaises(ResearchError):
                JsonFileDeferredExecutionGrantStore(path).load()

    def test_restart_preserves_every_other_binding(self) -> None:
        context = Context()
        granted = grant_for(context)
        with tempfile.TemporaryDirectory() as directory:
            store = self._store(directory)
            store.save([granted])

            [restored] = self._store(directory).load()

        self.assertEqual(restored, granted)


class TheOperatorIsToldTheDifferenceTests(unittest.TestCase):
    def _view(self, grant):
        from research.DeferredExecutionControlView import (
            DeferredExecutionControlView,
        )

        context = Context()
        return DeferredExecutionControlView(
            task_id=context.task.task_id,
            execution_id=context.task.execution_id,
            plan_digest=plan_digest(context.plan),
            task_budget=context.task.budget,
            grant=grant,
            decision=decide(context, grant),
        )

    def test_a_recorded_empty_set_reads_as_none(self) -> None:
        view = self._view(grant_for(Context()))

        self.assertEqual(view.approved_restrictions_text, "none")

    def test_an_unrecorded_grant_never_reads_as_none(self) -> None:
        """The whole point: silence must not be rendered as a finding."""
        legacy = replace(grant_for(Context()), approved_restrictions=None)

        view = self._view(legacy)

        self.assertEqual(
            view.approved_restrictions_text, "unavailable for legacy grant"
        )
        self.assertNotEqual(view.approved_restrictions_text, "none")

    def test_a_restricted_grant_names_its_restriction(self) -> None:
        restricted = replace(
            grant_for(Context()), approved_restrictions=frozenset({NO_EXTERNAL})
        )

        view = self._view(restricted)

        self.assertEqual(view.approved_restrictions_text, "no_external_source_access")

    def test_no_grant_reads_as_no_grant(self) -> None:
        view = self._view(None)

        self.assertEqual(view.approved_restrictions_text, "no grant")

    def test_the_confirmation_text_states_it(self) -> None:
        view = self._view(grant_for(Context()))

        self.assertIn("Approved restrictions: none", view.confirmation_text())


class OneExtractionFunctionTests(unittest.TestCase):
    def test_grants_and_authorizations_share_it(self) -> None:
        """No forked per-consumer notion of a plan's restrictions."""
        grant_source = (
            SRC_DIR / "cognition" / "TrustedDeferredExecutionControlService.py"
        ).read_text(encoding="utf-8")
        eligibility_source = (
            SRC_DIR / "research" / "DeferredExecutionEligibility.py"
        ).read_text(encoding="utf-8")

        for source in (grant_source, eligibility_source):
            with self.subTest(name=len(source)):
                self.assertIn("restrictions_of", source)
        for forbidden in ("grant_restrictions_of", "authorization_restrictions_of"):
            with self.subTest(name=forbidden):
                self.assertNotIn(forbidden, grant_source + eligibility_source)


class TheRealGrantPathDerivesItTests(unittest.TestCase):
    """Through the service, not the fixture helper.

    The helper mirrors what the service records by convention. Only driving the
    service proves the convention holds, and a derivation replaced by a
    constant or by a reading of the constraint text shows up nowhere else.
    """

    def _service(self, context: Context, directory: str):
        from cognition.TrustedDeferredExecutionControlService import (
            TrustedDeferredExecutionControlService,
        )

        return TrustedDeferredExecutionControlService(
            context,
            JsonFileDeferredExecutionGrantStore(Path(directory) / "grants.json"),
            clock=lambda: NOW,
            id_factory=lambda: "grant-1",
        )

    def _granted(self, context: Context):
        with tempfile.TemporaryDirectory() as directory:
            view = self._service(context, directory).grant("task-1")
        assert view.grant is not None
        return view

    def test_an_unrestricted_plan_is_granted_with_an_empty_set(self) -> None:
        view = self._granted(Context())

        assert view.grant is not None
        self.assertEqual(view.grant.approved_restrictions, frozenset())
        self.assertTrue(view.grant.records_restrictions)

    def test_a_restricted_plan_is_granted_with_its_exact_restriction(self) -> None:
        view = self._granted(restricted_context())

        assert view.grant is not None
        self.assertEqual(view.grant.approved_restrictions, frozenset({NO_EXTERNAL}))

    def test_the_granted_snapshot_equals_the_plans_restrictions(self) -> None:
        for context in (Context(), restricted_context()):
            with self.subTest(name=len(context.plan.constraints)):
                view = self._granted(context)

                assert view.grant is not None
                self.assertEqual(
                    view.grant.approved_restrictions, restrictions_of(context.plan)
                )

    def test_advisory_wording_alone_is_granted_with_no_restriction(self) -> None:
        """The same sentence, left advisory, records nothing."""
        from dataclasses import replace as _replace

        from research.ResearchPlanConstraint import ResearchPlanConstraint
        from research.ResearchPlanExecutionState import ResearchPlanExecutionState

        context = Context()
        context.plan = _replace(
            context.plan,
            constraints=(
                ResearchPlanConstraint(text="Do not access external sources."),
            ),
        )
        context.execution = ResearchPlanExecutionState.prepare(context.plan).start()

        view = self._granted(context)

        assert view.grant is not None
        self.assertEqual(view.grant.approved_restrictions, frozenset())

    def test_a_granted_restricted_plan_is_eligible(self) -> None:
        context = restricted_context()

        view = self._granted(context)

        self.assertTrue(view.decision.allowed)

    def test_the_service_takes_no_restriction_argument(self) -> None:
        import inspect

        from cognition.TrustedDeferredExecutionControlService import (
            TrustedDeferredExecutionControlService,
        )

        parameters = inspect.signature(
            TrustedDeferredExecutionControlService.grant
        ).parameters

        self.assertEqual(list(parameters), ["self", "task_id"])


class AnOmittedFieldClaimsNothingTests(unittest.TestCase):
    def test_the_model_default_is_unrecorded_not_empty(self) -> None:
        """Constructing a grant without the field must not assert "none"."""
        context = Context()
        built = DeferredExecutionGrant(
            grant_id="grant-1",
            task_id=context.task.task_id,
            execution_id=context.task.execution_id,
            plan_digest=plan_digest(context.plan),
            capabilities=capabilities_of(context.plan),
            task_budget=context.task.budget,
            granted_at=NOW,
            granted_by=grant_for(context).granted_by,
        )

        self.assertIsNone(built.approved_restrictions)
        self.assertFalse(built.records_restrictions)
        self.assertFalse(decide(context, built).allowed)


def contradictory_context() -> Context:
    """A plan that forbids external sources and whose only step needs them."""
    from dataclasses import replace as _replace

    from research.ResearchPlanConstraint import ResearchPlanConstraint
    from research.ResearchPlanExecutionState import ResearchPlanExecutionState
    from research.ResearchPlanStep import ResearchPlanStep
    from research.ResearchPlanStepCapability import ResearchPlanStepCapability

    context = Context()
    context.plan = _replace(
        context.plan,
        steps=(
            ResearchPlanStep(
                step_id="step-1",
                instruction="Discover supporting literature through Crossref.",
                capability=ResearchPlanStepCapability.SOURCE_DISCOVERY,
            ),
        ),
        constraints=(
            ResearchPlanConstraint(
                text="Do not access external sources.", restriction=NO_EXTERNAL
            ),
        ),
    )
    context.execution = ResearchPlanExecutionState.prepare(context.plan).start()
    return context


class ASelfContradictoryPlanIsNeverDeferredEligibleTests(unittest.TestCase):
    """A matching snapshot is not the same as a coherent plan.

    Approval and execution start both refuse a plan whose steps declare a
    capability its own restriction forbids. Deferred grants are the one
    authority that runs with nobody present, and they were the one boundary
    that never asked. Worse, the snapshot matches perfectly in this case —
    grant and plan agree exactly that external sources are forbidden — so
    every consistency check passes while the only step performs source
    discovery.
    """

    def test_the_fixture_plan_really_does_contradict_itself(self) -> None:
        from research.ResearchPlanRestrictionConflict import (
            plan_restriction_conflicts,
        )

        self.assertTrue(plan_restriction_conflicts(contradictory_context().plan))

    def test_the_snapshot_still_matches_the_plan(self) -> None:
        """So the mismatch check cannot be what saves us here."""
        context = contradictory_context()

        self.assertEqual(
            grant_for(context).approved_restrictions, restrictions_of(context.plan)
        )

    def test_a_contradictory_plan_is_not_deferred_eligible(self) -> None:
        context = contradictory_context()

        decision = decide(context, grant_for(context))

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "plan_restriction_conflict")

    def test_no_grant_can_be_minted_over_a_contradictory_plan(self) -> None:
        """Case E, at the boundary that mints unattended authority."""
        from cognition.TrustedDeferredExecutionControlService import (
            TrustedDeferredExecutionControlService,
        )
        from core.Exceptions import ResearchError as _ResearchError

        context = contradictory_context()
        with tempfile.TemporaryDirectory() as directory:
            store = JsonFileDeferredExecutionGrantStore(Path(directory) / "grants.json")
            before = (context.execution, context.allowance)
            service = TrustedDeferredExecutionControlService(
                context,
                store,
                clock=lambda: NOW,
                id_factory=lambda: "grant-1",
            )

            with self.assertRaises(_ResearchError):
                service.grant("task-1")
            self.assertEqual(store.load(), [])
            self.assertEqual((context.execution, context.allowance), before)

    def test_an_ordinary_restricted_local_plan_is_still_eligible(self) -> None:
        """The refusal must be about the contradiction, not about restrictions."""
        context = restricted_context()

        self.assertTrue(decide(context, grant_for(context)).allowed)


if __name__ == "__main__":
    unittest.main()
