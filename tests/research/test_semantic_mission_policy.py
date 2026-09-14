"""Canonical construction and approval of future mission-owned text only."""

import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from cognition.ResearchGoalStartApplicationService import (
    ResearchGoalStartApplicationService,
)
from core.Exceptions import ResearchError
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchDisclosure import ResearchDisclosure as Disclosure
from research.ResearchDiscoveryProviderName import (
    ResearchDiscoveryProviderName as Provider,
)
from research.ResearchMissionScope import SEMANTIC_POLICY, ResearchMissionScope
from research.ResearchPlanAuthorization import ResearchPlanAuthorization
from research.ResearchPlanAuthorizationVerifier import verify_plan_authorization
from research.ResearchPlanConstraint import ResearchPlanConstraint
from research.ResearchPlanDigest import plan_digest
from research.ResearchPlanDraftService import ResearchPlanDraftService
from research.ResearchPlanRestriction import ResearchPlanRestriction
from research.ResearchPlanStepCapability import ResearchPlanStepCapability as Cap
from research.SemanticMissionPolicy import SemanticMissionPolicy


class SemanticMissionPolicyTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(UTC)
        self.policy = SemanticMissionPolicy(
            "http://127.0.0.1:11434/v1/chat/completions",
            "fixture",
            Disclosure.LOCAL_ONLY,
        )
        self.opening = (
            ResearchPlanDraftService()
            .preview_question("Research evidence", "crossref")
            .plan
        )
        self.budget = ResearchAutonomyBudget(
            max_step_advances=18, max_network_operations=9, max_llm_operations=2
        )
        self.plan = self.make_plan(self.policy)

    def make_plan(self, policy):
        scope = ResearchMissionScope(
            Provider.CROSSREF,
            source_policy=SEMANTIC_POLICY,
            max_sources=3,
            semantic_policy=policy,
        )
        return ResearchGoalStartApplicationService._mission_plan(self.opening, scope)

    def approval(self, plan=None, disclosure=Disclosure.LOCAL_ONLY, budget=None):
        return ResearchPlanAuthorization.for_plan(
            authorization_id="approval",
            plan=plan or self.plan,
            research_run_id="run",
            budget=budget or self.budget,
            authorized_at=self.now,
            expires_at=self.now + timedelta(minutes=10),
            disclosure=disclosure,
        )

    def test_valid_approval_and_exact_costs(self):
        value = self.approval()
        self.assertEqual(
            verify_plan_authorization(value, self.plan, "run", self.now).value, "valid"
        )
        self.assertIn(Cap.SEMANTIC_EVIDENCE_COMPARISON, value.capabilities)
        self.assertNotIn(Cap.SEMANTIC_EVIDENCE_PROPOSAL, value.capabilities)

    def test_policy_mutations_change_digest_and_invalidate_approval(self):
        value = self.approval()
        for fields in (
            {"model": "other"},
            {"max_input_bytes": 4000},
            {"endpoint": "http://localhost:11434/v1/chat/completions"},
            {"disclosure": Disclosure.REMOTE_PERMITTED},
        ):
            plan = self.make_plan(replace(self.policy, **fields))
            self.assertNotEqual(plan_digest(plan), value.plan_digest)
            self.assertEqual(
                verify_plan_authorization(value, plan, "run", self.now).value,
                "digest_mismatch",
            )

    def test_missing_disclosure_and_inadequate_cost_refuse(self):
        for disclosure in (Disclosure.NONE, Disclosure.REMOTE_PERMITTED):
            with self.assertRaises(ResearchError):
                self.approval(disclosure=disclosure)
        for field in (
            "max_step_advances",
            "max_network_operations",
            "max_llm_operations",
        ):
            with self.assertRaises(ResearchError):
                self.approval(budget=replace(self.budget, **{field: 1}))

    def test_unbounded_or_inconsistent_input_policies_refuse(self):
        for fields in (
            {"input_scope": "any_file"},
            {"selection": "anything"},
            {"retention": "verified_facts"},
            {"max_input_bytes": 8193},
            {"max_input_bytes": True},
            {"endpoint": ""},
            {"disclosure": Disclosure.NONE},
            {"endpoint": "https://remote.example/v1/chat/completions"},
        ):
            with self.subTest(fields=fields), self.assertRaises(ResearchError):
                replace(self.policy, **fields)

    def test_legacy_scope_cannot_smuggle_model_policy(self):
        for policy in (self.policy, "bad", object()):
            with self.assertRaises(ResearchError):
                ResearchMissionScope(Provider.CROSSREF, semantic_policy=policy)
        with self.assertRaises(ResearchError):
            replace(self.plan, mission_scope=None)
        with self.assertRaises(ResearchError):
            replace(self.plan.steps[10], capability=Cap.SEMANTIC_EVIDENCE_PROPOSAL)

    def test_restriction_conflict_and_expired_approval_refuse(self):
        plan = replace(
            self.plan,
            constraints=(
                ResearchPlanConstraint(
                    "No external sources",
                    ResearchPlanRestriction.NO_EXTERNAL_SOURCE_ACCESS,
                ),
            ),
        )
        with self.assertRaises(ResearchError):
            self.approval(plan=plan)
        value = self.approval()
        self.assertEqual(
            verify_plan_authorization(
                value, self.plan, "run", self.now + timedelta(hours=1)
            ).value,
            "expired",
        )

    def test_old_opening_approval_never_acquires_semantic_authority(self):
        value = self.approval(plan=self.opening, disclosure=Disclosure.NONE)
        self.assertNotIn(Cap.SEMANTIC_EVIDENCE_COMPARISON, value.capabilities)
        self.assertEqual(
            verify_plan_authorization(value, self.plan, "run", self.now).value,
            "digest_mismatch",
        )
