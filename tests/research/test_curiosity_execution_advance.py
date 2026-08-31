"""The first real research operation Hypatia performs on its own suggestion.

Everything before this described work. Start consumed an approval and created a
RUNNING execution with every step still pending, which is the point the previous
milestone deliberately stopped at. Advancing is where the chain finally does
something — one authorized discovery step, because a person pressed a button.

So the tests are mostly about the word "one". A single advance attempts a single
step and stops; it does not continue to the next, does not retry a failure, and
does not become a loop because the outcome was disappointing. The step it
attempts is the next pending one in authored order, and the capability it uses is
the one the approval already named.

The budget is the other half. It is the budget attached to the consumed
approval, it is checked before the attempt so an exhausted allowance never
reaches a provider, and it is charged at the attempt boundary whether or not the
operation goes on to succeed — because an attempt that failed still used the
thing it was allowed to use.

Nothing here reaches a network. The provider is a fake that records what it was
asked to do, which is how the tests can say what did *not* happen.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from brain.BrainRequest import BrainRequest
from cognition.CuriosityApplicationService import (
    CURIOSITY_AUTHORIZE_PROPOSAL_INTENT,
    CURIOSITY_PREPARE_PROPOSAL_INTENT,
    CURIOSITY_START_AUTHORIZED_PROPOSAL_INTENT,
    CuriosityApplicationService,
)
from cognition.ResearchPlanAuthorizationApplicationService import (
    ResearchPlanAuthorizationApplicationService,
)
from cognition.ResearchPlanExecutionApplicationService import (
    RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT,
    RESEARCH_PLAN_EXECUTION_CANCEL_INTENT,
    ResearchPlanExecutionApplicationService,
)
from core.Exceptions import ResearchError
from knowledge.Chunk import Chunk
from research.JsonFileResearchPlanAuthorizationStore import (
    JsonFileResearchPlanAuthorizationStore,
)
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchCapabilityCost import cost_for
from research.ResearchExecutionAllowance import ResearchExecutionAllowance
from research.ResearchHypothesis import ResearchHypothesis
from research.ResearchKnowledgeGapKind import ResearchKnowledgeGapKind
from research.ResearchPlanDraftService import ResearchPlanDraftService
from research.ResearchPlanExecutionStatus import ResearchPlanExecutionStatus
from research.ResearchPlanOperationRegistry import ResearchPlanOperationRegistry
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchPlanStepOperationResult import ResearchPlanStepOperationResult
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSource import ResearchSource
from response.ResponseComposer import ResponseComposer

PAST = datetime.now(UTC) - timedelta(days=1)
NOW = PAST + timedelta(hours=1)
QUESTION = "Can the middleware authorization check be bypassed?"
STATEMENT = "Authorization middleware can be bypassed before route handling."
TEST = "Observe whether a protected route is reached without authorization."

HYPOTHESIS_GAP = ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP


class RecordingDiscoveryOperation:
    """A discovery step that records being asked instead of asking anyone."""

    operation_name = "fake_source_discovery"

    def __init__(self, *, fails: bool = False) -> None:
        self.calls: list[str] = []
        self.contexts: list[object] = []
        self._fails = fails

    def run(self, step, context) -> ResearchPlanStepOperationResult:
        self.calls.append(step.step_id)
        self.contexts.append(context)
        if self._fails:
            raise ResearchError("The provider refused this discovery.")
        return ResearchPlanStepOperationResult(
            performed=True, detail="Candidates recorded.", succeeded=True
        )


class StubHypothesisStore:
    def __init__(self, hypotheses: list[ResearchHypothesis]) -> None:
        self.hypotheses = hypotheses

    def load(self) -> list[ResearchHypothesis]:
        return list(self.hypotheses)

    def save(self, hypotheses: list[ResearchHypothesis]) -> None:
        raise AssertionError("Advancing must never write a hypothesis.")


class AdvanceFixture(unittest.TestCase):
    """The whole chain, ending in one operator-triggered discovery attempt."""

    fails = False

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.manager = ResearchRunManager(
            JsonFileResearchRunStore(self.root / "runs.json")
        )
        self.run_id = self.manager.create(QUESTION).run_id
        self.evidence_id = self._evidence()
        self.hypothesis = ResearchHypothesis(
            hypothesis_id="hypothesis-1",
            run_id=self.run_id,
            statement=STATEMENT,
            discriminating_test=TEST,
            created_at=PAST,
            updated_at=PAST,
        )
        self.hypothesis_store = StubHypothesisStore([self.hypothesis])
        self.authorization_service = ResearchPlanAuthorizationApplicationService(
            self.manager,
            ResponseComposer(),
            authorization_store=JsonFileResearchPlanAuthorizationStore(
                self.root / "authorizations.json"
            ),
            clock=lambda: NOW,
        )
        self.operation = RecordingDiscoveryOperation(fails=self.fails)
        registry = ResearchPlanOperationRegistry()
        registry.register(ResearchPlanStepCapability.SOURCE_DISCOVERY, self.operation)
        self.execution_service = ResearchPlanExecutionApplicationService(
            ResponseComposer(),
            operation_registry=registry,
            authorization_consumer=self.authorization_service,
            clock=lambda: NOW,
        )
        self.service = CuriosityApplicationService(
            self.manager,
            ResponseComposer(),
            hypothesis_store=self.hypothesis_store,
            authorization_service=self.authorization_service,
            execution_starter=self.execution_service,
            draft_service=ResearchPlanDraftService(
                id_factory=lambda: "plan-1", clock=lambda: NOW
            ),
            clock=lambda: NOW,
        )
        self.question = self._question()

    def _evidence(self) -> str:
        self.manager.add_source(
            self.run_id,
            ResearchSource(
                url="https://example.test/document",
                title="A source",
                content="An observation recorded during the run.",
                content_type="text/plain",
                fetched_at=PAST,
            ),
            "document-1",
        )
        run = self.manager.add_evidence(
            self.run_id,
            Chunk(
                document_id="document-1",
                index=0,
                content="An observation recorded during the run.",
                chunk_id="chunk-1",
            ),
            "A note.",
        )
        return run.evidence[-1].evidence_id

    def _request(self, intent: str, **metadata: str) -> BrainRequest:
        return BrainRequest(
            message="Curiosity", metadata={"intent": intent, **metadata}
        )

    def _question(self):
        self.service.process_question_store(
            self._request("curiosity_question_store", research_run_id=self.run_id)
        )
        [question] = [
            entry for entry in self.service.questions() if entry.kind is HYPOTHESIS_GAP
        ]
        return question

    def _started(self):
        """Run the whole chain up to RUNNING, and return the execution state."""
        self.service.process_question_accept(
            self._request(
                "curiosity_question_accept",
                curiosity_question_id=self.question.question_id,
            )
        )
        digest = self.service.process_prepare_proposal(
            self._request(
                CURIOSITY_PREPARE_PROPOSAL_INTENT,
                curiosity_question_id=self.question.question_id,
            )
        ).curiosity_proposal.digest
        authorization = self.service.process_authorize_proposal(
            self._request(
                CURIOSITY_AUTHORIZE_PROPOSAL_INTENT,
                curiosity_question_id=self.question.question_id,
                expected_plan_digest=digest,
            )
        ).research_plan_authorization
        started = self.service.process_start_authorized_proposal(
            self._request(
                CURIOSITY_START_AUTHORIZED_PROPOSAL_INTENT,
                curiosity_question_id=self.question.question_id,
                expected_plan_digest=digest,
                authorization_id=authorization.authorization_id,
            )
        ).research_plan_execution
        return started

    def _advance(self, execution_id: str):
        return self.execution_service.process_advance(
            BrainRequest(
                message="Advance",
                metadata={
                    "intent": RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT,
                    "research_plan_id": execution_id,
                },
            )
        )

    def _allowance(self, execution_id: str) -> ResearchExecutionAllowance:
        """Read the live allowance the start bound to this execution."""
        allowance = self.execution_service._allowances[execution_id]
        return allowance

    def _set_allowance(
        self,
        execution_id: str,
        allowance: ResearchExecutionAllowance,
    ) -> None:
        self.execution_service._allowances[execution_id] = allowance

    def _cancel(self, execution_id: str):
        return self.execution_service.process_cancel(
            BrainRequest(
                message="Cancel",
                metadata={
                    "intent": RESEARCH_PLAN_EXECUTION_CANCEL_INTENT,
                    "research_plan_id": execution_id,
                },
            )
        )


class ZeroStepBoundaryTests(AdvanceFixture):
    def test_the_whole_chain_before_advance_performs_no_step(self) -> None:
        """Accepting, previewing, approving and starting reach no provider."""
        started = self._started()

        self.assertIs(started.status, ResearchPlanExecutionStatus.RUNNING)
        self.assertEqual(started.completed_steps, 0)
        self.assertGreaterEqual(started.pending_steps, 1)
        self.assertEqual(self.operation.calls, [])

    def test_starting_does_not_advance_on_its_own(self) -> None:
        self._started()

        self.assertEqual(self.operation.calls, [])


class OneStepTests(AdvanceFixture):
    def test_one_advance_attempts_exactly_one_step(self) -> None:
        started = self._started()

        self._advance(started.plan_id)

        self.assertEqual(len(self.operation.calls), 1)

    def test_the_attempted_step_is_the_next_pending_one(self) -> None:
        started = self._started()
        expected = started.next_pending_step_id

        self._advance(started.plan_id)

        self.assertEqual(self.operation.calls, [expected])

    def test_a_second_step_is_never_reached_by_one_advance(self) -> None:
        """The invariant the whole milestone rests on."""
        started = self._started()

        response = self._advance(started.plan_id)

        state = response.research_plan_execution
        self.assertEqual(len(self.operation.calls), 1)
        self.assertEqual(state.completed_steps, 1)

    def test_a_successful_step_updates_the_state_truthfully(self) -> None:
        started = self._started()

        state = self._advance(started.plan_id).research_plan_execution

        self.assertEqual(state.plan_id, started.plan_id)
        self.assertEqual(state.completed_steps, 1)
        self.assertEqual(state.pending_steps, started.pending_steps - 1)

    def test_advancing_a_finished_plan_refuses_rather_than_looping(self) -> None:
        started = self._started()
        self._advance(started.plan_id)

        again = self._advance(started.plan_id)

        self.assertEqual(len(self.operation.calls), 1)
        self.assertIn("no pending step", again.message)

    def test_an_unknown_execution_is_refused(self) -> None:
        self._started()

        self._advance("execution-missing")

        self.assertEqual(self.operation.calls, [])

    def test_the_operation_sees_the_run_it_was_authorized_for(self) -> None:
        started = self._started()

        self._advance(started.plan_id)

        [context] = self.operation.contexts
        self.assertEqual(context.research_run_id, self.run_id)


class CapabilityAndBudgetTests(AdvanceFixture):
    def test_only_the_authorized_capability_is_executed(self) -> None:
        started = self._started()
        plan = self.execution_service.live_plan(started.plan_id)

        self._advance(started.plan_id)

        for step in plan.steps:
            with self.subTest(step=step.step_id):
                self.assertIs(
                    step.capability, ResearchPlanStepCapability.SOURCE_DISCOVERY
                )

    def test_the_allowance_is_the_budget_the_approval_carried(self) -> None:
        started = self._started()
        [authorization] = JsonFileResearchPlanAuthorizationStore(
            self.root / "authorizations.json"
        ).load()

        allowance = self._allowance(started.plan_id)

        self.assertEqual(allowance.budget, authorization.budget)

    def test_an_attempt_is_charged_against_the_allowance(self) -> None:
        started = self._started()
        before = self._allowance(started.plan_id)

        self._advance(started.plan_id)

        after = self._allowance(started.plan_id)
        self.assertLess(
            after.remaining_network_operations,
            before.remaining_network_operations,
        )

    def test_an_exhausted_allowance_stops_before_the_provider(self) -> None:
        """Refused at the boundary, so nothing is reached and nothing charged.

        Exhausted by charging the real cost through the real API until the
        allowance stops affording it, so the block is the one the architecture
        applies rather than a state invented for the test.
        """
        started = self._started()
        cost = cost_for(ResearchPlanStepCapability.SOURCE_DISCOVERY)
        allowance = self._allowance(started.plan_id)
        while allowance.affords(cost):
            allowance = allowance.charged(cost)
        self._set_allowance(started.plan_id, allowance)

        response = self._advance(started.plan_id)

        self.assertEqual(self.operation.calls, [])
        self.assertIn("budget", response.message.casefold())


class CancelTests(AdvanceFixture):
    def test_a_cancelled_execution_refuses_to_advance(self) -> None:
        started = self._started()
        self._cancel(started.plan_id)

        self._advance(started.plan_id)

        self.assertEqual(self.operation.calls, [])

    def test_cancel_remains_reachable_before_the_first_advance(self) -> None:
        started = self._started()

        cancelled = self._cancel(started.plan_id).research_plan_execution

        self.assertIs(cancelled.status, ResearchPlanExecutionStatus.CANCELLED)
        self.assertEqual(self.operation.calls, [])


class FailureTests(AdvanceFixture):
    fails = True

    def test_a_provider_failure_is_recorded_rather_than_raised(self) -> None:
        started = self._started()

        state = self._advance(started.plan_id).research_plan_execution

        self.assertIsNotNone(state)
        self.assertEqual(state.completed_steps, 0)

    def test_a_failure_is_not_retried_and_does_not_advance(self) -> None:
        """One attempt is one attempt, however it turned out."""
        started = self._started()

        self._advance(started.plan_id)

        self.assertEqual(len(self.operation.calls), 1)

    def test_a_failed_attempt_still_charged_the_allowance(self) -> None:
        started = self._started()
        before = self._allowance(started.plan_id)

        self._advance(started.plan_id)

        after = self._allowance(started.plan_id)
        self.assertLess(
            after.remaining_network_operations,
            before.remaining_network_operations,
        )

    def test_the_failed_step_is_not_left_running(self) -> None:
        """A refused attempt settles the step rather than abandoning it mid-flight."""
        started = self._started()

        state = self._advance(started.plan_id).research_plan_execution

        self.assertIsNone(state.running_step_id)
        self.assertEqual(state.completed_steps, 0)


class RestartTests(AdvanceFixture):
    def test_a_restored_execution_is_readable_but_not_advanceable(self) -> None:
        """Decision A, pinned: rebinding plan, context and allowance durably is
        its own milestone, so this limitation is recorded rather than removed."""
        started = self._started()

        reopened = ResearchPlanExecutionApplicationService(
            ResponseComposer(),
            operation_registry=ResearchPlanOperationRegistry(),
            authorization_consumer=self.authorization_service,
            clock=lambda: NOW,
        )

        self.assertIsNone(reopened.live_execution(started.plan_id))
        reopened.process_advance(
            BrainRequest(
                message="Advance",
                metadata={
                    "intent": RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT,
                    "research_plan_id": started.plan_id,
                },
            )
        )
        self.assertEqual(self.operation.calls, [])


if __name__ == "__main__":
    unittest.main()
