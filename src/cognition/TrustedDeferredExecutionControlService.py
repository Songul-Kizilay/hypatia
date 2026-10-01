"""Desktop-only control plane for deferred research permission.

This service is intentionally absent from Brain and CognitiveEngine dispatch.
Its caller is trusted because Bootstrap gives this narrow object only to the
local desktop adapter. That is a local TCB boundary, not cryptographic identity
and not a defence against arbitrary code already running inside this process.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from core.Exceptions import ResearchError
from research.BackgroundResearchTask import BackgroundResearchTask
from research.DeferredExecutionControlView import DeferredExecutionControlView
from research.DeferredExecutionEligibility import deferred_execution_decision
from research.DeferredExecutionGrant import DeferredExecutionGrant
from research.DeferredExecutionGrantStore import DeferredExecutionGrantStore
from research.DeferredGrantAuthorizer import DeferredGrantAuthorizer
from research.ReadsDeferredExecutionContext import ReadsDeferredExecutionContext
from research.ResearchExecutionAllowance import ResearchExecutionAllowance
from research.ResearchExecutionProgressBlock import progress_block
from research.ResearchPlan import ResearchPlan
from research.ResearchPlanAuthorization import capabilities_of, restrictions_of
from research.ResearchPlanDigest import plan_digest
from research.ResearchPlanExecutionState import ResearchPlanExecutionState


class TrustedDeferredExecutionControlService:
    """Record and revoke only trusted-local-desktop confirmation facts."""

    def __init__(
        self,
        context: ReadsDeferredExecutionContext,
        store: DeferredExecutionGrantStore,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._context = context
        self._store = store
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or (lambda: str(uuid4()))

    def preview(self, task_id: str) -> DeferredExecutionControlView:
        task, execution, plan, allowance = self._binding(
            task_id, require_meaningful=False
        )
        grant = self._active_grant(task.task_id)
        return DeferredExecutionControlView(
            task_id=task.task_id,
            execution_id=task.execution_id,
            plan_digest=plan_digest(plan),
            task_budget=task.budget,
            grant=grant,
            decision=deferred_execution_decision(
                task, execution, plan, allowance, grant, self._clock()
            ),
            # From the exact plan being previewed, through the same helper the
            # grant itself is built with. Never a caller-supplied argument and
            # never read out of constraint wording.
            pending_restrictions=restrictions_of(plan),
        )

    def grant(self, task_id: str) -> DeferredExecutionControlView:
        """Issue one fresh grant, refusing only while a genuinely live one exists.

        An expired-but-not-revoked prior grant can never again authorize
        anything -- `has_expired_at` is the same, already-trusted check every
        other consumer of this type uses -- so it must not be able to block
        issuing a verified replacement forever. It is never read as live
        authority here, never extended, and never reactivated: this method
        still builds an entirely new grant with its own fresh identity and
        `granted_at`, and still runs it through the exact same eligibility
        check (`deferred_execution_decision`, unweakened) every grant always
        has. The only thing that changes is that a dead record stops being
        able to sit in the way of a live one for the same task forever.
        """
        task, execution, plan, allowance = self._binding(task_id)
        grants = self._store.load()
        existing = self._active_grant(task.task_id, grants)
        if existing is not None and not existing.has_expired_at(self._clock()):
            raise ResearchError("This task already has an active deferred grant.")
        if not task.status.runnable:
            raise ResearchError("Only a pending scheduler task may be granted.")
        blocked = progress_block(execution)
        if blocked is not None:
            raise ResearchError(f"The execution cannot progress: {blocked.value}.")
        if allowance is None:
            raise ResearchError("The execution has no existing allowance.")
        grant = DeferredExecutionGrant(
            grant_id=self._id_factory(),
            task_id=task.task_id,
            execution_id=task.execution_id,
            plan_digest=plan_digest(plan),
            capabilities=capabilities_of(plan),
            # The same extraction authorizations use. One meaning of "this
            # plan's restrictions", not two that could drift.
            approved_restrictions=restrictions_of(plan),
            task_budget=task.budget,
            granted_at=self._clock(),
            granted_by=DeferredGrantAuthorizer.TRUSTED_LOCAL_OPERATOR,
        )
        decision = deferred_execution_decision(
            task, execution, plan, allowance, grant, self._clock()
        )
        if not decision.allowed:
            raise ResearchError(
                f"Deferred execution is not currently eligible: {decision.reason}."
            )
        if existing is not None:
            # Reached only when `existing.has_expired_at` was already true
            # above. Retiring it here (never rewriting its identity, digest,
            # capabilities or budget) is what keeps the store's own
            # at-most-one-active-grant-per-task invariant true, exactly as it
            # already was before an expiry could ever happen.
            superseded = existing.revoked(
                self._clock(), DeferredGrantAuthorizer.SUPERSEDED_BY_RENEWAL
            )
            grants = [
                superseded if candidate.grant_id == existing.grant_id else candidate
                for candidate in grants
            ]
        grants.append(grant)
        self._store.save(grants)
        return self.preview(task.task_id)

    def revoke(self, task_id: str) -> DeferredExecutionControlView:
        task, _, _, _ = self._binding(task_id, require_meaningful=False)
        grants = self._store.load()
        match = self._active_grant(task.task_id, grants)
        if match is None:
            raise ResearchError("This task has no active deferred grant.")
        revoked = match.revoked(
            self._clock(), DeferredGrantAuthorizer.TRUSTED_LOCAL_OPERATOR
        )
        self._store.save(
            [revoked if grant.grant_id == match.grant_id else grant for grant in grants]
        )
        return self.preview(task.task_id)

    def _binding(
        self,
        task_id: str,
        *,
        require_meaningful: bool = True,
    ) -> tuple[
        BackgroundResearchTask,
        ResearchPlanExecutionState,
        ResearchPlan,
        ResearchExecutionAllowance | None,
    ]:
        normalized = task_id.strip()
        if not normalized:
            raise ResearchError("Deferred execution task ID cannot be empty.")
        task = self._context.background_research_task(normalized)
        if task is None:
            raise ResearchError("No exact scheduler task has that ID.")
        execution = self._context.live_research_execution(task.execution_id)
        plan = self._context.live_research_plan(task.execution_id)
        allowance = self._context.research_execution_allowance(task.execution_id)
        if execution is None or plan is None:
            raise ResearchError("The task's exact live execution is unavailable.")
        if execution.plan_id != task.execution_id or plan.plan_id != task.execution_id:
            raise ResearchError("The task no longer matches its exact execution.")
        if require_meaningful and progress_block(execution) is not None:
            raise ResearchError("The task's execution can no longer progress.")
        return task, execution, plan, allowance

    def _active_grant(
        self,
        task_id: str,
        grants: list[DeferredExecutionGrant] | None = None,
    ) -> DeferredExecutionGrant | None:
        matches = [
            grant
            for grant in (grants if grants is not None else self._store.load())
            if grant.task_id == task_id and grant.active
        ]
        return matches[0] if len(matches) == 1 else None
