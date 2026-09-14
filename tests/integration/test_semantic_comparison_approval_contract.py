"""Canonical exact-pair approval, using real stored evidence; no model wiring."""

import json
import unittest
from dataclasses import replace
from datetime import timedelta
from unittest.mock import patch

from brain.BrainRequest import BrainRequest
from core.Exceptions import ResearchError
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchCapabilityCost import CAPABILITY_COSTS, cost_for
from research.ResearchDisclosure import ResearchDisclosure as Disclosure
from research.ResearchExecutionAllowance import ResearchExecutionAllowance
from research.ResearchOperationCost import ResearchOperationCost
from research.ResearchPlanAuthorizationVerifier import verify_plan_authorization
from research.ResearchPlanDigest import plan_digest
from research.ResearchPlanDraftService import ResearchPlanDraftService
from research.ResearchPlanStepCapability import ResearchPlanStepCapability as Cap
from research.ResearchPlanStepDraftInput import ResearchPlanStepDraftInput
from research.SemanticComparisonRequest import SemanticComparisonRequest
from research.SemanticComparisonStepBinding import SemanticComparisonStepBinding
from research.SemanticEvidenceStepBinding import SemanticEvidenceStepBinding
from tests.integration import test_research_mission_comparison as mission


class SemanticComparisonApprovalTests(unittest.TestCase):
    make_engine = mission.MissionComparisonTests.make_engine
    execution = mission.MissionComparisonTests.execution
    start = mission.MissionComparisonTests.start

    def setUp(self):
        mission.MissionComparisonTests.setUp(self)
        self.run = self.start().research_runs[0]
        self.authorizations = self.engine._plan_authorization_service
        self.binding = SemanticComparisonStepBinding(
            SemanticComparisonRequest(
                self.run.run_id, self.run.question, self.run.evidence
            ),
            "http://127.0.0.1:11434/v1/chat/completions",
            "test-model",
            Disclosure.LOCAL_ONLY,
        )
        self.steps = (
            ResearchPlanStepDraftInput(
                instruction="Compare the exact pair; contract only",
                capability=Cap.SEMANTIC_EVIDENCE_COMPARISON.value,
                semantic_comparison_binding=self.binding,
            ),
        )
        self.plan = (
            ResearchPlanDraftService().preview(self.run.question, self.steps).plan
        )
        self.budget = ResearchAutonomyBudget(
            max_step_advances=1, max_network_operations=1, max_llm_operations=1
        )

    def request(self, **changes):
        return BrainRequest(
            message="Approval",
            metadata={
                "research_run_id": self.run.run_id,
                "research_plan_question": self.run.question,
                "research_plan_steps": self.steps,
                "max_step_advances": "1",
                "max_network_operations": "1",
                "max_llm_operations": "1",
                "research_disclosure": "local_only",
                **changes,
            },
        )

    def grant(self, plan=None, disclosure=Disclosure.LOCAL_ONLY, budget=None):
        return self.authorizations.record_for_plan(
            plan or self.plan, self.run.run_id, disclosure, budget or self.budget
        )

    def test_exact_pair_preview_and_confirm_no_execution(self):
        previous = self.approval_store.load()
        snapshots = self.store.load()
        response = self.authorizations.process_preview(self.request())
        self.assertTrue(response.success)
        self.assertEqual(self.approval_store.load(), previous)
        for value in (
            self.binding.endpoint,
            self.binding.model,
            self.binding.request.content_fingerprint,
            "execution is not wired",
            *(e.excerpt for e in self.run.evidence),
            *(e.source_document_id for e in self.run.evidence),
        ):
            self.assertIn(value, response.message)
        approval = response.research_plan_authorization
        confirmed = self.authorizations.process_confirm(
            self.request(authorization_id=approval.authorization_id)
        )
        self.assertTrue(confirmed.success)
        self.assertEqual(len(self.approval_store.load()), len(previous) + 1)
        self.assertEqual(self.store.load(), snapshots)
        self.assertEqual(self.manager.get(self.run.run_id), self.run)
        self.assertEqual(self.fetcher.fetch.call_count, 2)
        self.assertEqual(
            approval.capabilities, frozenset({Cap.SEMANTIC_EVIDENCE_COMPARISON})
        )

    def test_missing_destination_disclosure_pair_and_cost_rejected(self):
        for changes in (
            {"endpoint": ""},
            {"model": ""},
            {"request": None},
            {"disclosure": Disclosure.NONE},
            {"disclosure": None},
            {"endpoint": "https://model.example/v1/chat/completions"},
            {"declared_cost": ResearchOperationCost()},
            {"declared_cost": ResearchOperationCost(2, 1)},
        ):
            with self.subTest(changes=changes), self.assertRaises(ResearchError):
                replace(self.binding, **changes)
        for disclosure in (Disclosure.NONE, Disclosure.REMOTE_PERMITTED):
            with self.assertRaises(ResearchError):
                self.grant(disclosure=disclosure)
        response = self.authorizations.process_preview(
            self.request(research_disclosure=None)
        )
        self.assertFalse(response.success)

    def test_explicit_remote_destination_requires_matching_disclosure(self):
        binding = replace(
            self.binding,
            endpoint="https://model.example/v1/chat/completions",
            disclosure=Disclosure.REMOTE_PERMITTED,
        )
        plan = replace(
            self.plan,
            steps=(replace(self.plan.steps[0], semantic_comparison_binding=binding),),
        )
        approval = self.grant(plan, Disclosure.REMOTE_PERMITTED)
        self.assertEqual(approval.disclosure, Disclosure.REMOTE_PERMITTED)
        with self.assertRaises(ResearchError):
            self.grant(plan, Disclosure.LOCAL_ONLY)

    def test_inputs_and_destination_invalidate_old_approval(self):
        approval = self.grant()
        for fields in (
            {"model": "other"},
            {"endpoint": "http://localhost:11434/v1/chat/completions"},
            {
                "request": replace(
                    self.binding.request, evidence=tuple(reversed(self.run.evidence))
                )
            },
            {
                "request": replace(
                    self.binding.request,
                    evidence=(
                        replace(self.run.evidence[0], excerpt="Changed"),
                        self.run.evidence[1],
                    ),
                )
            },
            {"request": replace(self.binding.request, limit=1)},
        ):
            binding = replace(self.binding, **fields)
            changed = replace(
                self.plan,
                steps=(
                    replace(self.plan.steps[0], semantic_comparison_binding=binding),
                ),
            )
            self.assertNotEqual(plan_digest(changed), approval.plan_digest)
            self.assertFalse(
                verify_plan_authorization(
                    approval, changed, self.run.run_id, approval.authorized_at
                ).authorizes
            )

    def test_missing_or_forged_canonical_evidence_refuses_approval(self):
        for fields in (
            {"excerpt": "Forged"},
            {"source_document_id": "missing"},
            {"evidence_id": "missing"},
            {"chunk_sha256": "0" * 64},
        ):
            request = replace(
                self.binding.request,
                evidence=(
                    replace(self.run.evidence[0], **fields),
                    self.run.evidence[1],
                ),
            )
            binding = replace(self.binding, request=request)
            plan = replace(
                self.plan,
                steps=(
                    replace(self.plan.steps[0], semantic_comparison_binding=binding),
                ),
            )
            with self.assertRaises(ResearchError):
                self.grant(plan)
            steps = (replace(self.steps[0], semantic_comparison_binding=binding),)
            self.assertFalse(
                self.authorizations.process_preview(
                    self.request(research_plan_steps=steps)
                ).success
            )

    def test_changed_run_and_question_refuse(self):
        with self.assertRaises(ResearchError):
            replace(self.plan, question="Other")
        binding = replace(
            self.binding, request=replace(self.binding.request, run_id="other")
        )
        changed = replace(
            self.plan,
            steps=(replace(self.plan.steps[0], semantic_comparison_binding=binding),),
        )
        with self.assertRaises(ResearchError):
            self.grant(changed)

    def test_extraction_and_lexical_approvals_are_not_comparison(self):
        approval = self.grant()
        extraction_binding = SemanticEvidenceStepBinding(
            "0" * 64, self.binding.endpoint, self.binding.model
        )
        extraction = replace(
            self.plan,
            steps=(
                replace(
                    self.plan.steps[0],
                    capability=Cap.SEMANTIC_EVIDENCE_PROPOSAL,
                    semantic_comparison_binding=None,
                    semantic_evidence_binding=extraction_binding,
                ),
            ),
        )
        other = self.grant(extraction)
        self.assertFalse(
            verify_plan_authorization(
                approval, extraction, self.run.run_id, approval.authorized_at
            ).authorizes
        )
        self.assertFalse(
            verify_plan_authorization(
                other, self.plan, self.run.run_id, other.authorized_at
            ).authorizes
        )
        for capability in (Cap.SOURCE_COMPARISON, Cap.SEMANTIC_EVIDENCE_PROPOSAL):
            with self.assertRaises(ResearchError):
                replace(self.plan.steps[0], capability=capability)
        self.assertEqual(cost_for(Cap.SOURCE_COMPARISON), ResearchOperationCost())

    def test_declared_cost_shared_budget_and_prior_spending(self):
        self.assertEqual(
            cost_for(Cap.SEMANTIC_EVIDENCE_COMPARISON), ResearchOperationCost(1, 1)
        )
        plan = replace(
            self.plan,
            steps=self.plan.steps + (replace(self.plan.steps[0], step_id="second"),),
        )
        with self.assertRaises(ResearchError):
            self.grant(plan)
        budget = replace(
            self.budget,
            max_step_advances=2,
            max_network_operations=2,
            max_llm_operations=2,
        )
        approval = self.grant(plan, budget=budget)
        allowance = ResearchExecutionAllowance(approval.budget)
        cost = cost_for(Cap.SEMANTIC_EVIDENCE_COMPARISON)
        once = allowance.charged(cost)
        self.assertTrue(once.affords(cost))
        self.assertFalse(once.charged(cost).affords(cost))
        self.assertEqual(allowance.spend.llm_operations, 0)

    def test_budget_and_disclosure_changes_require_new_preview(self):
        for change in (
            {"max_llm_operations": "2"},
            {"research_disclosure": "remote_permitted"},
        ):
            response = self.authorizations.process_preview(self.request())
            confirmed = self.authorizations.process_confirm(
                self.request(
                    authorization_id=response.research_plan_authorization.authorization_id,
                    **change,
                )
            )
            self.assertFalse(confirmed.success)

    def test_declared_policy_cost_drift_invalidates_approval(self):
        approval = self.grant()
        with patch.dict(
            CAPABILITY_COSTS,
            {Cap.SEMANTIC_EVIDENCE_COMPARISON: ResearchOperationCost(2, 1)},
        ):
            self.assertFalse(
                verify_plan_authorization(
                    approval, self.plan, self.run.run_id, approval.authorized_at
                ).authorizes
            )

    def test_store_roundtrip_preserves_legacy_and_new_approval_without_bodies(self):
        legacy = self.approval_store.load()
        approval = self.grant()
        loaded = self.approval_store.load()
        self.assertIn(approval, loaded)
        for old in legacy:
            self.assertIn(old, loaded)
            self.assertNotIn(Cap.SEMANTIC_EVIDENCE_COMPARISON, old.capabilities)
        payload = json.loads((self.root / "approvals.json").read_text())
        self.assertEqual(payload["schema_version"], 3)
        for e in self.run.evidence:
            self.assertNotIn(e.excerpt, (self.root / "approvals.json").read_text())
        self.assertTrue(
            verify_plan_authorization(
                approval, self.plan, self.run.run_id, approval.authorized_at
            ).authorizes
        )

    def test_expired_consumed_and_incompatible_disclosure_refuse(self):
        approval = self.grant()
        for changed, moment in (
            (approval, approval.expires_at + timedelta(seconds=1)),
            (
                approval.consumed_for("already-used", approval.authorized_at),
                approval.authorized_at,
            ),
            (replace(approval, disclosure=Disclosure.NONE), approval.authorized_at),
            (
                replace(approval, budget=replace(self.budget, max_llm_operations=0)),
                approval.authorized_at,
            ),
        ):
            self.assertFalse(
                verify_plan_authorization(
                    changed, self.plan, self.run.run_id, moment
                ).authorizes
            )

    def test_changed_evidence_after_preview_cannot_be_confirmed(self):
        response = self.authorizations.process_preview(self.request())
        with patch.object(
            self.manager,
            "get",
            return_value=replace(
                self.run,
                evidence=(
                    replace(self.run.evidence[0], excerpt="Changed excerpt"),
                    self.run.evidence[1],
                ),
            ),
        ):
            confirmed = self.authorizations.process_confirm(
                self.request(
                    authorization_id=response.research_plan_authorization.authorization_id
                )
            )
        self.assertFalse(confirmed.success)

    def test_contract_cannot_execute_and_automatic_mission_stays_closed(self):
        approval = self.grant()
        self.assertIsNone(
            self.execution._operation_registry.resolve(Cap.SEMANTIC_EVIDENCE_COMPARISON)
        )
        state = self.execution.start_for_plan(
            self.plan, self.run.run_id, approval.authorization_id
        )
        response = self.execution.process_advance(
            BrainRequest(
                message="Advance", metadata={"research_plan_id": state.plan_id}
            )
        )
        self.assertEqual(response.research_plan_execution.completed_steps, 0)
        self.assertEqual(
            self.execution.allowance(state.plan_id).spend.llm_operations, 0
        )
        denied = self.start(
            replace(self.budget, max_step_advances=11, max_network_operations=5)
        )
        self.assertFalse(denied.success)
        self.assertEqual(self.fetcher.fetch.call_count, 2)
