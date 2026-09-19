"""One explicitly approved revalidation, end to end through approval and execution.

Revalidation is execution authority, not freshness inference: an old
observation is never permission to fetch again.  These tests drive the real
approval store, execution service, durable execution snapshot, run manager and
acceptance transaction with a deterministic fetcher.  Nothing here reaches a
network, a model or a scheduler.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from brain.BrainRequest import BrainRequest
from cognition.ResearchPlanAuthorizationApplicationService import (
    ResearchPlanAuthorizationApplicationService,
)
from cognition.ResearchPlanExecutionApplicationService import (
    RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT,
    ResearchPlanExecutionApplicationService,
    ResearchPlanExecutionStartRefusal,
)
from cognition.ResearchSourceAcceptanceService import ResearchSourceAcceptanceService
from core.Exceptions import ResearchError
from knowledge.KnowledgeEngine import KnowledgeEngine
from research.JsonFileResearchExecutionStore import JsonFileResearchExecutionStore
from research.JsonFileResearchPlanAuthorizationStore import (
    JsonFileResearchPlanAuthorizationStore,
)
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchAttemptResolution import ResearchAttemptResolution
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchCapabilityCost import cost_for
from research.ResearchPlan import ResearchPlan
from research.ResearchPlanDigest import plan_digest
from research.ResearchPlanExecutionStatus import ResearchPlanExecutionStatus
from research.ResearchPlanOperationRegistry import ResearchPlanOperationRegistry
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepCapability import ResearchPlanStepCapability as Cap
from research.ResearchPlanStepStatus import ResearchPlanStepStatus
from research.ResearchRunManager import ResearchRunManager
from research.ResearchRunMarkdownRenderer import render_research_run_markdown
from research.ResearchSource import ResearchSource
from research.ResearchSourceRevalidationOutcome import ResearchSourceRevalidationOutcome
from research.SourceRevalidationStepBinding import SourceRevalidationStepBinding
from research.SourceRevalidationStepOperation import SourceRevalidationStepOperation
from response.ResponseComposer import ResponseComposer

QUESTION = "What does the advisory say now?"
REQUESTED_URL = "https://example.test/advisory"
FINAL_URL = "https://cdn.example.test/advisory.txt"
NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
EARLIER = NOW - timedelta(days=2)
LATER = NOW - timedelta(days=1)


class Crash(BaseException):
    """A process dying mid-call, which no ``except ResearchError`` catches."""


class Fetcher:
    def __init__(self, content: str = "Version two.", crash: bool = False) -> None:
        self.content = content
        self.crash = crash
        self.urls: list[str] = []

    def fetch(self, url: str) -> ResearchSource:
        self.urls.append(url)
        if self.crash:
            raise Crash()
        return ResearchSource(
            url=FINAL_URL,
            title="Advisory",
            content=self.content,
            content_type="text/plain",
            fetched_at=LATER,
        )


class ContentStore:
    def __init__(self) -> None:
        self.records: list[object] = []

    def load(self) -> list[object]:
        return list(self.records)

    def save(self, records: list[object]) -> None:
        self.records = list(records)


class CrashAfterAcceptance:
    """Commit the real acceptance durably, then die before the step completes."""

    def __init__(self, inner: ResearchSourceAcceptanceService) -> None:
        self.inner = inner

    def accept(self, source, run_id="", attempt_id="", **kwargs):  # type: ignore[no-untyped-def]
        self.inner.accept(source, run_id, attempt_id, **kwargs)
        raise Crash()


class BoundedSourceRevalidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.observation_ids = iter(f"observation-{n}" for n in range(1, 50))
        self.revalidation_ids = iter(f"revalidation-{n}" for n in range(1, 50))
        self.manager = self._manager()
        self.manager.load()
        self.knowledge = KnowledgeEngine()
        self.content = ContentStore()
        self.run_id = self.manager.create(QUESTION).run_id
        accepted = self._acceptance().accept(
            ResearchSource(
                url=FINAL_URL,
                title="Advisory",
                content="Version one.",
                content_type="text/plain",
                fetched_at=EARLIER,
            ),
            self.run_id,
            requested_url=REQUESTED_URL,
        )
        assert accepted.accepted and accepted.document_id is not None
        self.prior_document_id = accepted.document_id
        self.approval_ids = iter(f"approval-{n}" for n in range(1, 50))
        self.approvals = ResearchPlanAuthorizationApplicationService(
            self.manager,
            ResponseComposer(),
            authorization_store=JsonFileResearchPlanAuthorizationStore(
                self.root / "authorizations.json"
            ),
            clock=lambda: NOW,
            id_factory=lambda: next(self.approval_ids),
        )
        self.execution_store = JsonFileResearchExecutionStore(
            self.root / "executions.json"
        )

    def _manager(self) -> ResearchRunManager:
        return ResearchRunManager(
            JsonFileResearchRunStore(self.root / "runs.json"),
            clock=lambda: NOW,
            observation_id_factory=lambda: next(self.observation_ids),
            revalidation_id_factory=lambda: next(self.revalidation_ids),
        )

    def _acceptance(
        self, manager: ResearchRunManager | None = None
    ) -> ResearchSourceAcceptanceService:
        return ResearchSourceAcceptanceService(
            self.knowledge,
            manager or self.manager,
            self.content,  # type: ignore[arg-type]
        )

    def _plan(
        self,
        prior_observation_id: str = "observation-1",
        *,
        plan_id: str = "execution-1",
        max_sources: int = 2,
        capability: Cap = Cap.SOURCE_REVALIDATION,
    ) -> ResearchPlan:
        if capability is Cap.SOURCE_REVALIDATION:
            step = ResearchPlanStep(
                "step-1",
                "Re-fetch the exact recorded advisory observation once.",
                capability=capability,
                source_revalidation_binding=SourceRevalidationStepBinding(
                    self.run_id, prior_observation_id, REQUESTED_URL, max_sources
                ),
            )
        else:
            step = ResearchPlanStep(
                "step-1",
                "Fetch the advisory.",
                capability=capability,
                authorized_source_url=REQUESTED_URL,
            )
        return ResearchPlan(plan_id, QUESTION, (step,), NOW)

    def _execution(
        self,
        fetcher: Fetcher,
        *,
        manager: ResearchRunManager | None = None,
        acceptance: object | None = None,
    ) -> ResearchPlanExecutionApplicationService:
        manager = manager or self.manager
        registry = ResearchPlanOperationRegistry()
        registry.register(
            Cap.SOURCE_REVALIDATION,
            SourceRevalidationStepOperation(
                fetcher,  # type: ignore[arg-type]
                acceptance or self._acceptance(manager),  # type: ignore[arg-type]
                manager,
            ),
        )
        return ResearchPlanExecutionApplicationService(
            ResponseComposer(),
            operation_registry=registry,
            execution_store=self.execution_store,
            authorization_consumer=self.approvals,
            clock=lambda: NOW,
        )

    def _started(
        self,
        execution: ResearchPlanExecutionApplicationService,
        plan: ResearchPlan | None = None,
        budget: ResearchAutonomyBudget | None = None,
    ) -> str:
        plan = plan or self._plan()
        approval = self.approvals.record_for_plan(plan, self.run_id, budget=budget)
        assert approval is not None
        started = execution.start_for_plan(plan, self.run_id, approval.authorization_id)
        assert not isinstance(started, ResearchPlanExecutionStartRefusal), started
        return plan.plan_id

    @staticmethod
    def _advance(execution: ResearchPlanExecutionApplicationService, plan_id: str):  # type: ignore[no-untyped-def]
        return execution.process_advance(
            BrainRequest(
                message="Advance",
                metadata={
                    "intent": RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT,
                    "research_plan_id": plan_id,
                },
            )
        )

    def _restarted(self, fetcher: Fetcher):  # type: ignore[no-untyped-def]
        manager = self._manager()
        manager.load()
        return manager, self._execution(fetcher, manager=manager)

    def test_approved_revalidation_adds_one_observation_and_one_relation(
        self,
    ) -> None:
        fetcher = Fetcher()
        execution = self._execution(fetcher)
        plan_id = self._started(execution)
        before = execution.allowance(plan_id)
        assert before is not None
        prior = self.manager.get(self.run_id).sources[0]

        response = self._advance(execution, plan_id)

        self.assertTrue(response.success, response.message)
        self.assertEqual(fetcher.urls, [REQUESTED_URL])
        run = self.manager.get(self.run_id)
        self.assertEqual(run.sources[0], prior)
        later = run.sources[1]
        self.assertEqual(later.observation_id, "observation-2")
        self.assertEqual(later.revalidation_of_observation_id, "observation-1")
        self.assertEqual(later.revalidation_execution_id, plan_id)
        self.assertEqual(later.requested_url, REQUESTED_URL)
        self.assertEqual(later.url, FINAL_URL)
        self.assertNotEqual(later.document_id, prior.document_id)
        (relation,) = self.manager.source_revalidations()
        self.assertEqual(
            relation.record.outcome, ResearchSourceRevalidationOutcome.CONTENT_CHANGED
        )
        # One normal attempt: one advance and one network operation, charged
        # against the ordinary cumulative allowance and nothing else.
        after = execution.allowance(plan_id)
        assert after is not None
        cost = cost_for(Cap.SOURCE_REVALIDATION)
        self.assertEqual(cost.network_operations, 1)
        self.assertEqual(
            after.remaining_network_operations,
            before.remaining_network_operations - 1,
        )
        self.assertEqual(
            after.remaining_step_advances, before.remaining_step_advances - 1
        )
        state = execution.live_execution(plan_id)
        assert state is not None
        self.assertIs(state.status, ResearchPlanExecutionStatus.COMPLETED)
        self.assertIn("observation-1", state.steps[0].detail)
        self.assertIn("observation-2", state.steps[0].detail)
        self.assertIn("content_changed", state.steps[0].detail)

    def test_unchanged_content_is_a_new_observation_of_the_same_version(
        self,
    ) -> None:
        execution = self._execution(Fetcher("Version one."))
        plan_id = self._started(execution)

        self.assertTrue(self._advance(execution, plan_id).success)

        run = self.manager.get(self.run_id)
        self.assertEqual(len(run.sources), 2)
        self.assertEqual(run.sources[1].document_id, self.prior_document_id)
        self.assertNotEqual(
            run.sources[1].observation_id, run.sources[0].observation_id
        )
        (relation,) = self.manager.source_revalidations()
        self.assertEqual(
            relation.record.outcome,
            ResearchSourceRevalidationOutcome.CONTENT_UNCHANGED,
        )
        # The durable record survives a restart and still validates.
        restored = self._manager()
        restored.load()
        self.assertEqual(restored.get(self.run_id), run)
        self.assertEqual(
            restored.get(self.run_id).source_for_document(self.prior_document_id),
            run.sources[0],
        )
        exported = render_research_run_markdown(run)
        self.assertIn(
            "**Explicit revalidation of observation:** observation-1", exported
        )
        self.assertIn("not a freshness conclusion", exported)

    def test_temporal_history_observes_the_explicit_edge_without_freshness(
        self,
    ) -> None:
        execution = self._execution(Fetcher())
        self.assertTrue(self._advance(execution, self._started(execution)).success)

        history = self.manager.temporal_history(REQUESTED_URL, run_id=self.run_id)

        self.assertEqual(history.observation_ids, ("observation-1", "observation-2"))
        (edge,) = history.relations
        self.assertEqual(
            (edge.earlier_observation_id, edge.later_observation_id),
            ("observation-1", "observation-2"),
        )
        self.assertEqual(history.shape.value, "linear")
        rendered = repr(history).casefold()
        for word in ("fresh", "stale", "current", "outdated"):
            self.assertNotIn(word, rendered)

    def test_a_source_fetch_approval_cannot_start_a_revalidation(self) -> None:
        fetcher = Fetcher()
        execution = self._execution(fetcher)
        fetch_plan = self._plan(capability=Cap.SOURCE_FETCH)
        approval = self.approvals.record_for_plan(fetch_plan, self.run_id)
        assert approval is not None

        started = execution.start_for_plan(
            self._plan(), self.run_id, approval.authorization_id
        )

        self.assertIsInstance(started, ResearchPlanExecutionStartRefusal)
        self.assertEqual(fetcher.urls, [])
        self.assertEqual(self.manager.source_revalidations(), [])

    def test_a_revalidation_for_another_run_cannot_be_approved(self) -> None:
        other_run = self.manager.create("Another question?").run_id

        with self.assertRaisesRegex(ResearchError, "bound run"):
            self.approvals.record_for_plan(self._plan(), other_run)

    def test_a_budget_without_a_network_operation_is_not_approved(self) -> None:
        with self.assertRaisesRegex(ResearchError, "budget"):
            self.approvals.record_for_plan(
                self._plan(),
                self.run_id,
                budget=ResearchAutonomyBudget(max_network_operations=0),
            )

    def test_an_exhausted_cumulative_allowance_refuses_before_fetching(
        self,
    ) -> None:
        fetcher = Fetcher()
        execution = self._execution(fetcher)
        plan_id = self._started(execution)
        allowance = execution.allowance(plan_id)
        assert allowance is not None
        cost = cost_for(Cap.SOURCE_REVALIDATION)
        while allowance.affords(cost):
            allowance = allowance.charged(cost)
        execution._allowances[plan_id] = allowance

        response = self._advance(execution, plan_id)

        self.assertFalse(response.success)
        self.assertEqual(fetcher.urls, [])
        self.assertEqual(len(self.manager.get(self.run_id).sources), 1)
        self.assertEqual(execution.allowance(plan_id), allowance)

    def test_revalidation_has_no_implicit_budget_without_an_allowance(self) -> None:
        fetcher = Fetcher()
        execution = self._execution(fetcher)
        plan_id = self._started(execution)
        execution._allowances.pop(plan_id)

        response = self._advance(execution, plan_id)

        self.assertFalse(response.success)
        self.assertIn("allowance", response.message)
        self.assertEqual(fetcher.urls, [])

    def test_a_full_normal_source_limit_refuses_before_fetching(self) -> None:
        fetcher = Fetcher()
        execution = self._execution(fetcher)
        plan_id = self._started(execution, self._plan(max_sources=1))

        self._advance(execution, plan_id)

        self.assertEqual(fetcher.urls, [])
        self.assertEqual(len(self.manager.get(self.run_id).sources), 1)
        self.assertEqual(self.manager.source_revalidations(), [])

    def test_restart_after_the_durable_commit_completes_without_refetching(
        self,
    ) -> None:
        crashing = self._execution(
            Fetcher(), acceptance=CrashAfterAcceptance(self._acceptance())
        )
        plan_id = self._started(crashing)
        with self.assertRaises(Crash):
            self._advance(crashing, plan_id)
        charged = crashing.allowance(plan_id)
        self.assertEqual(len(self.manager.get(self.run_id).sources), 2)

        refetcher = Fetcher()
        manager, execution = self._restarted(refetcher)
        state = execution.rebind_restored(self._plan(), self.run_id, plan_id)

        assert not isinstance(state, ResearchPlanExecutionStartRefusal), state
        self.assertIs(state.status, ResearchPlanExecutionStatus.COMPLETED)
        self.assertIs(state.steps[0].status, ResearchPlanStepStatus.COMPLETED)
        self.assertTrue(state.steps[0].work_performed)
        self.assertIn("No second fetch", state.steps[0].detail)
        self.assertEqual(refetcher.urls, [])
        self.assertEqual(len(manager.get(self.run_id).sources), 2)
        self.assertEqual(len(manager.source_revalidations()), 1)
        self.assertEqual(execution.allowance(plan_id), charged)
        # The reconciliation is durable: another restart restores it completed.
        _, again = self._restarted(Fetcher())
        restored = again.restored_execution(plan_id)
        assert restored is not None
        self.assertIs(restored.status, ResearchPlanExecutionStatus.COMPLETED)

    def test_an_ambiguous_interrupted_fetch_is_never_retried_automatically(
        self,
    ) -> None:
        crashing = self._execution(Fetcher(crash=True))
        plan_id = self._started(crashing)
        with self.assertRaises(Crash):
            self._advance(crashing, plan_id)

        refetcher = Fetcher()
        manager, execution = self._restarted(refetcher)
        state = execution.rebind_restored(self._plan(), self.run_id, plan_id)
        assert not isinstance(state, ResearchPlanExecutionStartRefusal), state
        self.assertIs(state.steps[0].status, ResearchPlanStepStatus.INTERRUPTED)

        refused = self._advance(execution, plan_id)

        self.assertFalse(refused.success)
        self.assertEqual(refetcher.urls, [])
        self.assertEqual(len(manager.get(self.run_id).sources), 1)
        self.assertEqual(manager.source_revalidations(), [])

    def test_only_an_operator_not_performed_ruling_permits_a_new_attempt(
        self,
    ) -> None:
        crashing = self._execution(Fetcher(crash=True))
        plan_id = self._started(crashing)
        with self.assertRaises(Crash):
            self._advance(crashing, plan_id)
        refetcher = Fetcher()
        manager, execution = self._restarted(refetcher)
        execution.rebind_restored(self._plan(), self.run_id, plan_id)
        ruled = execution.process_resolve(
            BrainRequest(
                message="Resolve",
                metadata={
                    "intent": "research_plan_execution_resolve",
                    "research_plan_id": plan_id,
                    "step_id": "step-1",
                    "resolution": ResearchAttemptResolution.NOT_PERFORMED.value,
                },
            )
        )
        self.assertTrue(ruled.success, ruled.message)

        self.assertTrue(self._advance(execution, plan_id).success)

        self.assertEqual(refetcher.urls, [REQUESTED_URL])
        self.assertEqual(len(manager.source_revalidations()), 1)

    def test_restart_cannot_rebind_a_different_prior_observation(self) -> None:
        crashing = self._execution(Fetcher(crash=True))
        plan_id = self._started(crashing)
        with self.assertRaises(Crash):
            self._advance(crashing, plan_id)
        self.manager.add_source(
            self.run_id,
            ResearchSource(
                url=FINAL_URL,
                title="Other",
                content="Another page.",
                content_type="text/plain",
                fetched_at=EARLIER,
            ),
            "document-other",
            requested_url=REQUESTED_URL,
        )

        _, execution = self._restarted(Fetcher())
        substituted = execution.rebind_restored(
            self._plan("observation-2"), self.run_id, plan_id
        )

        self.assertIsInstance(substituted, ResearchPlanExecutionStartRefusal)
        snapshot = execution.restored_execution(plan_id)
        assert snapshot is not None
        self.assertEqual(snapshot.revalidation_plan_digest, plan_digest(self._plan()))

    def test_a_different_execution_never_claims_a_recorded_revalidation(
        self,
    ) -> None:
        first = self._execution(Fetcher())
        self.assertTrue(self._advance(first, self._started(first)).success)
        fetcher = Fetcher()
        second = self._execution(fetcher)
        plan_id = self._started(
            second, self._plan(plan_id="execution-2", max_sources=3)
        )

        response = self._advance(second, plan_id)

        state = second.live_execution(plan_id)
        assert state is not None
        self.assertIsNot(state.steps[0].status, ResearchPlanStepStatus.COMPLETED)
        self.assertIn("never fetched again", state.steps[0].detail)
        self.assertEqual(fetcher.urls, [])
        self.assertEqual(len(self.manager.source_revalidations()), 1)
        self.assertFalse(response.research_source_previews)

    def test_a_plan_cannot_revalidate_the_same_prior_twice(self) -> None:
        step = self._plan().steps[0]
        with self.assertRaisesRegex(ResearchError, "distinct prior"):
            ResearchPlan(
                "execution-1",
                QUESTION,
                (step, replace(step, step_id="step-2")),
                NOW,
            )


if __name__ == "__main__":
    unittest.main()
