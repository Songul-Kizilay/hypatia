"""Exact target identity enters approval without changing reference plans."""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError, dataclass, replace
from datetime import UTC, datetime

from core.Exceptions import ResearchError
from research.BackgroundResearchTask import BackgroundResearchTask
from research.DeferredExecutionEligibility import deferred_execution_decision
from research.DeferredExecutionGrant import DeferredExecutionGrant
from research.DeferredGrantAuthorizer import DeferredGrantAuthorizer
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchExecutionAllowance import ResearchExecutionAllowance
from research.ResearchPlan import ResearchPlan
from research.ResearchPlanAuthorization import capabilities_of, restrictions_of
from research.ResearchPlanConstraint import ResearchPlanConstraint
from research.ResearchPlanDigest import canonical_plan_bytes, plan_digest
from research.ResearchPlanExecutionCodec import (
    decode_execution_snapshot,
    encode_execution_snapshot,
)
from research.ResearchPlanExecutionSnapshot import ResearchPlanExecutionSnapshot
from research.ResearchPlanExecutionState import ResearchPlanExecutionState
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchPlanStepStatus import ResearchPlanStepStatus
from research.ResearchPlanTargetBinding import ResearchPlanTargetBinding
from research.ResearchTargetScope import ResearchTargetScope, TargetHostRule
from research.SemanticEvidenceStepBinding import SemanticEvidenceStepBinding

MOMENT = datetime(2026, 9, 3, tzinfo=UTC)
SCOPE_REVISION_DIGEST = "a" * 64


def reference_plan() -> ResearchPlan:
    return ResearchPlan(
        plan_id="legacy-plan",
        question="Read the selected source",
        steps=(
            ResearchPlanStep(
                "step-1",
                "Read the selected source",
                capability=ResearchPlanStepCapability.SOURCE_FETCH,
                authorized_source_url="https://example.test/",
            ),
        ),
        created_at=MOMENT,
    )


def target_binding() -> ResearchPlanTargetBinding:
    return ResearchPlanTargetBinding(
        program_id="program-1",
        scope=ResearchTargetScope(
            allowed_hosts=(
                TargetHostRule("example.test"),
                TargetHostRule("example.test", True),
            ),
            excluded_hosts=(TargetHostRule("pay.example.test"),),
            allowed_networks=("93.184.216.0/24",),
            excluded_networks=("93.184.216.35/32",),
        ),
        scope_revision_id="scope-revision-1",
        scope_revision_digest=SCOPE_REVISION_DIGEST,
    )


