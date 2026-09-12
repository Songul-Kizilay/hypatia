"""Exact-pair model execution through real approval, dispatch and persistence."""

import json
import unittest
from dataclasses import replace
from functools import partial
from unittest.mock import Mock, patch

from brain.BrainRequest import BrainRequest
from cognition.CognitiveEngine import CognitiveEngine
from core.CancellationSignal import CancellationSignal
from research.ResearchCapabilityCost import cost_for
from research.ResearchDisclosure import ResearchDisclosure
from research.ResearchPlanStepCapability import ResearchPlanStepCapability as Cap
from research.SemanticComparisonStepOperation import SemanticComparisonStepOperation
from research.StartsResearchPlanExecution import ResearchPlanExecutionStartRefusal
from tests.integration import test_research_goal_opening as opening
from tests.integration import test_semantic_comparison_approval_contract as contract


class SemanticComparisonExecutionTests(unittest.TestCase):
    def setUp(self):
        self.fx = contract.SemanticComparisonApprovalTests()
        self.fx.setUp()
        self.addCleanup(self.fx.doCleanups)
        self.transport = Mock(return_value=self.output())
        self.operation = self.operation_for()
        # Real composition registration, not a fake executor or helper-only call.
        with patch.object(
            opening,
            "CognitiveEngine",
            partial(CognitiveEngine, semantic_comparison_operation=self.operation),
        ):
            self.fx.engine = self.fx.make_engine()
        self.fx.authorizations = self.fx.engine._plan_authorization_service
        self.execution = self.fx.execution

    def output(self, **changes):
        row = {
            "relation": "possible_conflict",
            "left_quote": self.fx.run.evidence[0].excerpt[:50],
            "right_quote": self.fx.run.evidence[1].excerpt[:50],
            "rationale": "Tentative interpretation; verify conditions.",
        }
        row.update(changes)
        return {
            "choices": [{"message": {"content": json.dumps({"comparisons": [row]})}}]
        }

    def operation_for(self, **changes):
        return SemanticComparisonStepOperation(
            **{
                "endpoint": self.fx.binding.endpoint,
                "model": self.fx.binding.model,
                "api_key": None,
                "transport": self.transport,
                "run_manager": self.fx.manager,
                **changes,
            }
        )

    def start(self, plan=None, budget=None):
        plan = plan or self.fx.plan
        approval = self.fx.grant(plan, budget=budget)
        state = self.execution.start_for_plan(
            plan, self.fx.run.run_id, approval.authorization_id
        )
        self.assertNotIsInstance(state, ResearchPlanExecutionStartRefusal)
        self.transport.assert_not_called()
        return state

    def advance(self, token=None):
        return self.execution.process_advance(
            BrainRequest(
                message="Advance",
                metadata={"research_plan_id": self.fx.plan.plan_id},
                cancellation_token=token,
            )
        )

    def test_valid_result_and_durable_charge_before_exact_destination_call(self):
        self.start()
        original = self.transport.return_value

        def observe(*args, **kwargs):
            snapshot = next(
                s for s in self.fx.store.load() if s.plan_id == self.fx.plan.plan_id
            )
            self.assertEqual(snapshot.steps[0].status.value, "running")
            spend = snapshot.allowance.spend
            self.assertEqual(
                (spend.step_advances, spend.network_operations, spend.llm_operations),
                (1, 1, 1),
            )
            self.assertEqual(args[0], self.fx.binding.endpoint)
            self.assertEqual(args[2]["model"], self.fx.binding.model)
            return original

        self.transport.side_effect = observe
        response = self.advance()
        self.transport.assert_called_once()
        (result,) = response.semantic_comparison_proposals
        self.assertEqual(result.request, self.fx.binding.request)
        self.assertEqual(result.execution_id, self.fx.plan.plan_id)
        self.assertEqual(result.candidates[0].relation.value, "possible_conflict")
        self.assertIn("tentative", response.message)
        self.assertEqual(self.fx.manager.get(self.fx.run.run_id), self.fx.run)
        snapshot = next(
            s for s in self.fx.store.load() if s.plan_id == self.fx.plan.plan_id
        )
        self.assertEqual(snapshot.steps[0].status.value, "completed")
        self.assertTrue(snapshot.steps[0].work_performed)
        self.advance()
        self.transport.assert_called_once()

    def test_missing_or_wrong_approval_cannot_start(self):
        for authorization_id in (
            "missing",
            self.fx.approval_store.load()[0].authorization_id,
        ):
            state = self.execution.start_for_plan(
                self.fx.plan, self.fx.run.run_id, authorization_id
            )
            self.assertIsInstance(state, ResearchPlanExecutionStartRefusal)
        self.transport.assert_not_called()

    def test_changed_destination_approval_cannot_start(self):
        approval = self.fx.grant()
        changed = replace(
            self.fx.plan,
            steps=(
                replace(
                    self.fx.plan.steps[0],
                    semantic_comparison_binding=replace(self.fx.binding, model="other"),
                ),
            ),
        )
        state = self.execution.start_for_plan(
            changed, self.fx.run.run_id, approval.authorization_id
        )
        self.assertIsInstance(state, ResearchPlanExecutionStartRefusal)
        self.transport.assert_not_called()

    def test_configured_destination_mismatch_never_calls_or_falls_back(self):
        self.start()
        with patch.object(
            self.execution._operation_registry,
            "resolve",
            return_value=self.operation_for(model="other"),
        ):
            response = self.advance()
        self.assertEqual(response.semantic_comparison_proposals, ())
        self.transport.assert_not_called()

    def test_changed_evidence_after_start_never_calls(self):
        self.start()
        run = replace(
            self.fx.run,
            evidence=(
                replace(self.fx.run.evidence[0], excerpt="changed"),
                self.fx.run.evidence[1],
            ),
        )
        with patch.object(self.fx.manager, "get", return_value=run):
            response = self.advance()
        self.assertEqual(response.semantic_comparison_proposals, ())
        self.transport.assert_not_called()
        self.assertEqual(
            self.execution.allowance(self.fx.plan.plan_id).spend.llm_operations, 1
        )

    def test_wrong_run_or_disclosure_context_never_calls(self):
        self.start()
        context = self.execution._contexts[self.fx.plan.plan_id]
        self.execution._contexts[self.fx.plan.plan_id] = replace(
            context, disclosure=ResearchDisclosure.NONE
        )
        self.advance()
        self.transport.assert_not_called()

    def test_missing_current_run_never_calls(self):
        from core.Exceptions import ResearchError

        self.start()
        with patch.object(self.fx.manager, "get", side_effect=ResearchError("missing")):
            self.advance()
        self.transport.assert_not_called()

    def test_exhausted_cumulative_budget_refuses_before_attempt(self):
        self.start()
        allowance = self.execution.allowance(self.fx.plan.plan_id)
        self.execution._allowances[self.fx.plan.plan_id] = allowance.charged(
            cost_for(Cap.SEMANTIC_EVIDENCE_COMPARISON)
        )
        before = self.execution.allowance(self.fx.plan.plan_id)
        response = self.advance()
        self.assertFalse(response.success)
        self.assertEqual(self.execution.allowance(self.fx.plan.plan_id), before)
        self.transport.assert_not_called()

    def test_two_steps_preserve_prior_spend_without_reset(self):
        self.fx.plan = replace(
            self.fx.plan,
            steps=(
                self.fx.plan.steps[0],
                replace(self.fx.plan.steps[0], step_id="second"),
            ),
        )
        budget = replace(
            self.fx.budget,
            max_step_advances=2,
            max_network_operations=2,
            max_llm_operations=2,
        )
        self.start(budget=budget)
        self.advance()
        self.advance()
        self.assertEqual(self.transport.call_count, 2)
        self.assertEqual(
            self.execution.allowance(self.fx.plan.plan_id).spend.llm_operations, 2
        )
        self.advance()
        self.assertEqual(self.transport.call_count, 2)

    def test_invalid_output_charges_once_and_does_not_retry(self):
        self.start()
        self.transport.return_value = self.output(left_quote="Invented quotation")
        response = self.advance()
        self.assertEqual(response.semantic_comparison_proposals, ())
        self.assertEqual(
            response.research_plan_execution.steps[0].status.value, "failed"
        )
        self.assertEqual(
            self.execution.allowance(self.fx.plan.plan_id).spend.llm_operations, 1
        )
        self.advance()
        self.transport.assert_called_once()

    def test_malformed_output_fails(self):
        self.start()
        self.transport.return_value = {
            "choices": [{"message": {"content": "bad json"}}]
        }
        self.assertEqual(self.advance().semantic_comparison_proposals, ())
        self.transport.assert_called_once()

    def test_not_comparable_is_observable_not_truth(self):
        self.start()
        self.transport.return_value = self.output(relation="not_comparable")
        (result,) = self.advance().semantic_comparison_proposals
        self.assertEqual(result.candidates[0].relation.value, "not_comparable")

    def test_cancel_before_call_prevents_disclosure(self):
        self.start()
        signal = CancellationSignal()
        signal.cancel()
        self.assertEqual(self.advance(signal).semantic_comparison_proposals, ())
        self.transport.assert_not_called()

    def test_cancel_during_call_discards_result_and_keeps_charge(self):
        self.start()
        signal = CancellationSignal()

        def cancel(*args):
            signal.cancel()
            return self.output()

        self.transport.side_effect = cancel
        self.assertEqual(self.advance(signal).semantic_comparison_proposals, ())
        self.assertEqual(
            self.execution.allowance(self.fx.plan.plan_id).spend.llm_operations, 1
        )
        self.advance()
        self.transport.assert_called_once()

    def test_transport_failure_has_no_retry_or_private_diagnostic(self):
        self.start()
        self.transport.side_effect = OSError("private diagnostic")
        response = self.advance()
        self.assertEqual(response.semantic_comparison_proposals, ())
        self.assertNotIn("private diagnostic", response.message)
        self.advance()
        self.transport.assert_called_once()

    def test_failed_checkpoint_does_not_reach_model(self):
        self.start()
        with patch.object(self.execution, "_persist_checkpoint", return_value=False):
            self.advance()
        self.transport.assert_not_called()
        self.assertEqual(
            self.execution.allowance(self.fx.plan.plan_id).spend.llm_operations, 0
        )

    def test_automatic_entry_stays_closed_with_registered_operation(self):
        # The fresh engine is registered; use its actual goal boundary.
        response = self.fx.engine.process(
            BrainRequest(
                message=opening.QUESTION,
                metadata={
                    "intent": "research_goal_start",
                    "research_goal_scope": opening.OPENING_SCOPE,
                    "discovery_provider": "crossref",
                    "research_autonomy_budget": self.fx.budget,
                },
            )
        )
        self.assertFalse(response.success)
        self.transport.assert_not_called()

    def test_wrong_run_membership_never_calls(self):
        self.start()
        with patch.object(
            self.fx.manager, "get", return_value=replace(self.fx.run, run_id="other")
        ):
            self.advance()
        self.transport.assert_not_called()

    def test_missing_pair_and_sources_never_calls(self):
        self.start()
        empty = replace(
            self.fx.run, sources=(), evidence=(), assessments=(), comparison_notes=()
        )
        with patch.object(self.fx.manager, "get", return_value=empty):
            self.advance()
        self.transport.assert_not_called()

    def test_extraction_approval_cannot_start_comparison(self):
        from research.SemanticEvidenceStepBinding import SemanticEvidenceStepBinding

        extraction = replace(
            self.fx.plan,
            steps=(
                replace(
                    self.fx.plan.steps[0],
                    capability=Cap.SEMANTIC_EVIDENCE_PROPOSAL,
                    semantic_comparison_binding=None,
                    semantic_evidence_binding=SemanticEvidenceStepBinding(
                        self.fx.binding.request.content_fingerprint,
                        self.fx.binding.endpoint,
                        self.fx.binding.model,
                    ),
                ),
            ),
        )
        approval = self.fx.grant(extraction)
        result = self.execution.start_for_plan(
            self.fx.plan, self.fx.run.run_id, approval.authorization_id
        )
        self.assertIsInstance(result, ResearchPlanExecutionStartRefusal)
        self.transport.assert_not_called()

    def test_lexical_dispatch_cannot_run_comparison_operation(self):
        lexical = replace(
            self.fx.plan,
            steps=(
                replace(
                    self.fx.plan.steps[0],
                    capability=Cap.SOURCE_COMPARISON,
                    semantic_comparison_binding=None,
                ),
            ),
        )
        self.fx.plan = lexical
        self.start()
        with patch.object(
            self.execution._operation_registry, "resolve", return_value=self.operation
        ):
            response = self.advance()
        self.assertEqual(response.semantic_comparison_proposals, ())
        self.transport.assert_not_called()

    def test_duplicate_output_rejected_without_retry(self):
        self.start()
        payload = self.output()
        body = json.loads(payload["choices"][0]["message"]["content"])
        body["comparisons"] *= 2
        payload["choices"][0]["message"]["content"] = json.dumps(body)
        self.transport.return_value = payload
        self.assertEqual(self.advance().semantic_comparison_proposals, ())
        self.advance()
        self.transport.assert_called_once()

    def test_bounded_continuation_preserves_observable_result(self):
        self.start()
        response = self.execution.process_continue(
            BrainRequest(
                message="Continue",
                metadata={"research_plan_id": self.fx.plan.plan_id, "max_steps": 1},
            )
        )
        self.assertEqual(len(response.semantic_comparison_proposals), 1)
        self.transport.assert_called_once()
