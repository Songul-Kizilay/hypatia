"""Partial North Star: one goal action reaches discovery, not a complete answer.

Real Brain/controller, authorization, execution, local search and JSON stores;
only external discovery/fetch are fakes. No caller-side Continue or Advance.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from brain.Brain import Brain
from brain.BrainRequest import BrainRequest
from cognition.CognitiveEngine import CognitiveEngine
from cognition.ResearchGoalStartApplicationService import OPENING_SCOPE
from core.CancellationSignal import CancellationSignal
from core.Exceptions import ResearchError
from core.ExclusiveStoreOwnership import release_all
from desktop.DesktopController import DesktopController
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.MemoryManager import MemoryManager
from planner.Planner import Planner
from research.JsonFileResearchExecutionStore import JsonFileResearchExecutionStore
from research.JsonFileResearchPlanAuthorizationStore import (
    JsonFileResearchPlanAuthorizationStore,
)
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchAutonomyResult import AutonomyStopReason
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSourceCandidate import ResearchSourceCandidate
from response.ResponseComposer import ResponseComposer
from session.SessionManager import SessionManager
from session.SessionRenameTransactionService import SessionRenameTransactionService

QUESTION = "Research indirect prompt injection defenses."


class ResearchGoalOpeningTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.addCleanup(release_all)
        self.root = Path(temporary.name)
        self.events = EventBus()
        self.memory = MemoryManager(self.events)
        self.sessions = SessionManager(self.events)
        self.knowledge = KnowledgeEngine()
        self.manager = ResearchRunManager(
            JsonFileResearchRunStore(self.root / "runs.json")
        )
        self.provider = Mock(provider_name="fixture")
        self.provider.discover.return_value = [
            ResearchSourceCandidate(
                url="https://example.org/defenses",
                title="Unverified defense study",
                snippet="A candidate, not evidence.",
            )
        ]
        self.fetcher = Mock()
        self.store = JsonFileResearchExecutionStore(self.root / "executions.json")
        self.approval_store = JsonFileResearchPlanAuthorizationStore(
            self.root / "approvals.json"
        )
        self.engine = self.make_engine()
        self.brain = Brain(self.engine, self.memory, self.events)
        self.controller = DesktopController(self.brain)

    def make_engine(self, approvals=True):
        return CognitiveEngine(
            self.knowledge,
            self.memory,
            Planner(),
            self.events,
            ResponseComposer(),
            self.sessions,
            SessionRenameTransactionService(
                session_manager=self.sessions,
                memory_manager=self.memory,
                event_bus=self.events,
            ),
            research_run_manager=self.manager,
            research_source_discovery_provider=self.provider,
            research_source_discovery_providers={
                ResearchDiscoveryProviderName.CROSSREF: self.provider
            },
            research_source_fetcher=self.fetcher,
            plan_authorization_store=self.approval_store if approvals else None,
            research_execution_store=self.store,
        )

    def request(self, **changes):
        metadata = {
            "intent": "research_goal_start",
            "research_goal_scope": OPENING_SCOPE,
            "discovery_provider": "crossref",
            "research_autonomy_budget": ResearchAutonomyBudget(),
        }
        metadata.update(changes)
        return BrainRequest(message=QUESTION, metadata=metadata)

    def test_north_star_opening_one_call_no_manual_continuation(self):
        response = self.controller.start_research_goal(
            QUESTION, "crossref", ResearchAutonomyBudget()
        )
        self.assertTrue(response.success)
        self.provider.discover.assert_called_once_with(QUESTION, limit=5)
        self.fetcher.fetch.assert_not_called()
        self.assertEqual(response.research_autonomy.steps_attempted, 2)
        state = response.research_plan_execution
        self.assertEqual(
            [s.status.value for s in state.steps], ["completed", "completed"]
        )
        run = response.research_runs[0]
        self.assertEqual(run.question, QUESTION)
        self.assertEqual(len(run.discoveries), 1)
        self.assertEqual((run.sources, run.evidence, run.claims), ((), (), ()))
        self.assertEqual(run.status.value, "collecting")
        self.assertIn("Research incomplete", response.message)
        self.assertIn("not evaluated, not proven absent", response.message)
        approval = self.engine._plan_authorization_service.authorization_for_execution(
            state.plan_id
        )
        self.assertTrue(approval.is_consumed)
        self.assertEqual(
            approval.capabilities,
            frozenset(
                {
                    ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH,
                    ResearchPlanStepCapability.SOURCE_DISCOVERY,
                }
            ),
        )
        self.assertEqual(self.store.load()[0].allowance.spend.network_operations, 1)

    def test_unknown_scope_capability_or_authored_plan_cannot_be_smuggled(self):
        for extra in (
            {"research_goal_scope": "all"},
            {"research_plan_steps": ()},
            {"target_binding": "target"},
            {"discovery_provider": "shell"},
            {"discovery_provider": "nvd"},
            {"research_disclosure": "remote_permitted"},
        ):
            self.assertFalse(self.brain.process(self.request(**extra)).success)
        self.provider.discover.assert_not_called()
        self.assertFalse((self.root / "runs.json").exists())

    def test_no_implicit_budget_or_model_grant(self):
        for budget in (
            None,
            {},
            ResearchAutonomyBudget(max_llm_operations=1),
            ResearchAutonomyBudget(max_network_operations=0),
            ResearchAutonomyBudget(max_step_advances=1),
        ):
            self.assertFalse(
                self.brain.process(
                    self.request(research_autonomy_budget=budget)
                ).success
            )
        self.provider.discover.assert_not_called()

    def test_nonfinite_wall_clock_budgets_are_invalid(self):
        for value in (float("nan"), float("inf"), float("-inf"), 10**1000):
            with self.assertRaises(ResearchError):
                ResearchAutonomyBudget(max_seconds=value)

    def test_zero_time_budget_stops_without_discovery(self):
        result = self.brain.process(
            self.request(research_autonomy_budget=ResearchAutonomyBudget(max_seconds=0))
        )
        self.assertEqual(
            result.research_autonomy.stop_reason,
            AutonomyStopReason.TIME_BUDGET_EXHAUSTED,
        )
        self.provider.discover.assert_not_called()
        self.assertIn("Research incomplete", result.message)

    def test_cancel_before_start_has_no_writes(self):
        signal = CancellationSignal()
        signal.cancel()
        response = self.controller.start_research_goal(
            QUESTION, "crossref", ResearchAutonomyBudget(), cancellation_token=signal
        )
        self.assertFalse(response.success)
        self.provider.discover.assert_not_called()
        self.assertFalse((self.root / "runs.json").exists())

    def test_cancel_during_discovery_does_not_record_candidates_or_fetch(self):
        signal = CancellationSignal()

        def cancel(*args, **kwargs):
            signal.cancel()
            return self.provider.discover.return_value

        self.provider.discover.side_effect = cancel
        response = self.controller.start_research_goal(
            QUESTION, "crossref", ResearchAutonomyBudget(), cancellation_token=signal
        )
        self.assertEqual(
            response.research_autonomy.stop_reason, AutonomyStopReason.CANCELLED
        )
        self.assertEqual(response.research_runs[0].discoveries, ())
        self.fetcher.fetch.assert_not_called()

    def test_duplicate_request_stops_without_repeated_query(self):
        request = self.request()
        self.brain.process(request)
        self.assertFalse(self.brain.process(request).success)
        self.provider.discover.assert_called_once()

    def test_no_durable_approval_means_no_goal_execution(self):
        response = self.make_engine(approvals=False).process(self.request())
        self.assertFalse(response.success)
        self.provider.discover.assert_not_called()

    def test_zero_results_are_reported_not_retried_or_called_complete(self):
        self.provider.discover.return_value = []
        response = self.brain.process(self.request())
        self.assertIn("0 unaccepted candidate(s)", response.message)
        self.assertIn("Research incomplete", response.message)
        self.provider.discover.assert_called_once()

    def test_failed_discovery_is_recorded_and_never_retried(self):
        self.provider.discover.side_effect = ResearchError("Provider unavailable")
        response = self.brain.process(self.request())
        self.assertEqual(
            response.research_autonomy.stop_reason, AutonomyStopReason.STEP_FAILED
        )
        self.assertEqual(len(response.research_runs[0].failures), 1)
        self.provider.discover.assert_called_once()

    def test_restart_preserves_audit_without_automatic_replay(self):
        response = self.brain.process(self.request())
        self.manager.load()
        self.make_engine()
        self.assertEqual(
            self.manager.get(response.research_runs[0].run_id).discoveries,
            response.research_runs[0].discoveries,
        )
        self.provider.discover.assert_called_once()
        self.assertEqual(len(self.store.load()), 1)

    def test_refused_advance_stops_loop_immediately(self):
        executor = self.engine._research_plan_execution_service
        with patch.object(executor, "process_advance", return_value=Mock()) as advance:
            response = self.brain.process(self.request())
        advance.assert_called_once()
        self.assertEqual(
            response.research_autonomy.stop_reason, AutonomyStopReason.ADVANCE_REFUSED
        )
        self.provider.discover.assert_not_called()

    def test_plain_question_does_not_grant_external_authority(self):
        self.brain.process(QUESTION)
        self.provider.discover.assert_not_called()