class PlanTargetBindingTests(unittest.TestCase):
    def test_binding_normalizes_program_and_is_immutable(self) -> None:
        binding = replace(target_binding(), program_id="  program-1  ")
        self.assertEqual(binding, target_binding())
        with self.assertRaises(FrozenInstanceError):
            binding.program_id = "other"  # type: ignore[misc]

    def test_binding_rejects_unbounded_or_untyped_values(self) -> None:
        for program_id in ("", " ", "p" * 201, None, 42):
            with self.subTest(program_id=program_id), self.assertRaises(ResearchError):
                ResearchPlanTargetBinding(program_id, target_binding().scope)  # type: ignore[arg-type]
        for scope in (None, {}, "example.test"):
            with self.subTest(scope=scope), self.assertRaises(ResearchError):
                ResearchPlanTargetBinding("program-1", scope)  # type: ignore[arg-type]
        for values in (
            {"scope_revision_id": "scope-1"},
            {"scope_revision_digest": SCOPE_REVISION_DIGEST},
            {"scope_revision_id": "", "scope_revision_digest": SCOPE_REVISION_DIGEST},
            {"scope_revision_id": "scope-1", "scope_revision_digest": "A" * 64},
            {"scope_revision_id": "scope-1", "scope_revision_digest": "g" * 64},
            {"scope_revision_id": "scope-1", "scope_revision_digest": "a" * 63},
        ):
            with self.subTest(values=values), self.assertRaises(ResearchError):
                ResearchPlanTargetBinding(
                    "program-1",
                    target_binding().scope,
                    **values,
                )
        self.assertEqual(
            len(replace(target_binding(), program_id="p" * 200).program_id), 200
        )

    def test_plan_requires_typed_binding(self) -> None:
        with self.assertRaises(ResearchError):
            replace(reference_plan(), target_binding={})  # type: ignore[arg-type]

    def test_only_bounded_target_acquisition_capabilities_are_accepted(self) -> None:
        for capability in ResearchPlanStepCapability:
            if capability is ResearchPlanStepCapability.SEMANTIC_EVIDENCE_PROPOSAL:
                step = ResearchPlanStep(
                    "step-1",
                    "Propose",
                    capability=capability,
                    semantic_evidence_binding=SemanticEvidenceStepBinding(
                        "a" * 64, "http://127.0.0.1/model", "test"
                    ),
                )
            else:
                step = replace(reference_plan().steps[0], capability=capability)
            with self.subTest(capability=capability):
                if capability in {
                    ResearchPlanStepCapability.SOURCE_FETCH,
                    ResearchPlanStepCapability.SOURCE_ACCEPT,
                }:
                    plan = replace(
                        reference_plan(), steps=(step,), target_binding=target_binding()
                    )
                    self.assertEqual(plan.steps[0].capability, capability)
                else:
                    with self.assertRaisesRegex(ResearchError, "only source"):
                        replace(
                            reference_plan(),
                            steps=(step,),
                            target_binding=target_binding(),
                        )
                # The existing reference-plan vocabulary remains unchanged.
                self.assertIsNone(
                    replace(reference_plan(), steps=(step,)).target_binding
                )

    def test_legacy_v2_and_v4_bytes_keep_their_pinned_prechange_identity(self) -> None:
        # Captured from ed68fd3/v0.3.298 before adding target_binding.
        self.assertEqual(
            plan_digest(reference_plan()),
            "68d394c41b70d7aad43f2ade2267c584399fab49da61d12cbfcfc0026f639323",
        )
        constrained = replace(
            reference_plan(),
            constraints=(ResearchPlanConstraint("Keep the exact source"),),
        )
        self.assertEqual(
            plan_digest(constrained),
            "355475ac82394a96272126a22a501f082fc75ca30d2616b2a0e0d99a57e65353",
        )
        self.assertNotIn(b"target_binding", canonical_plan_bytes(reference_plan()))
        self.assertNotIn(b"target_binding", canonical_plan_bytes(constrained))

    def test_scoped_schema_covers_program_rules_and_constraints(self) -> None:
        binding = target_binding()
        plan = replace(reference_plan(), target_binding=binding)
        self.assertIn(b"hypatia:research-plan-digest:v6", canonical_plan_bytes(plan))
        scope = binding.scope
        variants = (
            replace(plan, target_binding=None),
            replace(plan, target_binding=replace(binding, program_id="program-2")),
            replace(
                plan,
                target_binding=replace(binding, scope_revision_id="scope-revision-2"),
            ),
            replace(
                plan,
                target_binding=replace(binding, scope_revision_digest="b" * 64),
            ),
            replace(plan, constraints=(ResearchPlanConstraint("Only this source"),)),
            replace(
                plan,
                steps=(
                    replace(plan.steps[0], authorized_source_url="https://other.test/"),
                ),
            ),
            *(
                replace(plan, target_binding=replace(binding, scope=changed))
                for changed in (
                    replace(scope, allowed_hosts=(TargetHostRule("other.test"),)),
                    replace(scope, excluded_hosts=()),
                    replace(scope, allowed_networks=()),
                    replace(scope, excluded_networks=()),
                    replace(scope, allowed_hosts=tuple(reversed(scope.allowed_hosts))),
                    replace(
                        scope,
                        excluded_hosts=(TargetHostRule("pay.example.test", True),),
                    ),
                )
            ),
        )
        for variant in variants:
            with self.subTest(variant=variant):
                self.assertNotEqual(plan_digest(plan), plan_digest(variant))
        self.assertEqual(
            plan_digest(plan), plan_digest(replace(plan, plan_id="another-preview"))
        )

    def test_future_binding_fields_enter_digest_automatically(self) -> None:
        @dataclass(frozen=True, slots=True)
        class FutureBinding(ResearchPlanTargetBinding):
            revision: str = "first"

        binding = FutureBinding(
            "program-1",
            target_binding().scope,
            scope_revision_id="scope-revision-1",
            scope_revision_digest=SCOPE_REVISION_DIGEST,
        )
        first = replace(reference_plan(), target_binding=binding)
        second = replace(first, target_binding=replace(binding, revision="second"))
        self.assertNotEqual(plan_digest(first), plan_digest(second))

    def test_deferred_grant_requires_exact_target_binding_and_active_grant(
        self,
    ) -> None:
        binding = target_binding()
        plan = replace(reference_plan(), target_binding=binding)
        state = ResearchPlanExecutionState.prepare(plan).start()
        budget = ResearchAutonomyBudget()
        allowance = ResearchExecutionAllowance(budget)
        task = BackgroundResearchTask(
            task_id="target-task",
            execution_id=plan.plan_id,
            budget=budget,
            created_at=MOMENT,
            updated_at=MOMENT,
        )
        grant = DeferredExecutionGrant(
            grant_id="target-grant",
            task_id=task.task_id,
            execution_id=task.execution_id,
            plan_digest=plan_digest(plan),
            capabilities=capabilities_of(plan),
            approved_restrictions=restrictions_of(plan),
            task_budget=task.budget,
            granted_at=MOMENT,
            granted_by=DeferredGrantAuthorizer.TRUSTED_LOCAL_OPERATOR,
        )
        exact = deferred_execution_decision(task, state, plan, allowance, grant)
        self.assertTrue(exact.allowed)
        self.assertEqual(exact.reason, "deferred_eligible")
        for changed in (
            replace(plan, target_binding=None),
            replace(plan, target_binding=replace(binding, program_id="program-2")),
            replace(
                plan,
                target_binding=replace(
                    binding, scope=replace(binding.scope, excluded_hosts=())
                ),
            ),
        ):
            with self.subTest(binding=changed.target_binding):
                refused = deferred_execution_decision(
                    task, state, changed, allowance, grant
                )
                self.assertFalse(refused.allowed)
                self.assertEqual(refused.reason, "plan_digest_mismatch")
        revoked = grant.revoked(MOMENT, DeferredGrantAuthorizer.TRUSTED_LOCAL_OPERATOR)
        refused = deferred_execution_decision(task, state, plan, allowance, revoked)
        self.assertFalse(refused.allowed)
        self.assertEqual(refused.reason, "manual_only")


