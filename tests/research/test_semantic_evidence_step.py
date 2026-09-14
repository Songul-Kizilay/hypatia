"""Approved semantic operation through the real executor, with fake transport."""

import json
import unittest
from dataclasses import replace
from unittest.mock import Mock

from brain.BrainRequest import BrainRequest
from core.CancellationSignal import CancellationSignal
from core.Exceptions import ResearchError
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchCapabilityCost import cost_for
from research.ResearchDisclosure import ResearchDisclosure
from research.ResearchExecutionAllowance import ResearchExecutionAllowance
from research.ResearchPlanDigest import plan_digest
from research.ResearchPlanExecutionContext import ResearchPlanExecutionContext
from research.ResearchPlanOperationRegistry import ResearchPlanOperationRegistry
from research.ResearchPlanRestriction import ResearchPlanRestriction
from research.ResearchPlanStepCapability import ResearchPlanStepCapability as Capability
from research.ResearchPlanStepDraftInput import ResearchPlanStepDraftInput
from research.ResearchPlanStepOperationResult import ResearchPlanStepOperationResult
from research.SemanticEvidenceRequest import SemanticEvidenceRequest
from research.SemanticEvidenceStepBinding import SemanticEvidenceStepBinding
from research.SemanticEvidenceStepOperation import SemanticEvidenceStepOperation
from tests.desktop.test_research_source_preview_panel import preview
from tests.research import test_execution_disclosure_context as fixture


