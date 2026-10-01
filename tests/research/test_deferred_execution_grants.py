"""Security boundary and exact-binding proofs for deferred execution grants."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
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
from research.DeferredExecutionGrant import (
    MAX_DEFERRED_EXECUTION_GRANT_VALIDITY,
    DeferredExecutionGrant,
)
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
MINUTE = timedelta(minutes=1)


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


class MutableClock:
    def __init__(self, now: datetime = NOW) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


class GrantRenewalTests(unittest.TestCase):
    """An expired, never-revoked grant must never block a verified renewal,
    and a renewal must never extend, reactivate, or otherwise read the old
    grant as live authority."""

    def setUp(self) -> None:
        self.context = Context()
        self.store = MemoryGrantStore()
        self.clock = MutableClock()
        self.ids = iter(["grant-1", "grant-2"])
        self.service = TrustedDeferredExecutionControlService(
            self.context,
            self.store,
            clock=self.clock,
            id_factory=lambda: next(self.ids),
        )

    def test_a_live_grant_still_blocks_renewal(self) -> None:
        self.service.grant("task-1")
        with self.assertRaisesRegex(ResearchError, "already has an active"):
            self.service.grant("task-1")

    def test_an_expired_grant_allows_a_verified_renewal(self) -> None:
        self.service.grant("task-1")
        self.clock.now = NOW + MAX_DEFERRED_EXECUTION_GRANT_VALIDITY

        view = self.service.grant("task-1")

        self.assertTrue(view.decision.allowed)
        assert view.grant is not None
        self.assertEqual(view.grant.grant_id, "grant-2")
        self.assertEqual(view.grant.granted_at, self.clock.now)

    def test_renewal_retires_the_old_grant_without_rewriting_its_identity(
        self,
    ) -> None:
        self.service.grant("task-1")
        original = self.store.records[0]
        self.clock.now = NOW + MAX_DEFERRED_EXECUTION_GRANT_VALIDITY

        self.service.grant("task-1")

        retired = next(g for g in self.store.records if g.grant_id == "grant-1")
        self.assertFalse(retired.active)
        self.assertEqual(
            retired.revoked_by, DeferredGrantAuthorizer.SUPERSEDED_BY_RENEWAL
        )
        self.assertEqual(retired.revoked_at, self.clock.now)
        # Nothing about the retired grant's own identity or validity window
        # was rewritten -- only revoked_at/revoked_by moved from unset.
        self.assertEqual(retired.granted_at, original.granted_at)
        self.assertEqual(retired.expires_at, original.expires_at)
        self.assertEqual(retired.task_id, original.task_id)
        self.assertEqual(retired.execution_id, original.execution_id)
        self.assertEqual(retired.plan_digest, original.plan_digest)
        self.assertEqual(retired.task_budget, original.task_budget)
        self.assertTrue(retired.has_expired_at(self.clock.now))

    def test_renewal_leaves_exactly_one_active_grant_for_the_task(self) -> None:
        """The store's own at-most-one-active-grant-per-task invariant must
        hold after a renewal -- proven against the real persisted store, not
        only the in-memory fixture, since that invariant is enforced there."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "deferred.json"
            store = JsonFileDeferredExecutionGrantStore(path)
            service = TrustedDeferredExecutionControlService(
                self.context,
                store,
                clock=self.clock,
                id_factory=lambda: next(self.ids),
            )
            service.grant("task-1")
            self.clock.now = NOW + MAX_DEFERRED_EXECUTION_GRANT_VALIDITY
            service.grant("task-1")

            persisted = JsonFileDeferredExecutionGrantStore(path).load()
        active = [g for g in persisted if g.active]
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].grant_id, "grant-2")
        self.assertEqual({g.grant_id for g in persisted}, {"grant-1", "grant-2"})

    def test_renewal_still_requires_a_meaningful_eligible_execution(self) -> None:
        """The fix removes the stale-grant obstacle, never the underlying
        eligibility gate every grant has always had to pass."""
        self.service.grant("task-1")
        self.clock.now = NOW + MAX_DEFERRED_EXECUTION_GRANT_VALIDITY
        self.context.allowance = ResearchExecutionAllowance(
            ResearchAutonomyBudget(),
            ResearchExecutionSpend(step_advances=5),
        )

        with self.assertRaisesRegex(ResearchError, "allowance_exhausted"):
            self.service.grant("task-1")

    def test_renewed_grant_binds_the_current_plan_not_the_old_one(self) -> None:
        """A renewal is a brand new grant derived from the plan as it is now
        -- it does not inherit or copy anything from the expired record."""
        self.service.grant("task-1")
        self.clock.now = NOW + MAX_DEFERRED_EXECUTION_GRANT_VALIDITY
        changed_plan = replace(
            self.context.plan,
            steps=self.context.plan.steps
            + (
                ResearchPlanStep(
                    step_id="step-2",
                    instruction="Fetch a source",
                    capability=ResearchPlanStepCapability.SOURCE_FETCH,
                ),
            ),
        )
        self.context.plan = changed_plan
        self.context.task = replace(
            self.context.task, budget=ResearchAutonomyBudget(max_step_advances=9)
        )

        view = self.service.grant("task-1")

        assert view.grant is not None
        self.assertEqual(view.grant.plan_digest, plan_digest(changed_plan))
        self.assertEqual(view.grant.capabilities, capabilities_of(changed_plan))
        self.assertEqual(view.grant.task_budget.max_step_advances, 9)


class PureEligibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = Context()
        self.grant = grant_for(self.context)

    def decide(self, grant=None, moment=NOW):
        return deferred_execution_decision(
            self.context.task,
            self.context.execution,
            self.context.plan,
            self.context.allowance,
            self.grant if grant is None else grant,
            moment,
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
            NOW,
        )
        self.assertEqual(decision.reason, "manual_only")

    def test_expired_grant_is_refused_with_its_own_named_reason(self) -> None:
        just_before = self.decide(
            moment=self.grant.granted_at
            + MAX_DEFERRED_EXECUTION_GRANT_VALIDITY
            - timedelta(seconds=1)
        )
        self.assertTrue(just_before.allowed)
        at_expiry = self.decide(
            moment=self.grant.granted_at + MAX_DEFERRED_EXECUTION_GRANT_VALIDITY
        )
        self.assertFalse(at_expiry.allowed)
        self.assertEqual(at_expiry.reason, "grant_expired")
        long_after = self.decide(
            moment=self.grant.granted_at
            + MAX_DEFERRED_EXECUTION_GRANT_VALIDITY
            + timedelta(days=365)
        )
        self.assertFalse(long_after.allowed)
        self.assertEqual(long_after.reason, "grant_expired")

    def test_revoked_grant_reports_manual_only_even_when_also_expired(self) -> None:
        revoked = self.grant.revoked(
            NOW, DeferredGrantAuthorizer.TRUSTED_LOCAL_OPERATOR
        )
        decision = self.decide(
            grant=revoked,
            moment=self.grant.granted_at
            + MAX_DEFERRED_EXECUTION_GRANT_VALIDITY
            + timedelta(days=1),
        )
        self.assertFalse(decision.allowed)
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
            NOW,
        )
        self.assertFalse(decision.allowed)


class GrantExpiryTests(unittest.TestCase):
    """`DeferredExecutionGrant.expires_at` closes the one domain in this
    codebase with no bound on how long a standing permission for *unattended*
    execution stays good."""

    def setUp(self) -> None:
        self.context = Context()
        self.grant = grant_for(self.context)

    def test_expiry_is_exactly_the_bounded_window_after_grant(self) -> None:
        self.assertEqual(
            self.grant.expires_at,
            self.grant.granted_at + MAX_DEFERRED_EXECUTION_GRANT_VALIDITY,
        )
        self.assertFalse(self.grant.has_expired_at(self.grant.expires_at - MINUTE))
        self.assertTrue(self.grant.has_expired_at(self.grant.expires_at))
        self.assertTrue(self.grant.has_expired_at(self.grant.expires_at + MINUTE))

    def test_expiry_check_requires_an_aware_moment(self) -> None:
        with self.assertRaises(ResearchError):
            self.grant.has_expired_at(NOW.replace(tzinfo=None))

    def test_revocation_does_not_change_expiry(self) -> None:
        """Revoked and expired are independent facts about the same grant."""
        revoked = self.grant.revoked(
            NOW, DeferredGrantAuthorizer.TRUSTED_LOCAL_OPERATOR
        )
        self.assertEqual(revoked.expires_at, self.grant.expires_at)
        self.assertFalse(revoked.active)
        self.assertFalse(revoked.has_expired_at(NOW))

    def test_restart_cannot_extend_or_revive_a_grants_validity(self) -> None:
        """A grant reloaded after restart reports the identical expiry its
        in-memory original did -- restart grants no fresh authority window."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "deferred.json"
            store = JsonFileDeferredExecutionGrantStore(path)
            store.save([self.grant])
            restored = store.load()[0]
        self.assertEqual(restored.expires_at, self.grant.expires_at)
        far_future = self.grant.granted_at + MAX_DEFERRED_EXECUTION_GRANT_VALIDITY
        self.assertTrue(restored.has_expired_at(far_future))

    def test_a_legacy_schema_one_grant_is_bound_by_the_same_rule(self) -> None:
        """`expires_at` is derived from `granted_at`, which every schema
        version always recorded, so a grant written before this rule existed
        is retroactively and safely bound by it -- never read as eternal."""
        legacy_document = {
            "schema_version": 1,
            "grants": [
                {
                    "grant_id": "legacy-grant",
                    "task_id": self.context.task.task_id,
                    "execution_id": self.context.task.execution_id,
                    "plan_digest": plan_digest(self.context.plan),
                    "capabilities": sorted(
                        value.value for value in capabilities_of(self.context.plan)
                    ),
                    "task_budget": {
                        "max_step_advances": self.context.task.budget.max_step_advances,
                        "max_network_operations": (
                            self.context.task.budget.max_network_operations
                        ),
                        "max_llm_operations": (
                            self.context.task.budget.max_llm_operations
                        ),
                        "max_seconds": self.context.task.budget.max_seconds,
                    },
                    "granted_at": NOW.isoformat(),
                    "granted_by": "trusted_local_operator",
                    "revoked_at": None,
                    "revoked_by": None,
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.json"
            path.write_text(json.dumps(legacy_document), encoding="utf-8")
            legacy = JsonFileDeferredExecutionGrantStore(path).load()[0]
        self.assertFalse(
            legacy.has_expired_at(NOW + MAX_DEFERRED_EXECUTION_GRANT_VALIDITY / 2)
        )
        self.assertTrue(
            legacy.has_expired_at(NOW + MAX_DEFERRED_EXECUTION_GRANT_VALIDITY)
        )


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
