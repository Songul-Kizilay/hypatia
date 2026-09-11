"""Consumed approval -> live operation context; restart never invents consent."""

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from brain.BrainRequest import BrainRequest
from cognition.ResearchPlanAuthorizationApplicationService import (
    ResearchPlanAuthorizationApplicationService,
)
from cognition.ResearchPlanExecutionApplicationService import (
    ResearchPlanExecutionApplicationService,
)
from core.Exceptions import ResearchError
from core.ExclusiveStoreOwnership import release_all
from research.JsonFileResearchExecutionStore import JsonFileResearchExecutionStore
from research.JsonFileResearchPlanAuthorizationStore import (
    JsonFileResearchPlanAuthorizationStore,
)
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchDisclosure import ResearchDisclosure
from research.ResearchPlanDraftService import ResearchPlanDraftService
from research.ResearchPlanExecutionContext import ResearchPlanExecutionContext
from research.ResearchPlanOperationRegistry import ResearchPlanOperationRegistry
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchPlanStepDraftInput import ResearchPlanStepDraftInput
from research.ResearchPlanStepOperationResult import ResearchPlanStepOperationResult
from research.ResearchRunManager import ResearchRunManager
from response.ResponseComposer import ResponseComposer


class RecordingOperation:
    operation_name = "record_context"

    def __init__(self):
        self.contexts = []

    def run(self, step, context):
        self.contexts.append(context)
        return ResearchPlanStepOperationResult(performed=True, detail="Local check.")


class ExecutionDisclosureTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.addCleanup(release_all)
        self.root = Path(temporary.name)
        self.manager = ResearchRunManager(
            JsonFileResearchRunStore(self.root / "runs.json")
        )
        self.run_id = self.manager.create("Research question").run_id
        self.composer = ResponseComposer()
        self.authorizations = ResearchPlanAuthorizationApplicationService(
            self.manager,
            self.composer,
            authorization_store=JsonFileResearchPlanAuthorizationStore(
                self.root / "approvals.json"
            ),
        )
        self.drafts = ResearchPlanDraftService()
        self.steps = (
            ResearchPlanStepDraftInput(
                instruction="Local check", capability="local_knowledge_search"
            ),
        )
        self.operation = RecordingOperation()
        self.registry = ResearchPlanOperationRegistry(
            {ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH: self.operation}
        )
        self.store = JsonFileResearchExecutionStore(self.root / "executions.json")
        self.execution = self.service()

    def service(self, approved=True):
        return ResearchPlanExecutionApplicationService(
            self.composer,
            self.drafts,
            operation_registry=self.registry,
            authorization_consumer=self.authorizations if approved else None,
            execution_store=self.store,
        )

    def grant(self, disclosure):
        plan = self.drafts.preview("Research question", self.steps).plan
        authorization = self.authorizations.record_for_plan(
            plan, self.run_id, disclosure
        )
        self.assertIsNotNone(authorization)
        return plan, authorization

    def advance(self, service, execution_id, **metadata):
        return service.process_advance(
            BrainRequest(
                message="Advance",
                metadata={"research_plan_id": execution_id, **metadata},
            )
        )

    def authored(self, service, authorization_id, **metadata):
        return service.process_start(
            BrainRequest(
                message="Start",
                metadata={
                    "research_plan_question": "Research question",
                    "research_plan_steps": self.steps,
                    "research_run_id": self.run_id,
                    "authorization_id": authorization_id,
                    **metadata,
                },
            )
        )

    def test_context_defaults_to_none_and_rejects_untyped_permission(self):
        self.assertIs(
            ResearchPlanExecutionContext().disclosure, ResearchDisclosure.NONE
        )
        for value in (None, "remote_permitted", True, 1):
            with self.assertRaises(ResearchError):
                ResearchPlanExecutionContext(disclosure=value)

    def test_authored_start_preserves_exact_consumed_disclosure(self):
        for disclosure in ResearchDisclosure:
            with self.subTest(disclosure=disclosure):
                _, approval = self.grant(disclosure)
                started = self.authored(self.execution, approval.authorization_id)
                self.assertTrue(started.success)
                before = len(self.operation.contexts)
                state = started.research_plan_execution
                self.assertIsNotNone(state)
                self.assertIs(
                    self.execution._contexts[state.plan_id].disclosure, disclosure
                )
                self.assertEqual(len(self.operation.contexts), before)
                self.assertTrue(self.advance(self.execution, state.plan_id).success)
                self.assertIs(self.operation.contexts[-1].disclosure, disclosure)
                consumed = self.authorizations.authorization_for_execution(
                    state.plan_id
                )
                self.assertTrue(consumed.is_consumed)
                self.assertIs(consumed.disclosure, disclosure)

    def test_derived_plan_start_preserves_exact_consumed_disclosure(self):
        for disclosure in ResearchDisclosure:
            plan, approval = self.grant(disclosure)
            state = self.execution.start_for_plan(
                plan, self.run_id, approval.authorization_id
            )
            self.assertEqual(state.plan_id, plan.plan_id)
            self.assertTrue(self.advance(self.execution, state.plan_id).success)
            self.assertIs(self.operation.contexts[-1].disclosure, disclosure)

    def test_metadata_cannot_upgrade_start_or_advance_permission(self):
        _, approval = self.grant(ResearchDisclosure.LOCAL_ONLY)
        started = self.authored(
            self.execution,
            approval.authorization_id,
            disclosure="remote_permitted",
            research_disclosure="remote_permitted",
        )
        self.assertTrue(started.success)
        result = self.advance(
            self.execution,
            started.research_plan_execution.plan_id,
            disclosure="remote_permitted",
            research_disclosure="remote_permitted",
        )
        self.assertTrue(result.success)
        self.assertIs(
            self.operation.contexts[-1].disclosure, ResearchDisclosure.LOCAL_ONLY
        )

    def test_no_consumer_does_not_create_permission_from_metadata(self):
        execution = self.service(approved=False)
        started = self.authored(execution, "invented", disclosure="remote_permitted")
        self.assertTrue(started.success)
        self.assertTrue(
            self.advance(execution, started.research_plan_execution.plan_id).success
        )
        self.assertIs(self.operation.contexts[-1].disclosure, ResearchDisclosure.NONE)

    def test_refused_approval_produces_no_context_or_operation(self):
        result = self.authored(self.execution, "unknown", disclosure="remote_permitted")
        self.assertFalse(result.success)
        self.assertEqual(self.execution._contexts, {})
        self.assertEqual(self.operation.contexts, [])

    def test_restart_rebind_does_not_restore_unrecorded_disclosure(self):
        plan, approval = self.grant(ResearchDisclosure.REMOTE_PERMITTED)
        state = self.execution.start_for_plan(
            plan, self.run_id, approval.authorization_id
        )
        self.assertIs(
            self.execution._contexts[state.plan_id].disclosure,
            ResearchDisclosure.REMOTE_PERMITTED,
        )
        restored = self.service()
        rebound = restored.rebind_restored(plan, self.run_id, state.plan_id)
        self.assertEqual(rebound.plan_id, state.plan_id)
        self.assertTrue(
            self.advance(restored, state.plan_id, disclosure="remote_permitted").success
        )
        self.assertIs(self.operation.contexts[-1].disclosure, ResearchDisclosure.NONE)

    def test_continuation_carries_permission_to_each_operation(self):
        self.steps = self.steps + (
            replace(self.steps[0], instruction="Another local check"),
        )
        plan, approval = self.grant(ResearchDisclosure.LOCAL_ONLY)
        state = self.execution.start_for_plan(
            plan, self.run_id, approval.authorization_id
        )
        response = self.execution.process_continue(
            BrainRequest(
                message="Continue",
                metadata={
                    "research_plan_id": state.plan_id,
                    "max_steps": "2",
                    "disclosure": "remote_permitted",
                },
            )
        )
        self.assertTrue(response.success)
        self.assertEqual(len(self.operation.contexts), 2)
        self.assertTrue(
            all(
                c.disclosure is ResearchDisclosure.LOCAL_ONLY
                for c in self.operation.contexts
            )
        )


if __name__ == "__main__":
    unittest.main()