class SemanticEvidenceStepTests(unittest.TestCase):
    def setUp(self):
        self.fx = fixture.ExecutionDisclosureTests()
        self.fx.setUp()
        self.addCleanup(self.fx.doCleanups)
        self.request = SemanticEvidenceRequest(
            "Research question",
            (
                replace(
                    preview(text="Exact quotation with provenance"),
                    run_id=self.fx.run_id,
                ),
            ),
        )
        self.requests = {self.request.content_fingerprint: self.request}
        self.transport = Mock(
            return_value={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "candidates": [
                                        {
                                            "source": "0",
                                            "quote": "Exact quotation",
                                            "rationale": "Tentative",
                                        }
                                    ]
                                }
                            )
                        }
                    }
                ]
            }
        )
        self.endpoint = "http://127.0.0.1:11434/v1/chat/completions"
        self.model = "test-model"
        self.binding = SemanticEvidenceStepBinding(
            self.request.content_fingerprint, self.endpoint, self.model
        )
        self.fx.steps = (
            ResearchPlanStepDraftInput(
                instruction="Propose unaccepted evidence",
                capability=Capability.SEMANTIC_EVIDENCE_PROPOSAL.value,
                semantic_evidence_binding=self.binding,
            ),
        )
        self.operation = self.operation_for()
        self.fx.registry = ResearchPlanOperationRegistry(
            {Capability.SEMANTIC_EVIDENCE_PROPOSAL: self.operation}
        )
        self.fx.execution = self.fx.service()

    def operation_for(self, endpoint=None, model=None):
        return SemanticEvidenceStepOperation(
            endpoint=endpoint or self.endpoint,
            model=model or self.model,
            api_key=None,
            transport=self.transport,
            resolve_request=self.requests.get,
        )

    def start(self, disclosure=ResearchDisclosure.LOCAL_ONLY):
        plan = self.fx.drafts.preview("Research question", self.fx.steps).plan
        budget = ResearchAutonomyBudget(
            max_step_advances=1, max_network_operations=1, max_llm_operations=1
        )
        approval = self.fx.authorizations.record_for_plan(
            plan, self.fx.run_id, disclosure, budget
        )
        state = self.fx.execution.start_for_plan(
            plan, self.fx.run_id, approval.authorization_id
        )
        self.assertEqual(state.plan_id, plan.plan_id)
        return plan, state

    def direct_context(self, **changes):
        return replace(
            ResearchPlanExecutionContext(
                research_run_id=self.fx.run_id,
                execution_id="semantic-execution",
                research_question="Research question",
                disclosure=ResearchDisclosure.LOCAL_ONLY,
            ),
            **changes,
        )

    def step(self):
        return self.fx.drafts.preview("Research question", self.fx.steps).plan.steps[0]

    def test_approval_start_is_zero_step_and_advance_charges_before_call(self):
        plan, state = self.start()
        self.transport.assert_not_called()
        original = self.transport.return_value

        def observe(*args):
            allowance = self.fx.execution._allowances[state.plan_id]
            self.assertEqual(
                (
                    allowance.spend.step_advances,
                    allowance.spend.network_operations,
                    allowance.spend.llm_operations,
                ),
                (1, 1, 1),
            )
            return original

        self.transport.side_effect = observe
        result = self.fx.advance(self.fx.execution, state.plan_id)
        self.assertTrue(result.success)
        self.transport.assert_called_once()
        payload = result.semantic_evidence_proposals[0]
        self.assertEqual(payload.candidates[0].quote, "Exact quotation")
        self.assertIs(payload.candidates[0].preview, self.request.previews[0])
        self.assertEqual(payload.execution_id, plan.plan_id)
        self.assertNotIn("Exact quotation", result.message)
        self.assertNotIn("Exact quotation", repr(result))
        self.fx.advance(self.fx.execution, state.plan_id)
        self.transport.assert_called_once()

    def test_authored_start_and_continue_return_transient_result(self):
        plan = self.fx.drafts.preview("Research question", self.fx.steps).plan
        approval = self.fx.authorizations.record_for_plan(
            plan,
            self.fx.run_id,
            ResearchDisclosure.LOCAL_ONLY,
            ResearchAutonomyBudget(max_llm_operations=1),
        )
        started = self.fx.authored(self.fx.execution, approval.authorization_id)
        self.assertTrue(started.success)
        self.transport.assert_not_called()
        result = self.fx.execution.process_continue(
            BrainRequest(
                message="Continue",
                metadata={
                    "research_plan_id": started.research_plan_execution.plan_id,
                    "max_steps": "1",
                },
            )
        )
        self.assertTrue(result.success)
        self.assertEqual(len(result.semantic_evidence_proposals), 1)

    def test_no_disclosure_refuses_without_transport_and_is_not_refunded(self):
        _, state = self.start(ResearchDisclosure.NONE)
        result = self.fx.advance(self.fx.execution, state.plan_id)
        self.assertEqual(result.semantic_evidence_proposals, ())
        self.transport.assert_not_called()
        self.assertEqual(
            self.fx.execution._allowances[state.plan_id].spend.llm_operations, 1
        )

    def test_unapproved_executor_cannot_run_model_even_with_fake_metadata(self):
        execution = self.fx.service(approved=False)
        started = self.fx.authored(execution, "fake", disclosure="remote_permitted")
        result = self.fx.advance(execution, started.research_plan_execution.plan_id)
        self.assertFalse(result.success)
        self.transport.assert_not_called()

    def test_insufficient_approval_budget_is_refused(self):
        plan = self.fx.drafts.preview("Research question", self.fx.steps).plan
        with self.assertRaises(ResearchError):
            self.fx.authorizations.record_for_plan(
                plan, self.fx.run_id, ResearchDisclosure.LOCAL_ONLY
            )
        self.transport.assert_not_called()

    def test_exhausted_model_budget_refuses_before_operation(self):
        _, state = self.start()
        allowance = self.fx.execution._allowances[state.plan_id]
        self.fx.execution._allowances[state.plan_id] = ResearchExecutionAllowance(
            allowance.budget, replace(allowance.spend, llm_operations=1)
        )
        result = self.fx.advance(self.fx.execution, state.plan_id)
        self.assertFalse(result.success)
        self.transport.assert_not_called()
        self.assertEqual(
            self.fx.execution._allowances[state.plan_id].spend.step_advances, 0
        )

    def test_transport_error_and_bad_output_consume_one_attempt(self):
        for response in (None, "bad"):
            self.transport.reset_mock()
            plan, state = self.start()
            if response is None:
                self.transport.side_effect = OSError("private diagnostic")
            else:
                self.transport.side_effect = None
                self.transport.return_value = {
                    "choices": [{"message": {"content": response}}]
                }
            result = self.fx.advance(self.fx.execution, state.plan_id)
            self.assertEqual(result.semantic_evidence_proposals, ())
            self.assertEqual(
                self.fx.execution._allowances[plan.plan_id].spend.llm_operations, 1
            )
            self.assertNotIn("private diagnostic", result.message)
            self.transport.assert_called_once()

    def test_changed_or_missing_input_never_refetches(self):
        for value in (None, replace(self.request, question="Changed")):
            self.requests[self.binding.input_fingerprint] = value
            result = self.operation.run(self.step(), self.direct_context())
            self.assertFalse(result.performed)
        self.transport.assert_not_called()

    def test_wrong_run_question_or_execution_refuses(self):
        for changes in (
            {"research_run_id": "other"},
            {"research_question": "other"},
            {"execution_id": None},
        ):
            result = self.operation.run(self.step(), self.direct_context(**changes))
            self.assertFalse(result.performed)
        self.transport.assert_not_called()

    def test_exact_destination_and_model_mismatch_refuses(self):
        for operation in (
            self.operation_for(model="different"),
            self.operation_for(endpoint="https://example.org/model"),
        ):
            self.assertFalse(
                operation.run(
                    self.step(),
                    self.direct_context(disclosure=ResearchDisclosure.REMOTE_PERMITTED),
                ).performed
            )
        self.transport.assert_not_called()

    def test_local_permission_cannot_reach_remote_but_explicit_remote_can(self):
        endpoint = "https://example.org/model"
        operation = self.operation_for(endpoint=endpoint)
        step = replace(
            self.step(),
            semantic_evidence_binding=replace(self.binding, endpoint=endpoint),
        )
        self.assertFalse(operation.run(step, self.direct_context()).performed)
        self.transport.assert_not_called()
        result = operation.run(
            step, self.direct_context(disclosure=ResearchDisclosure.REMOTE_PERMITTED)
        )
        self.assertTrue(result.succeeded)
        self.assertEqual(self.transport.call_args.args[0], endpoint)

    def test_cancel_before_and_during_model_call_discards_output(self):
        signal = CancellationSignal()
        signal.cancel()
        self.assertFalse(
            self.operation.run(
                self.step(), self.direct_context(cancellation_token=signal)
            ).performed
        )
        self.transport.assert_not_called()
        signal = CancellationSignal()
        original = self.transport.return_value

        def cancel(*args):
            signal.cancel()
            return original

        self.transport.side_effect = cancel
        result = self.operation.run(
            self.step(), self.direct_context(cancellation_token=signal)
        )
        self.assertTrue(result.performed)
        self.assertFalse(result.succeeded)
        self.assertIsNone(result.semantic_evidence)

    def test_restart_and_status_do_not_restore_source_or_permission(self):
        plan, state = self.start()
        restored = self.fx.service()
        restored.rebind_restored(plan, self.fx.run_id, state.plan_id)
        result = self.fx.advance(restored, state.plan_id)
        self.transport.assert_not_called()
        self.assertEqual(result.semantic_evidence_proposals, ())
        content = (self.fx.root / "executions.json").read_text(encoding="utf-8")
        self.assertNotIn(self.request.previews[0].source.content, content)
        self.assertNotIn("Tentative", content)

    def test_no_acceptance_and_no_proposals_in_durable_status(self):
        _, state = self.start()
        self.fx.advance(self.fx.execution, state.plan_id)
        response = self.fx.execution.process_status(
            BrainRequest(message="Status", metadata={"research_plan_id": state.plan_id})
        )
        self.assertEqual(response.semantic_evidence_proposals, ())
        for path in self.fx.root.glob("*.json"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(self.request.previews[0].source.content, text)
            self.assertNotIn('"Tentative"', text)

    def test_binding_changes_plan_digest_and_legacy_digest_is_preserved(self):
        plan = self.fx.drafts.preview("Research question", self.fx.steps).plan
        for changes in (
            {"input_fingerprint": "a" * 64},
            {"model": "other"},
            {"endpoint": "https://example.org/model"},
        ):
            binding = replace(self.binding, **changes)
            changed = replace(
                plan, steps=(replace(plan.steps[0], semantic_evidence_binding=binding),)
            )
            self.assertNotEqual(plan_digest(plan), plan_digest(changed))
        legacy = self.fx.drafts.preview(
            "Legacy question",
            (
                ResearchPlanStepDraftInput(
                    instruction="Local check", capability="local_knowledge_search"
                ),
            ),
        ).plan
        self.assertEqual(
            plan_digest(legacy),
            "f8bce090b941a30d7c71cf74047b6c07ce07064ab15de9099865b9e4472aaf79",
        )

    def test_binding_cannot_be_placed_on_other_capability_or_mixed_authority(self):
        for changes in (
            {"capability": Capability.SOURCE_FETCH},
            {"authorized_source_url": "https://example.org"},
            {"selected_source_document_ids": ("doc",)},
            {"semantic_evidence_binding": None},
        ):
            with self.assertRaises(ResearchError):
                replace(self.step(), **changes)
        self.assertEqual(
            cost_for(Capability.SEMANTIC_EVIDENCE_PROPOSAL).llm_operations, 1
        )
        self.assertTrue(
            ResearchPlanRestriction.NO_EXTERNAL_SOURCE_ACCESS.forbids(
                Capability.SEMANTIC_EVIDENCE_PROPOSAL
            )
        )

    def test_invalid_binding_destinations_fail_closed(self):
        for endpoint in (
            "http://example.org",
            "https://user:pass@example.org",
            "https://example.org/\n",
            "not-url",
        ):
            with self.assertRaises(ResearchError):
                replace(self.binding, endpoint=endpoint)
        for fingerprint in ("", "x" * 64, None):
            with self.assertRaises(ResearchError):
                replace(self.binding, input_fingerprint=fingerprint)

    def test_other_operation_cannot_smuggle_semantic_result(self):
        payload = self.operation.run(
            self.step(), self.direct_context()
        ).semantic_evidence
        stub = Mock(operation_name="unrelated")
        stub.run.return_value = ResearchPlanStepOperationResult(
            performed=True, detail="done", semantic_evidence=payload
        )
        self.fx.steps = (
            ResearchPlanStepDraftInput(
                instruction="Local check", capability="local_knowledge_search"
            ),
        )
        self.fx.registry = ResearchPlanOperationRegistry(
            {Capability.LOCAL_KNOWLEDGE_SEARCH: stub}
        )
        self.fx.execution = self.fx.service()
        plan, state = self.start()
        self.assertEqual(
            self.fx.advance(
                self.fx.execution, state.plan_id
            ).semantic_evidence_proposals,
            (),
        )

    def approval_request(self, **changes):
        return BrainRequest(
            message="Review",
            metadata={
                "research_run_id": self.fx.run_id,
                "research_plan_question": "Research question",
                "research_plan_steps": self.fx.steps,
                "max_llm_operations": "1",
                "research_disclosure": "local_only",
                **changes,
            },
        )

    def test_approval_preview_names_binding_then_confirm_start_advance(self):
        reviewed = self.fx.authorizations.process_preview(self.approval_request())
        self.assertTrue(reviewed.success)
        for value in (self.endpoint, self.model, self.binding.input_fingerprint):
            self.assertIn(value, reviewed.message)
        self.assertNotIn(self.request.previews[0].source.content, reviewed.message)
        self.transport.assert_not_called()
        approval_id = reviewed.research_plan_authorization.authorization_id
        confirmed = self.fx.authorizations.process_confirm(
            self.approval_request(authorization_id=approval_id)
        )
        self.assertTrue(confirmed.success)
        started = self.fx.authored(self.fx.execution, approval_id)
        self.assertTrue(started.success)
        self.transport.assert_not_called()
        advanced = self.fx.advance(
            self.fx.execution, started.research_plan_execution.plan_id
        )
        self.assertEqual(len(advanced.semantic_evidence_proposals), 1)

    def test_changed_binding_cannot_confirm_old_approval(self):
        reviewed = self.fx.authorizations.process_preview(self.approval_request())
        old_id = reviewed.research_plan_authorization.authorization_id
        changed_steps = (
            replace(
                self.fx.steps[0],
                semantic_evidence_binding=replace(self.binding, model="other"),
            ),
        )
        confirmed = self.fx.authorizations.process_confirm(
            self.approval_request(
                authorization_id=old_id, research_plan_steps=changed_steps
            )
        )
        self.assertFalse(confirmed.success)
        self.transport.assert_not_called()

    def test_empty_model_output_is_successful_zero_proposals(self):
        self.transport.return_value = {
            "choices": [{"message": {"content": '{"candidates":[]}'}}]
        }
        _, state = self.start()
        response = self.fx.advance(self.fx.execution, state.plan_id)
        self.assertTrue(response.success)
        self.assertEqual(response.semantic_evidence_proposals[0].candidates, ())
        self.transport.assert_called_once()


if __name__ == "__main__":
    unittest.main()