class TargetExecutionIdentityTests(unittest.TestCase):
    def snapshot(self) -> ResearchPlanExecutionSnapshot:
        plan = replace(reference_plan(), target_binding=target_binding())
        state = ResearchPlanExecutionState.prepare(plan).start().start_step("step-1")
        return ResearchPlanExecutionSnapshot.capture(
            state,
            plan.question,
            plan.steps,
            MOMENT,
            research_run_id="run-1",
            target_plan_digest=plan_digest(plan),
        )

    def test_capture_codec_and_interrupted_restore_preserve_exact_identity(
        self,
    ) -> None:
        snapshot = self.snapshot()
        document = encode_execution_snapshot(snapshot)
        self.assertEqual(document["target_plan_digest"], snapshot.target_plan_digest)
        loaded = decode_execution_snapshot(document)
        self.assertEqual(loaded, snapshot)
        restored = loaded.restored()
        self.assertEqual(restored.target_plan_digest, snapshot.target_plan_digest)
        self.assertEqual(restored.research_run_id, "run-1")
        self.assertIs(restored.steps[0].status, ResearchPlanStepStatus.INTERRUPTED)

    def test_absent_digest_preserves_both_legacy_document_shapes(self) -> None:
        snapshot = replace(self.snapshot(), target_plan_digest=None)
        document = encode_execution_snapshot(snapshot)
        self.assertNotIn("target_plan_digest", document)
        self.assertEqual(decode_execution_snapshot(document), snapshot)
        del document["allowance"]
        self.assertEqual(decode_execution_snapshot(document), snapshot)

    def test_present_digest_requires_lowercase_hex_and_never_null(self) -> None:
        for value in (None, "", "a" * 63, "a" * 65, "A" * 64, "g" * 64, 42, True, []):
            document = encode_execution_snapshot(self.snapshot())
            document["target_plan_digest"] = value
            with self.subTest(value=value), self.assertRaises(ResearchError):
                decode_execution_snapshot(document)
            if value is not None:
                with self.assertRaises(ResearchError):
                    replace(self.snapshot(), target_plan_digest=value)  # type: ignore[arg-type]

    def test_target_identity_cannot_be_mixed_with_partial_or_unknown_shape(
        self,
    ) -> None:
        document = encode_execution_snapshot(self.snapshot())
        del document["allowance"]
        with self.assertRaises(ResearchError):
            decode_execution_snapshot(document)
        document = encode_execution_snapshot(self.snapshot())
        document["program_id"] = "unbound-extra"
        with self.assertRaises(ResearchError):
            decode_execution_snapshot(document)


if __name__ == "__main__":
    unittest.main()
