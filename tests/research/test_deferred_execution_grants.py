"""Security boundary and exact-binding proofs for deferred execution grants."""

from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from cognition.TrustedDeferredExecutionControlService import (
    TrustedDeferredExecutionControlService,
)
from core.Exceptions import ResearchError
from desktop.DesktopController import DesktopController
from desktop.TkinterDesktopWindow import TkinterDesktopWindow
from research.BackgroundResearchTask import BackgroundResearchTask
from research.BackgroundResearchTaskStatus import BackgroundResearchTaskStatus
from research.DeferredExecutionEligibility import deferred_execution_decision
from research.DeferredExecutionGrant import DeferredExecutionGrant
from research.DeferredGrantAuthorizer import DeferredGrantAuthorizer
from research.JsonFileDeferredExecutionGrantStore import (
    JsonFileDeferredExecutionGrantStore,
)
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchExecutionAllowance import ResearchExecutionAllowance
from research.ResearchExecutionSpend import ResearchExecutionSpend
from research.ResearchPlan import ResearchPlan
from research.ResearchPlanAuthorization import capabilities_of, restrictions_of
from research.ResearchPlanDigest import plan_digest
from research.ResearchPlanExecutionState import ResearchPlanExecutionState
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepCapability import ResearchPlanStepCapability

NOW = datetime(2026, 9, 2, tzinfo=UTC)


class MemoryGrantStore:
    def __init__(self) -> None:
        self.records: list[DeferredExecutionGrant] = []

    def load(self) -> list[DeferredExecutionGrant]:
        return list(self.records)

    def save(self, grants: list[DeferredExecutionGrant]) -> None:
        self.records = list(grants)


class Context:
    def __init__(self) -> None:
        self.plan = ResearchPlan(
            plan_id="execution-1",
            question="What is known?",
            steps=(
                ResearchPlanStep(
                    step_id="step-1",
                    instruction="Search local knowledge",
                    capability=ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH,
                ),
            ),
            created_at=NOW,
        )
        self.execution = ResearchPlanExecutionState.prepare(self.plan).start()
        self.allowance = ResearchExecutionAllowance(ResearchAutonomyBudget())
        self.task = BackgroundResearchTask(
            task_id="task-1",
            execution_id=self.plan.plan_id,
            budget=ResearchAutonomyBudget(max_step_advances=2),
            created_at=NOW,
            updated_at=NOW,
        )
        self.reads = 0

    def background_research_task(self, task_id: str):
        self.reads += 1
        return self.task if task_id == self.task.task_id else None

    def live_research_execution(self, execution_id: str):
        self.reads += 1
        return self.execution if execution_id == self.execution.plan_id else None

    def live_research_plan(self, execution_id: str):
        self.reads += 1
        return self.plan if execution_id == self.plan.plan_id else None

    def research_execution_allowance(self, execution_id: str):
        self.reads += 1
        return self.allowance if execution_id == self.plan.plan_id else None


def grant_for(context: Context, **changes) -> DeferredExecutionGrant:
    grant = DeferredExecutionGrant(
        grant_id="grant-1",
        task_id=context.task.task_id,
        execution_id=context.task.execution_id,
        plan_digest=plan_digest(context.plan),
        capabilities=capabilities_of(context.plan),
        # What the service records, so a hand-built grant behaves like a real
        # one; individual tests still override it through replace().
        approved_restrictions=restrictions_of(context.plan),
        task_budget=context.task.budget,
        granted_at=NOW,
        granted_by=DeferredGrantAuthorizer.TRUSTED_LOCAL_OPERATOR,
    )
    return replace(grant, **changes)


class TrustedControlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = Context()
        self.store = MemoryGrantStore()
        self.service = TrustedDeferredExecutionControlService(
            self.context,
            self.store,
            clock=lambda: NOW,
            id_factory=lambda: "grant-1",
        )

    def test_task_without_grant_is_manual_only(self) -> None:
        self.assertEqual(self.service.preview("task-1").decision.reason, "manual_only")

    def test_trusted_grant_binds_every_existing_authority_fact(self) -> None:
        view = self.service.grant("task-1")
        grant = view.grant
        assert grant is not None
        self.assertEqual(grant.task_id, "task-1")
        self.assertEqual(grant.execution_id, "execution-1")
        self.assertEqual(grant.plan_digest, plan_digest(self.context.plan))
        self.assertEqual(grant.capabilities, capabilities_of(self.context.plan))
        self.assertEqual(grant.task_budget, self.context.task.budget)
        self.assertEqual(
            grant.granted_by, DeferredGrantAuthorizer.TRUSTED_LOCAL_OPERATOR
        )
        self.assertTrue(view.decision.allowed)

    def test_grant_and_revoke_spend_no_execution_allowance(self) -> None:
        before = self.context.allowance
        self.service.grant("task-1")
        self.service.revoke("task-1")
        self.assertEqual(self.context.allowance, before)
        self.assertEqual(self.context.execution.status.value, "running")
        self.assertEqual(self.context.task.status, BackgroundResearchTaskStatus.PENDING)

    def test_revoke_keeps_task_and_execution_and_disables_deferred(self) -> None:
        self.service.grant("task-1")
        view = self.service.revoke("task-1")
        self.assertEqual(view.decision.reason, "manual_only")
        self.assertEqual(self.context.task.task_id, "task-1")
        self.assertEqual(self.context.execution.plan_id, "execution-1")

    def test_duplicate_grant_is_refused(self) -> None:
        self.service.grant("task-1")
        with self.assertRaises(ResearchError):
            self.service.grant("task-1")

    def test_unknown_task_has_no_latest_fallback(self) -> None:
        with self.assertRaises(ResearchError):
            self.service.grant("latest")

    def test_exhausted_allowance_cannot_be_granted(self) -> None:
        self.context.allowance = ResearchExecutionAllowance(
            ResearchAutonomyBudget(),
            ResearchExecutionSpend(step_advances=5),
        )
        with self.assertRaisesRegex(ResearchError, "allowance_exhausted"):
            self.service.grant("task-1")

    def test_paused_task_cannot_be_granted(self) -> None:
        self.context.task = replace(
            self.context.task, status=BackgroundResearchTaskStatus.PAUSED
        )
        with self.assertRaises(ResearchError):
            self.service.grant("task-1")


class PureEligibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = Context()
        self.grant = grant_for(self.context)

    def decide(self, grant=None):
        return deferred_execution_decision(
            self.context.task,
            self.context.execution,
            self.context.plan,
            self.context.allowance,
            self.grant if grant is None else grant,
        )

    def test_exact_active_grant_is_eligible(self) -> None:
        self.assertTrue(self.decide().allowed)

    def test_no_grant_is_manual_only(self) -> None:
        decision = deferred_execution_decision(
            self.context.task,
            self.context.execution,
            self.context.plan,
            self.context.allowance,
            None,
        )
        self.assertEqual(decision.reason, "manual_only")

    def test_task_execution_digest_capability_and_budget_mismatches_fail(self) -> None:
        mismatches = (
            replace(self.grant, task_id="task-2"),
            replace(self.grant, execution_id="execution-2"),
            replace(self.grant, plan_digest="0" * 64),
            replace(
                self.grant,
                capabilities=frozenset({ResearchPlanStepCapability.SOURCE_FETCH}),
            ),
            replace(self.grant, task_budget=ResearchAutonomyBudget()),
        )
        for mismatch in mismatches:
            with self.subTest(reason=mismatch):
                self.assertFalse(self.decide(mismatch).allowed)

    def test_paused_cancelled_and_completed_tasks_fail(self) -> None:
        for status in (
            BackgroundResearchTaskStatus.PAUSED,
            BackgroundResearchTaskStatus.CANCELLED,
            BackgroundResearchTaskStatus.COMPLETED,
        ):
            with self.subTest(status=status):
                self.context.task = replace(self.context.task, status=status)
                self.assertEqual(self.decide().reason, "task_not_runnable")

    def test_terminal_and_blocked_execution_state_wins(self) -> None:
        cancelled = self.context.execution.cancel()
        decision = deferred_execution_decision(
            self.context.task,
            cancelled,
            self.context.plan,
            self.context.allowance,
            self.grant,
        )
        self.assertFalse(decision.allowed)


class PersistenceTests(unittest.TestCase):
    def test_restart_restores_exact_grant_and_runs_nothing(self) -> None:
        context = Context()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "deferred.json"
            store = JsonFileDeferredExecutionGrantStore(path)
            service = TrustedDeferredExecutionControlService(
                context,
                store,
                clock=lambda: NOW,
                id_factory=lambda: "grant-1",
            )
            service.grant("task-1")
            restored = JsonFileDeferredExecutionGrantStore(path).load()
        self.assertEqual(restored, [grant_for(context)])
        self.assertEqual(context.execution.steps_with_research_work, 0)

    def test_absent_legacy_grant_store_is_manual_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = JsonFileDeferredExecutionGrantStore(Path(directory) / "absent.json")
            self.assertEqual(store.load(), [])


class StructuralBoundaryTests(unittest.TestCase):
    def test_control_plane_is_not_a_brain_intent(self) -> None:
        sources = (
            Path("src/cognition/CognitiveEngine.py").read_text(encoding="utf-8"),
            Path(
                "src/cognition/BackgroundResearchSchedulerApplicationService.py"
            ).read_text(encoding="utf-8"),
        )
        for source in sources:
            self.assertNotIn("deferred_execution_grant_intent", source)
            self.assertNotIn('metadata.get("human")', source)
            self.assertNotIn('source == "desktop"', source)

    def test_no_timer_polling_or_run_at_was_added(self) -> None:
        source = Path(
            "src/cognition/TrustedDeferredExecutionControlService.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("Timer(", source)
        self.assertNotIn("run_at", source)
        self.assertNotIn("sleep(", source)

    def test_desktop_control_does_not_send_a_brain_request(self) -> None:
        context = Context()
        store = MemoryGrantStore()
        service = TrustedDeferredExecutionControlService(
            context,
            store,
            clock=lambda: NOW,
            id_factory=lambda: "grant-1",
        )

        class RefusingBrain:
            def process(self, request):
                raise AssertionError("Trusted control must not reach Brain.")

        controller = DesktopController(RefusingBrain(), service)
        controller.allow_deferred_execution("task-1")
        self.assertEqual(len(store.records), 1)

    def test_declining_desktop_confirmation_creates_no_grant(self) -> None:
        context = Context()
        store = MemoryGrantStore()
        service = TrustedDeferredExecutionControlService(
            context,
            store,
            clock=lambda: NOW,
            id_factory=lambda: "grant-1",
        )

        class RefusingBrain:
            def process(self, request):
                raise AssertionError("Brain must not be called.")

        class Text:
            def __init__(self, value="") -> None:
                self.value = value

            def get(self):
                return self.value

            def set(self, value) -> None:
                self.value = value

        window = object.__new__(TkinterDesktopWindow)
        window._controller = DesktopController(RefusingBrain(), service)
        window._scheduler_task_id = Text("task-1")
        window._deferred_execution_status = Text()
        window._root = object()
        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno",
            return_value=False,
        ):
            window._allow_deferred_execution()
        self.assertEqual(store.records, [])
        self.assertIn("unchanged", window._deferred_execution_status.get())


if __name__ == "__main__":
    unittest.main()
