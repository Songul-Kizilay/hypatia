"""Ephemeral coordination for one explicitly started research-plan execution.

Stages 2 and 3 of research-plan execution. This service owns execution state for
the current process only and performs no persistence.

Starting a plan records that execution began and advances no step. Advancing a
step runs exactly one connected research operation. Only an operation that
actually executed may mark a step as backed by real work; when no operation is
connected, or an operation reports that it performed nothing, the step is
blocked with a bounded reason instead of being reported as completed research.

Operation selection is an explicit table lookup on the step's declared typed
capability, never a heuristic over authored instruction text. A step declaring no
capability, or a capability with no registered operation, is blocked rather than
routed to something else.

A completed operation proves only that the operation ran. It is not evidence and
it is not a verified claim; evidence and claims still go through the existing
research evidence pipeline, which remains unconnected here.

State lives here, not in CognitiveEngine, and is lost when the process exits.
That loss is reported explicitly rather than presented as a finished or
resumable execution.

When an authorization consumer is composed in, starting requires one durable
human approval for this exact plan and run, and spends it. Ordering is the
safety property: the plan is built, every cheap refusal is checked, and only
then is the approval spent — and only a successful durable write produces a
runnable execution. A crash can therefore leave an approval spent with no
execution, and cannot leave an execution running on an approval still available
to spend again.

Without a consumer the service behaves as it always has. That shape is
composition, not a bypass: the runtime attaches a consumer wherever approvals
are kept, which is the same condition under which any start control exists.

The approved budget stops being a recorded number here. Every advance costs one
step advance plus whatever the step's declared capability costs, checked against
what remains *before* the attempt and charged at the attempt boundary. Nothing
is refunded when an operation fails or blocks: the attempt was made, and a
budget that came back after a failure could be spent twice by failing once.

Wall-clock is counted as time inside attempts, not time since the execution
started. An execution stepped by a person is idle between advances and idle
entirely while the application is closed; charging that would exhaust a budget
nobody spent.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from threading import RLock
from typing import cast

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from cognition.ResearchPlanExecutionEvents import (
    ExecutionBlockReason,
    ResearchPlanExecutionEvents,
)
from core.Exceptions import ResearchError
from eventbus.EventBus import EventBus
from research.ResearchAttemptRecovery import ResearchAttemptRecovery
from research.ResearchAttemptRecoveryDecision import (
    ResearchAttemptRecoveryDecision,
)
from research.ResearchAttemptResolution import ResearchAttemptResolution
from research.ResearchCapabilityCost import cost_for
from research.ResearchContinuationStopReason import (
    ResearchContinuationStopReason,
)
from research.ResearchDisclosure import ResearchDisclosure
from research.ResearchExecutionAllowance import ResearchExecutionAllowance
from research.ResearchExecutionContinuation import (
    MAX_FOREGROUND_CONTINUATION_STEPS,
    ResearchExecutionContinuation,
)
from research.ResearchExecutionStore import ResearchExecutionStore
from research.ResearchMissionStepResolver import ResearchMissionStepResolver
from research.ResearchPlan import ResearchPlan
from research.ResearchPlanAuthorizationConsumer import (
    ResearchPlanAuthorizationConsumer,
)
from research.ResearchPlanAuthorizationDecision import (
    ResearchPlanAuthorizationDecision,
)
from research.ResearchPlanAuthorizationVerdict import (
    ResearchPlanAuthorizationVerdict,
)
from research.ResearchPlanDigest import plan_digest
from research.ResearchPlanDraftService import (
    RESEARCH_PLAN_CONSTRAINTS_KEY,
    RESEARCH_PLAN_RESTRICTION_KEY,
    RESEARCH_PLAN_TARGET_BINDING_KEY,
    ResearchPlanDraftService,
    ResearchPlanStepDraft,
)
from research.ResearchPlanExecutionContext import ResearchPlanExecutionContext
from research.ResearchPlanExecutionSnapshot import (
    MAX_MISSION_REQUEST_ID_CHARACTERS,
    ResearchPlanExecutionSnapshot,
)
from research.ResearchPlanExecutionState import ResearchPlanExecutionState
from research.ResearchPlanExecutionStatus import ResearchPlanExecutionStatus
from research.ResearchPlanOperationRegistry import ResearchPlanOperationRegistry
from research.ResearchPlanRestriction import ResearchPlanRestriction
from research.ResearchPlanRestrictionConflict import (
    plan_restriction_conflicts,
)
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchPlanStepState import ResearchPlanStepState
from research.ResearchPlanStepStatus import ResearchPlanStepStatus
from research.ResearchPlanTargetBinding import ResearchPlanTargetBinding
from research.ResearchPlanTargetScopeRevisionGuard import (
    target_scope_revision_refusal,
)
from research.ResearchProgramScopeRevisionStore import ResearchProgramScopeRevisionStore
from research.ResearchSourcePreview import ResearchSourcePreview
from research.SemanticComparisonStepResult import SemanticComparisonStepResult
from research.SemanticEvidenceStepResult import SemanticEvidenceStepResult
from research.StartsResearchPlanExecution import ResearchPlanExecutionStartRefusal
from response.ResponseComposer import ResponseComposer

RESEARCH_PLAN_EXECUTION_START_INTENT = "research_plan_execution_start"
RESEARCH_PLAN_EXECUTION_STATUS_INTENT = "research_plan_execution_status"
RESEARCH_PLAN_EXECUTION_RESOLVE_INTENT = "research_plan_execution_resolve"
RESEARCH_PLAN_EXECUTION_RECOVER_INTENT = "research_plan_execution_recover"
RESEARCH_PLAN_EXECUTION_CONTINUE_INTENT = "research_plan_execution_continue"
RESEARCH_PLAN_EXECUTION_CANCEL_INTENT = "research_plan_execution_cancel"
RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT = "research_plan_execution_advance"

MAX_ACTIVE_RESEARCH_PLAN_EXECUTIONS = 20


class ResearchPlanExecutionApplicationService:
    """Coordinate bounded ephemeral execution state without doing research."""

    def __init__(
        self,
        response_composer: ResponseComposer,
        draft_service: ResearchPlanDraftService | None = None,
        *,
        operation_registry: ResearchPlanOperationRegistry | None = None,
        event_bus: EventBus | None = None,
        execution_store: ResearchExecutionStore | None = None,
        authorization_consumer: ResearchPlanAuthorizationConsumer | None = None,
        program_scope_revision_store: ResearchProgramScopeRevisionStore | None = None,
        clock: Callable[[], datetime] | None = None,
        max_active_executions: int = MAX_ACTIVE_RESEARCH_PLAN_EXECUTIONS,
        mission_resolver: ResearchMissionStepResolver | None = None,
    ) -> None:
        if (
            isinstance(max_active_executions, bool)
            or not isinstance(max_active_executions, int)
            or max_active_executions < 1
        ):
            raise ValueError(
                "Research plan execution capacity must be a positive integer."
            )
        self._response_composer = response_composer
        self._draft_service = draft_service or ResearchPlanDraftService()
        self._operation_registry = operation_registry or ResearchPlanOperationRegistry()
        self._events = ResearchPlanExecutionEvents(event_bus)
        self._max_active_executions = max_active_executions
        #: Held only around a commit, never across a provider call. It makes
        #: one read-modify-write of an execution indivisible, which is all that
        #: is needed: the danger is a slow attempt finishing onto a state that
        #: somebody else replaced while it ran.
        self._commit_lock = RLock()
        self._executions: dict[str, ResearchPlanExecutionState] = {}
        self._plans: dict[str, ResearchPlan] = {}
        self._contexts: dict[str, ResearchPlanExecutionContext] = {}
        self._execution_store = execution_store
        self._authorization_consumer = authorization_consumer
        self._program_scope_revision_store = program_scope_revision_store
        self._allowances: dict[str, ResearchExecutionAllowance] = {}
        self._mission_resolver = mission_resolver
        self._mission_digests: dict[str, str] = {}
        self._mission_request_ids: dict[str, str] = {}
        self._mission_recovery_refusals: dict[str, str] = {}
        self._clock = clock or (lambda: datetime.now(UTC))
        self._restored: dict[str, ResearchPlanExecutionSnapshot] = {}
        self._restore()

    @staticmethod
    def is_start_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == RESEARCH_PLAN_EXECUTION_START_INTENT

    @staticmethod
    def is_status_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == RESEARCH_PLAN_EXECUTION_STATUS_INTENT

    @staticmethod
    def is_cancel_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == RESEARCH_PLAN_EXECUTION_CANCEL_INTENT

    @staticmethod
    def is_advance_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT

    def process_start(self, request: BrainRequest) -> BrainResponse:
        """Start execution for one authored plan, or explain why it cannot."""
        question = request.metadata.get("research_plan_question")
        step_drafts = request.metadata.get("research_plan_steps")
        preview = self._draft_service.preview(
            cast(str, question),
            cast(tuple[ResearchPlanStepDraft, ...], step_drafts),
            # Rebuilt with its constraints, so the digest covers exactly what
            # the operator previewed. Dropping them here would approve or start
            # a different plan than the one that was shown.
            cast(
                tuple[str, ...],
                request.metadata.get(RESEARCH_PLAN_CONSTRAINTS_KEY) or (),
            ),
            cast(
                ResearchPlanRestriction | None,
                request.metadata.get(RESEARCH_PLAN_RESTRICTION_KEY),
            ),
            target_binding=cast(
                ResearchPlanTargetBinding | None,
                request.metadata.get(RESEARCH_PLAN_TARGET_BINDING_KEY),
            ),
        )
        if not preview.allowed:
            return self._response_composer.research_plan_execution_rejected(
                request,
                preview.reason,
            )
        plan = preview.plan
        assert plan is not None
        if plan.target_binding is not None and self._authorization_consumer is None:
            return self._response_composer.research_plan_execution_rejected(
                request, "Target-bound research requires a recorded human approval."
            )
        if scope_refusal := self._target_scope_refusal(plan):
            return self._response_composer.research_plan_execution_rejected(
                request,
                scope_refusal,
            )

        # The same canonical check the approval boundary ran. A stale or
        # internal path that reached here with a contradictory plan stops
        # before any provider is touched.
        conflicts = plan_restriction_conflicts(plan)
        if conflicts:
            return self._response_composer.research_plan_execution_rejected(
                request,
                " ".join(
                    ("This research plan contradicts itself, so it cannot start.",)
                    + tuple(conflict.summary() for conflict in conflicts)
                ),
            )

        if plan.plan_id in self._executions:
            return self._response_composer.research_plan_execution_rejected(
                request,
                "Research plan already has execution state in this process.",
            )
        if len(self._executions) >= self._max_active_executions:
            return self._response_composer.research_plan_execution_rejected(
                request,
                "Research plan execution capacity is full in this process.",
            )

        try:
            context = ResearchPlanExecutionContext(
                research_run_id=self._optional_run_id(request),
                target_binding=plan.target_binding,
            )
        except ResearchError as error:
            return self._response_composer.research_plan_execution_rejected(
                request,
                str(error),
            )

        # The identifier is allocated by building the plan, before anything is
        # runnable. Naming an execution is not starting one, and the approval
        # has to be spent against a name that already exists.
        decision = self._authorize(request, plan, context)
        if decision is not None and not decision.permits_start:
            return self._response_composer.research_plan_execution_unauthorized(
                request,
                decision.verdict,
            )
        if decision is not None and decision.authorization is not None:
            # The approved budget becomes this execution's allowance. Nothing
            # else may set it, so an advance can never be measured against a
            # bound nobody approved.
            self._allowances[plan.plan_id] = ResearchExecutionAllowance(
                budget=decision.authorization.budget
            )
            context = replace(context, disclosure=decision.authorization.disclosure)

        state = ResearchPlanExecutionState.prepare(plan).start()
        with self._commit_lock:
            self._executions[plan.plan_id] = state
            self._plans[plan.plan_id] = plan
            self._contexts[plan.plan_id] = context
        self._events.started(state, context.has_research_run)
        self._persist(plan.plan_id)
        return self._response_composer.research_plan_execution_status(request, state)

    def start_for_plan(
        self,
        plan: ResearchPlan,
        research_run_id: str,
        authorization_id: str,
        *,
        mission_request_id: str | None = None,
    ) -> ResearchPlanExecutionState | ResearchPlanExecutionStartRefusal:
        """Begin one already-derived plan, spending exactly one approval.

        The same start as any other: the same capacity check, the same
        approval consumer, the same allowance, the same state transition, the
        same event and the same durable write. What differs is only where the
        plan came from — a caller that derived and validated it — so it is not
        rebuilt from a message on the way in.

        Zero steps run. `start()` moves a prepared plan to running without
        beginning one, which is the boundary this whole chain has been built
        toward: the approval is now spent, and the first actual step still
        waits for a person to ask for it.
        """
        if plan.plan_id in self._executions:
            return ResearchPlanExecutionStartRefusal(
                "Research plan already has execution state in this process."
            )
        if plan.mission_scope is not None and (
            self._mission_resolver is None or self._execution_store is None
        ):
            return ResearchPlanExecutionStartRefusal(
                "Mission execution requires its resolver and durable execution store."
            )
        if len(self._executions) >= self._max_active_executions:
            return ResearchPlanExecutionStartRefusal(
                "Research plan execution capacity is full in this process."
            )
        try:
            normalized_mission_request_id = self._mission_request_id(mission_request_id)
        except ResearchError as error:
            return ResearchPlanExecutionStartRefusal(str(error))
        if scope_refusal := self._target_scope_refusal(plan):
            return ResearchPlanExecutionStartRefusal(scope_refusal)
        try:
            context = ResearchPlanExecutionContext(
                research_run_id=research_run_id, target_binding=plan.target_binding
            )
        except ResearchError as error:
            return ResearchPlanExecutionStartRefusal(str(error))
        if self._authorization_consumer is None:
            return ResearchPlanExecutionStartRefusal(
                "Research plan approval is unavailable, so nothing was started."
            )
        # Spent at the last moment, exactly as the authored-plan path spends it:
        # after every check that could refuse, so no approval is used on work
        # something else would have turned away.
        decision = self._authorization_consumer.consume_for_execution(
            authorization_id,
            plan,
            research_run_id,
            plan.plan_id,
            self._clock(),
        )
        if not decision.permits_start:
            return ResearchPlanExecutionStartRefusal(
                f"That approval does not permit starting: {decision.verdict.value}."
            )
        if decision.authorization is not None:
            self._allowances[plan.plan_id] = ResearchExecutionAllowance(
                budget=decision.authorization.budget
            )
            context = replace(context, disclosure=decision.authorization.disclosure)
        state = ResearchPlanExecutionState.prepare(plan).start()
        with self._commit_lock:
            self._executions[plan.plan_id] = state
            self._plans[plan.plan_id] = plan
            self._contexts[plan.plan_id] = context
            if plan.mission_scope is not None:
                self._mission_digests[plan.plan_id] = plan_digest(plan)
                if normalized_mission_request_id is not None:
                    self._mission_request_ids[plan.plan_id] = (
                        normalized_mission_request_id
                    )
        self._events.started(state, context.has_research_run)
        self._persist(plan.plan_id)
        return state

    def rebind_restored(
        self,
        plan: ResearchPlan,
        research_run_id: str,
        execution_id: str,
    ) -> ResearchPlanExecutionState | ResearchPlanExecutionStartRefusal:
        """Restore one durable execution so an operator can advance it again.

        Everything comes from what was written down. The step states are the
        recorded ones, so a completed step stays completed and is never run a
        second time; the allowance is the persisted one, so nothing is refunded
        by the act of restarting; and no approval is consulted or spent, because
        the approval that permitted this execution was spent when it started and
        must stay spent.

        It refuses rather than repairing. A missing snapshot, a status that was
        never runnable, an allowance that was never written, a plan whose steps
        do not match what was recorded, or a capability with no registered
        operation each end here, because every one of them means the execution
        that would be resumed is not provably the execution that was persisted.
        """
        snapshot = self._restored.get(execution_id)
        if snapshot is None:
            return ResearchPlanExecutionStartRefusal(
                "No durable execution with that identity was restored."
            )
        mission = (
            snapshot.mission_plan_digest is not None or plan.mission_scope is not None
        )
        if mission and (
            self._mission_resolver is None
            or snapshot.mission_plan_digest is None
            or snapshot.mission_scope is None
            or plan.mission_scope != snapshot.mission_scope
            or snapshot.mission_disclosure is ResearchDisclosure.NONE
            or snapshot.research_run_id != research_run_id
            or plan_digest(plan) != snapshot.mission_plan_digest
        ):
            return ResearchPlanExecutionStartRefusal(
                "Mission recovery lacks its exact recorded authority, scope or "
                "disclosure; no source or model call was replayed."
            )
        if execution_id in self._executions:
            return ResearchPlanExecutionStartRefusal(
                "That execution is already live in this process."
            )
        if snapshot.status not in _RESUMABLE_EXECUTION_STATUSES:
            return ResearchPlanExecutionStartRefusal(
                f"A {snapshot.status.value} execution cannot be resumed."
            )
        if snapshot.allowance is None:
            return ResearchPlanExecutionStartRefusal(
                "That execution recorded no approved allowance, so it cannot "
                "be resumed without inventing one."
            )
        if snapshot.target_plan_digest is not None or plan.target_binding is not None:
            if (
                plan.target_binding is None
                or snapshot.target_plan_digest != plan_digest(plan)
                or snapshot.research_run_id != research_run_id
            ):
                return ResearchPlanExecutionStartRefusal(
                    "Target execution must retain its exact recorded plan, "
                    "program, scope and research run."
                )
        if plan_restriction_conflicts(plan):
            return ResearchPlanExecutionStartRefusal(
                "The derived plan contains a capability forbidden by its own "
                "restriction."
            )
        if scope_refusal := self._target_scope_refusal(plan):
            return ResearchPlanExecutionStartRefusal(scope_refusal)
        recorded = {step.step_id: step for step in snapshot.steps}
        if {step.step_id for step in plan.steps} != set(recorded):
            return ResearchPlanExecutionStartRefusal(
                "The derived plan does not match the recorded execution steps."
            )
        for step in plan.steps:
            if step.capability is not recorded[step.step_id].capability:
                return ResearchPlanExecutionStartRefusal(
                    "The derived plan changes a recorded step capability."
                )
            if (
                recorded[step.step_id].status is ResearchPlanStepStatus.PENDING
                and step.capability.executable
                and self._operation_registry.resolve(step.capability) is None
            ):
                return ResearchPlanExecutionStartRefusal(
                    f"Capability '{step.capability.value}' has no registered "
                    "operation here, so this execution cannot be resumed."
                )
        try:
            state = ResearchPlanExecutionState(
                plan_id=execution_id,
                status=snapshot.status,
                steps=tuple(
                    ResearchPlanStepState(
                        step_id=step.step_id,
                        status=step.status,
                        detail=step.detail,
                        operation=step.operation,
                        work_performed=step.work_performed,
                    )
                    for step in snapshot.steps
                ),
                detail=snapshot.detail,
            )
            context = ResearchPlanExecutionContext(
                research_run_id=research_run_id,
                target_binding=plan.target_binding,
                disclosure=(
                    snapshot.mission_disclosure if mission else ResearchDisclosure.NONE
                ),
            )
        except ResearchError as error:
            return ResearchPlanExecutionStartRefusal(str(error))
        bound = replace(plan, plan_id=execution_id)
        if mission:
            assert self._mission_resolver is not None
            try:
                self._mission_resolver.restore(
                    bound,
                    snapshot.mission_checkpoint,
                    snapshot.steps,
                    research_run_id,
                )
            except ResearchError as error:
                return ResearchPlanExecutionStartRefusal(str(error))
        with self._commit_lock:
            self._executions[execution_id] = state
            self._plans[execution_id] = bound
        self._contexts[execution_id] = context
        self._allowances[execution_id] = snapshot.allowance
        if mission:
            assert snapshot.mission_plan_digest is not None
            self._mission_digests[execution_id] = snapshot.mission_plan_digest
            if snapshot.mission_request_id is not None:
                self._mission_request_ids[execution_id] = snapshot.mission_request_id
        self._restored.pop(execution_id, None)
        return state

    def _authorize(
        self,
        request: BrainRequest,
        plan: ResearchPlan,
        context: ResearchPlanExecutionContext,
    ) -> ResearchPlanAuthorizationDecision | None:
        """Spend one approval, returning a verdict only when refusing.

        Called at the last moment before anything becomes runnable, so no
        refusal can leave a half-started execution behind and no approval is
        spent on work another check would have rejected.
        """
        if self._authorization_consumer is None:
            return None
        authorization_id = request.metadata.get("authorization_id")
        if not isinstance(authorization_id, str) or not authorization_id.strip():
            return ResearchPlanAuthorizationDecision.refused(
                ResearchPlanAuthorizationVerdict.UNKNOWN
            )
        research_run_id = context.research_run_id
        if research_run_id is None:
            # An approval names a run, so a start that names none can never
            # match one. Refused as unknown rather than run-mismatched: there
            # is nothing to compare against.
            return ResearchPlanAuthorizationDecision.refused(
                ResearchPlanAuthorizationVerdict.UNKNOWN
            )
        return self._authorization_consumer.consume_for_execution(
            authorization_id,
            plan,
            research_run_id,
            plan.plan_id,
            self._clock(),
        )

    def _target_scope_refusal(self, plan: ResearchPlan) -> str | None:
        """Report a target plan whose saved scope revision is not live."""
        if plan.target_binding is None:
            return None
        try:
            return target_scope_revision_refusal(
                plan.target_binding,
                self._program_scope_revision_store,
                self._clock(),
            )
        except ResearchError as error:
            return str(error)

    def live_execution(self, plan_id: str) -> ResearchPlanExecutionState | None:
        """Return live execution state for a caller that only reads it."""
        return self._executions.get(plan_id)

    def live_plan(self, plan_id: str) -> ResearchPlan | None:
        """Return the authored plan behind a live execution, if any."""
        return self._plans.get(plan_id)

    def restored_execution(
        self,
        plan_id: str,
    ) -> ResearchPlanExecutionSnapshot | None:
        """Return restored durable state, which can be read but not advanced."""
        return self._restored.get(plan_id)

    def restored_mission_executions(self) -> tuple[ResearchPlanExecutionSnapshot, ...]:
        """Return only new-format mission snapshots eligible for safe recovery."""
        return tuple(
            snapshot
            for snapshot in self._restored.values()
            if snapshot.mission_scope is not None
        )

    def restored_mission_request_ids(self) -> frozenset[str]:
        """Return durable mission request IDs without treating them as authority."""
        return frozenset(
            snapshot.mission_request_id
            for snapshot in self._restored.values()
            if snapshot.mission_request_id is not None
        )

    def record_mission_recovery_refusal(self, plan_id: str, reason: str) -> None:
        """Keep one bounded restart reason visible without changing durable state."""
        if (
            plan_id not in self._restored
            or not isinstance(reason, str)
            or not reason.strip()
        ):
            return
        self._mission_recovery_refusals[plan_id] = reason.strip()[:500]

    def process_status(self, request: BrainRequest) -> BrainResponse:
        """Report live state, restored durable state, or neither."""
        plan_id = self._normalized_plan_id(request)
        state = self._executions.get(plan_id)
        if state is None:
            restored = self._restored.get(plan_id)
            if restored is not None:
                return self._response_composer.research_plan_execution_restored(
                    request,
                    restored,
                    self._mission_recovery_refusals.get(plan_id),
                )
            return self._response_composer.research_plan_execution_missing(
                request,
                plan_id,
            )
        return self._response_composer.research_plan_execution_status(
            request,
            state,
            self._allowances.get(plan_id),
            self._next_capability(plan_id, state),
        )

    def _next_capability(
        self,
        plan_id: str,
        state: ResearchPlanExecutionState,
    ) -> str:
        """Name the capability the next advance would use, or nothing."""
        plan = self._plans.get(plan_id)
        step_id = state.next_pending_step_id
        if plan is None or step_id is None:
            return ""
        for step in plan.steps:
            if step.step_id == step_id:
                return step.capability.value
        return ""

    def process_cancel(self, request: BrainRequest) -> BrainResponse:
        """Cancel unfinished steps while preserving completed-step history."""
        plan_id = self._normalized_plan_id(request)
        # Read, derive and write together. Deriving from a state somebody else
        # replaces before the write is exactly how a cancellation used to be
        # lost, and cancelling is the transition that can least afford it.
        with self._commit_lock:
            state = self._executions.get(plan_id)
            if state is None:
                return self._response_composer.research_plan_execution_missing(
                    request,
                    plan_id,
                )
            try:
                cancelled = state.cancel("Cancelled by explicit user request.")
            except ResearchError as error:
                return self._response_composer.research_plan_execution_rejected(
                    request,
                    str(error),
                )
            self._executions[plan_id] = cancelled
        self._events.cancelled(cancelled)
        self._persist(plan_id)
        return self._response_composer.research_plan_execution_status(
            request,
            cancelled,
        )

    def is_resolve_request(self, request: BrainRequest) -> bool:
        return request.metadata.get("intent") == RESEARCH_PLAN_EXECUTION_RESOLVE_INTENT

    def process_resolve(self, request: BrainRequest) -> BrainResponse:
        """Record one explicit human ruling about an interrupted attempt.

        Nothing is inferred and nothing is retried. The operator names the exact
        execution, the exact step, and what they actually know; this writes that
        down and stops. No provider is reached, so no budget is charged — the
        charge for the interrupted attempt was made when it began and stays
        exactly as it is.
        """
        plan_id = self._normalized_plan_id(request)
        state = self._executions.get(plan_id)
        if state is None:
            return self._response_composer.research_plan_execution_missing(
                request,
                plan_id,
            )
        step_id = str(request.metadata.get("step_id", "")).strip()
        if not step_id:
            return self._response_composer.research_plan_execution_rejected(
                request,
                "Resolving an interrupted attempt needs the exact step.",
            )
        try:
            resolution = ResearchAttemptResolution(
                str(request.metadata.get("resolution", "")).strip()
            )
        except ValueError:
            return self._response_composer.research_plan_execution_rejected(
                request,
                "That is not a ruling this system understands.",
            )
        try:
            resolved = state.resolve_interrupted_step(
                step_id,
                resolution,
                self._clock(),
            )
        except ResearchError as error:
            return self._response_composer.research_plan_execution_rejected(
                request,
                str(error),
            )
        if not self._commit_outcome(plan_id, state, resolved):
            # Somebody committed a newer state while this decision was
            # being formed. Theirs stands; nothing here is forced over it.
            return self._response_composer.research_plan_execution_rejected(
                request,
                "That execution changed while the ruling was being made.",
            )
        self._events.step_resolved(plan_id, step_id, resolution.value)
        if not self._persist_checkpoint(plan_id):
            # The ruling is only worth having if it survives. Put the previous
            # state back rather than report a decision no restart would find.
            self._commit_outcome(plan_id, resolved, state)
            return self._response_composer.research_plan_execution_rejected(
                request,
                "The ruling could not be recorded durably, so it was not kept.",
            )
        return self._response_composer.research_plan_execution_status(
            request,
            resolved,
            self._allowances.get(plan_id),
            self._next_capability(plan_id, resolved),
        )

    def is_recover_request(self, request: BrainRequest) -> bool:
        return request.metadata.get("intent") == RESEARCH_PLAN_EXECUTION_RECOVER_INTENT

    def process_recover(self, request: BrainRequest) -> BrainResponse:
        """Record what an operator did about a performed, unseen attempt.

        The two decisions are the operator's alone. Nothing here contacts a
        provider, so nothing is charged; the attempt was paid for when it began
        and stays paid for. What the operator reports is kept as theirs, and no
        part of this request can grant a capability, an approval or a budget.
        """
        plan_id = self._normalized_plan_id(request)
        state = self._executions.get(plan_id)
        if state is None:
            return self._response_composer.research_plan_execution_missing(
                request,
                plan_id,
            )
        step_id = str(request.metadata.get("step_id", "")).strip()
        if not step_id:
            return self._response_composer.research_plan_execution_rejected(
                request,
                "Recovering an attempt needs the exact step.",
            )
        try:
            recovery = ResearchAttemptRecovery(
                decision=ResearchAttemptRecoveryDecision(
                    str(request.metadata.get("decision", "")).strip()
                ),
                recorded_at=self._clock(),
                summary=str(request.metadata.get("summary", "")),
                claimed_operation=str(request.metadata.get("claimed_operation", "")),
            )
        except ValueError:
            return self._response_composer.research_plan_execution_rejected(
                request,
                "That is not a recovery decision this system understands.",
            )
        except ResearchError as error:
            return self._response_composer.research_plan_execution_rejected(
                request,
                str(error),
            )
        try:
            recovered = state.recover_blocked_step(step_id, recovery)
        except ResearchError as error:
            return self._response_composer.research_plan_execution_rejected(
                request,
                str(error),
            )
        if not self._commit_outcome(plan_id, state, recovered):
            # Somebody committed a newer state while this decision was
            # being formed. Theirs stands; nothing here is forced over it.
            return self._response_composer.research_plan_execution_rejected(
                request,
                "That execution changed while the decision was being made.",
            )
        self._events.step_recovered(plan_id, step_id, recovery.decision.value)
        if not self._persist_checkpoint(plan_id):
            self._commit_outcome(plan_id, recovered, state)
            return self._response_composer.research_plan_execution_rejected(
                request,
                "The decision could not be recorded durably, so it was not kept.",
            )
        return self._response_composer.research_plan_execution_status(
            request,
            recovered,
            self._allowances.get(plan_id),
            self._next_capability(plan_id, recovered),
        )

    def is_continue_request(self, request: BrainRequest) -> bool:
        return request.metadata.get("intent") == RESEARCH_PLAN_EXECUTION_CONTINUE_INTENT

    def process_continue(self, request: BrainRequest) -> BrainResponse:
        """Run the ordinary one-step advance, at most this many times.

        Deliberately nothing more than a loop around `process_advance`. Every
        budget check, capability check, durable attempt checkpoint and refusal
        is the one an operator pressing the button once would get, because it
        is literally that code being called again. Nothing here reaches an
        operation, charges anything, or writes execution state itself.

        It stops at the first sign that carrying on is not obviously safe, and
        never steps over a problem to find a step it likes better. A blocked or
        interrupted step ends the run where it is, and what to do about it stays
        an explicit human decision made afterwards.
        """
        plan_id = self._normalized_plan_id(request)
        bound = self._continuation_bound(request)
        if bound is None:
            return self._response_composer.research_plan_execution_rejected(
                request,
                "Continuing needs an explicit step count from 1 to "
                f"{MAX_FOREGROUND_CONTINUATION_STEPS}.",
            )
        if self._executions.get(plan_id) is None:
            return self._response_composer.research_plan_execution_missing(
                request,
                plan_id,
            )
        attempted: list[str] = []
        previews: list[ResearchSourcePreview] = []
        semantic_results: list[SemanticEvidenceStepResult] = []
        comparison_results: list[SemanticComparisonStepResult] = []
        reason = ResearchContinuationStopReason.BOUND_REACHED
        while len(attempted) < bound:
            state = self._executions[plan_id]
            halted = self._continuation_halt(state)
            if halted is not None:
                reason = halted
                break
            step_id = state.next_pending_step_id
            if step_id is None:
                reason = ResearchContinuationStopReason.NO_PENDING_STEP
                break
            response = self.process_advance(request)
            previews.extend(response.research_source_previews)
            semantic_results.extend(response.semantic_evidence_proposals)
            comparison_results.extend(response.semantic_comparison_proposals)
            after = self._executions[plan_id]
            if self._step_status(after, step_id) is not ResearchPlanStepStatus.PENDING:
                attempted.append(step_id)
            halted = self._continuation_halt(after)
            if halted is not None:
                reason = halted
                break
            if not response.success or step_id == after.next_pending_step_id:
                reason = self._refusal_reason(plan_id, after)
                break
        final = self._executions[plan_id]
        continuation = ResearchExecutionContinuation(
            execution_id=plan_id,
            requested_max_steps=bound,
            final_status=final.status,
            stop_reason=reason,
            attempted_step_ids=tuple(attempted),
            next_step_id=final.next_pending_step_id or "",
            allowance=self._allowances.get(plan_id),
        )
        return replace(
            self._response_composer.research_plan_execution_continued(
                request,
                continuation,
                final,
            ),
            # At most one bounded body per attempted step; continuation has a
            # hard ten-step ceiling. Nothing is retained on the service itself.
            research_source_previews=tuple(previews),
            semantic_evidence_proposals=tuple(semantic_results),
            semantic_comparison_proposals=tuple(comparison_results),
        )

    @staticmethod
    def _continuation_bound(request: BrainRequest) -> int | None:
        """Return the operator's explicit bound, or nothing when unusable.

        Absent is never taken to mean unlimited. A bound is something somebody
        chose, and no reading of a missing field produces one.
        """
        raw = request.metadata.get("max_steps")
        if isinstance(raw, bool) or not isinstance(raw, (int, str)):
            return None
        try:
            bound = int(raw)
        except TypeError, ValueError:
            return None
        if bound < 1 or bound > MAX_FOREGROUND_CONTINUATION_STEPS:
            return None
        return bound

    @staticmethod
    def _continuation_halt(
        state: ResearchPlanExecutionState,
    ) -> ResearchContinuationStopReason | None:
        """Return why this state stops a continuation, or nothing if it does not."""
        return _CONTINUATION_HALTS.get(state.status)

    @staticmethod
    def _step_status(
        state: ResearchPlanExecutionState,
        step_id: str,
    ) -> ResearchPlanStepStatus | None:
        for step in state.steps:
            if step.step_id == step_id:
                return step.status
        return None

    def _refusal_reason(
        self,
        plan_id: str,
        state: ResearchPlanExecutionState,
    ) -> ResearchContinuationStopReason:
        """Name why an advance changed nothing, without re-deciding anything.

        The allowance is only read here, to tell an operator out of budget from
        an operator refused for some other reason. Whether a step may run was
        already settled inside the one-step path.
        """
        allowance = self._allowances.get(plan_id)
        step_id = state.next_pending_step_id
        if allowance is not None and step_id is not None:
            step = next(
                (
                    candidate
                    for candidate in self._plans[plan_id].steps
                    if candidate.step_id == step_id
                ),
                None,
            )
            if step is not None and not allowance.affords(cost_for(step.capability)):
                return ResearchContinuationStopReason.BUDGET_EXHAUSTED
        return ResearchContinuationStopReason.ADVANCE_REFUSED

    def mission_delivery_ready(self, plan_id: str) -> bool:
        plan = self._plans.get(plan_id)
        state = self._executions.get(plan_id)
        return bool(
            plan is not None
            and state is not None
            and self._mission_resolver is not None
            and self._mission_resolver.followup_unnecessary(
                plan, state.next_pending_step_id
            )
        )

    def process_advance(self, request: BrainRequest) -> BrainResponse:
        """Run one real research operation for the next pending step."""
        plan_id = self._normalized_plan_id(request)
        state = self._executions.get(plan_id)
        plan = self._plans.get(plan_id)
        if state is None or plan is None:
            return self._response_composer.research_plan_execution_missing(
                request,
                plan_id,
            )
        if (plan.mission_scope is not None or plan_id in self._mission_digests) and (
            plan.mission_scope is None
            or self._mission_digests.get(plan_id) != plan_digest(plan)
            or self._mission_resolver is None
            or plan_id not in self._allowances
        ):
            return self._response_composer.research_plan_execution_rejected(
                request, "Derived mission work lacks the original consumed authority."
            )
        if scope_refusal := self._target_scope_refusal(plan):
            return self._response_composer.research_plan_execution_rejected(
                request,
                scope_refusal,
            )
        if self.mission_delivery_ready(plan_id):
            return self._response_composer.research_plan_execution_rejected(
                request,
                "Bounded deliverable ready; optional follow-up is unnecessary. "
                "No further attempt or charge.",
            )
        interrupted = next(
            (
                candidate.step_id
                for candidate in state.steps
                if candidate.status is ResearchPlanStepStatus.INTERRUPTED
            ),
            None,
        )
        if interrupted is not None:
            # The attempt was charged and may have reached the provider before
            # the process died. Whether it did is not knowable here, so this
            # refuses rather than quietly performing it a second time.
            return self._response_composer.research_plan_execution_rejected(
                request,
                f"Step '{interrupted}' was interrupted mid-attempt and its "
                "outcome is unknown. It was already charged and may have "
                "reached its provider, so advancing will not run it again.",
            )
        step_id = state.next_pending_step_id
        if step_id is None:
            return self._response_composer.research_plan_execution_rejected(
                request,
                "Research plan execution has no pending step to advance.",
            )
        step = next(
            candidate for candidate in plan.steps if candidate.step_id == step_id
        )
        if not step.capability.executable:
            return self._blocked(
                request,
                plan_id,
                state,
                step_id,
                ("Step declares no executable capability; " "nothing was performed."),
                ExecutionBlockReason.NO_DECLARED_CAPABILITY,
            )
        operation = self._operation_registry.resolve(step.capability)
        if operation is None:
            return self._blocked(
                request,
                plan_id,
                state,
                step_id,
                (
                    f"Capability '{step.capability.value}' has no registered "
                    "operation; nothing was performed."
                ),
                ExecutionBlockReason.UNREGISTERED_CAPABILITY,
            )

        allowance = self._allowances.get(plan_id)
        cost = cost_for(step.capability)
        if cost.llm_operations and allowance is None:
            return self._response_composer.research_plan_execution_rejected(
                request, "Model steps require an explicit approved execution budget."
            )
        if allowance is not None and not allowance.affords(cost):
            # Refused before the attempt, so nothing is charged and no
            # operation runs. Pressing the button again cannot get past this.
            self._events.budget_refused(plan_id, step_id, step.capability.value)
            return self._response_composer.research_plan_execution_budget_refused(
                request,
                plan_id,
                step.capability.value,
                allowance,
            )

        try:
            running = state.start_step(step_id, operation.operation_name)
        except ResearchError as error:
            return self._response_composer.research_plan_execution_rejected(
                request,
                str(error),
            )
        # The attempt boundary. From here the advance is spent whatever the
        # operation goes on to do.
        attempt_started_at = self._clock()
        if allowance is not None:
            self._allowances[plan_id] = allowance.charged(cost)
        # Written down before the provider is reachable. A crash from here on
        # leaves a record saying this step was attempted and paid for, which is
        # the truth; leaving it pending would say the attempt never happened.
        if not self._commit_outcome(plan_id, state, running):
            # Somebody committed while this attempt was being prepared. No
            # provider is reached, so the charge made a moment ago is given
            # back — the same thing the failed-checkpoint path does, and for
            # the same reason: nothing was spent because nothing was tried.
            if allowance is not None:
                self._allowances[plan_id] = allowance
            return self._superseded(request, plan_id, step_id, operation.operation_name)
        self._events.step_started(
            plan_id,
            step_id,
            step.capability.value,
            operation.operation_name,
        )
        if not self._persist_checkpoint(plan_id):
            # Nothing external has happened yet, so the record from before the
            # attempt is still the true one. Put it back rather than run an
            # operation whose having happened no restart could discover — but
            # only if this attempt's own state is still what stands, because a
            # rollback over somebody else's newer decision is the same mistake
            # in the other direction.
            self._commit_outcome(plan_id, running, state)
            if allowance is not None:
                self._allowances[plan_id] = allowance
            return self._response_composer.research_plan_execution_rejected(
                request,
                "The attempt could not be recorded durably, so nothing was "
                "performed and nothing was charged.",
            )
        try:
            stored = self._contexts.get(plan_id, ResearchPlanExecutionContext())
            operation_context = ResearchPlanExecutionContext(
                research_run_id=stored.research_run_id,
                cancellation_token=request.cancellation_token,
                target_binding=plan.target_binding,
                execution_id=plan_id,
                disclosure=stored.disclosure,
                research_question=plan.question,
            )
            if plan.mission_scope is not None:
                assert self._mission_resolver is not None
                step, operation_context = self._mission_resolver.resolve(
                    plan, step, operation_context
                )
            result = operation.run(
                step,
                operation_context,
            )
            if plan.mission_scope is not None:
                assert self._mission_resolver is not None
                self._mission_resolver.observe(plan, step, operation_context, result)
        except ResearchError as error:
            self._charge_elapsed(plan_id, attempt_started_at)
            failed = running.fail_step(step_id, str(error))
            if not self._commit_outcome(plan_id, running, failed):
                return self._superseded(
                    request, plan_id, step_id, operation.operation_name
                )
            self._events.step_failed(
                plan_id,
                step_id,
                operation.operation_name,
                type(error).__name__,
                work_performed=False,
            )
            self._persist(plan_id)
            return self._response_composer.research_plan_execution_status(
                request,
                failed,
                self._allowances.get(plan_id),
                self._next_capability(plan_id, failed),
            )
        self._charge_elapsed(plan_id, attempt_started_at)
        if not result.performed:
            return self._blocked(
                request,
                plan_id,
                running,
                step_id,
                result.detail,
                ExecutionBlockReason.OPERATION_PERFORMED_NOTHING,
            )
        if not result.succeeded:
            failed = running.fail_step(
                step_id,
                result.detail,
                work_performed=True,
                operation=operation.operation_name,
            )
            if not self._commit_outcome(plan_id, running, failed):
                return self._superseded(
                    request, plan_id, step_id, operation.operation_name
                )
            self._events.step_failed(
                plan_id,
                step_id,
                operation.operation_name,
                "operation_did_not_succeed",
                work_performed=True,
            )
            self._persist(plan_id)
            return self._response_composer.research_plan_execution_status(
                request,
                failed,
                self._allowances.get(plan_id),
                self._next_capability(plan_id, failed),
            )
        completed = running.complete_step(
            step_id,
            result.detail,
            work_performed=True,
            operation=operation.operation_name,
        )
        if not self._commit_outcome(plan_id, running, completed):
            return self._superseded(request, plan_id, step_id, operation.operation_name)
        self._events.step_completed(plan_id, step_id, operation.operation_name)
        self._persist(plan_id)
        preview = result.source_preview
        comparison = result.semantic_comparison
        comparison_matches = (
            comparison is not None
            and step.capability
            is ResearchPlanStepCapability.SEMANTIC_EVIDENCE_COMPARISON
            and step.semantic_comparison_binding is not None
            and comparison.request == step.semantic_comparison_binding.request
            and comparison.execution_id == plan_id
            and comparison.step_id == step_id
            and comparison.request.run_id == stored.research_run_id
            and comparison.request.question == plan.question
            and not (
                request.cancellation_token and request.cancellation_token.is_cancelled()
            )
        )
        semantic = result.semantic_evidence
        semantic_matches = (
            semantic is not None
            and step.capability is ResearchPlanStepCapability.SEMANTIC_EVIDENCE_PROPOSAL
            and step.semantic_evidence_binding is not None
            and semantic.request.content_fingerprint
            == step.semantic_evidence_binding.input_fingerprint
            and semantic.execution_id == plan_id
            and semantic.step_id == step_id
            and semantic.request.previews[0].run_id == stored.research_run_id
            and semantic.request.question.strip() == plan.question
            and not (
                request.cancellation_token and request.cancellation_token.is_cancelled()
            )
        )
        preview_matches = (
            preview is not None
            and step.capability is ResearchPlanStepCapability.SOURCE_FETCH
            and preview.execution_id == plan_id
            and preview.run_id == stored.research_run_id
            and preview.step_id == step_id
            and preview.requested_url == step.authorized_source_url
            and not (
                request.cancellation_token and request.cancellation_token.is_cancelled()
            )
        )
        return replace(
            self._response_composer.research_plan_execution_status(
                request,
                completed,
                self._allowances.get(plan_id),
                self._next_capability(plan_id, completed),
            ),
            research_source_previews=(preview,) if preview_matches and preview else (),
            semantic_comparison_proposals=(
                (comparison,) if comparison_matches and comparison else ()
            ),
            semantic_evidence_proposals=(
                (semantic,) if semantic_matches and semantic else ()
            ),
        )

    def _commit_outcome(
        self,
        plan_id: str,
        expected: ResearchPlanExecutionState,
        successor: ResearchPlanExecutionState,
    ) -> bool:
        """Commit one canonical transition, unless the execution has moved on.

        The comparison is against the exact state this attempt committed before
        reaching the provider. Execution states are immutable values, so equality
        answers the only question that matters — is this still the execution I
        started from — without needing a revision counter to ask it.

        A newer state always wins. It was written by somebody who knew what they
        were doing at a later moment: an operator cancelling, a ruling on an
        interrupted attempt, a recovery. Overwriting it with a successor built
        before any of that happened would undo a decision, silently.
        """
        with self._commit_lock:
            if self._executions.get(plan_id) != expected:
                return False
            self._executions[plan_id] = successor
            return True

    def _superseded(
        self,
        request: BrainRequest,
        plan_id: str,
        step_id: str,
        operation: str,
    ) -> BrainResponse:
        """Report an outcome that arrived after the execution had moved on.

        The operation may genuinely have run, and the event says so. What is
        reported as canonical is the state that actually stands, not the one
        this attempt was building, because reporting the latter would tell an
        operator their cancellation had been undone.

        Anything already charged for the attempt stays charged. Time and network
        were spent reaching out, and a concurrent decision elsewhere does not
        give them back.
        """
        current = self._executions.get(plan_id)
        self._events.outcome_superseded(
            plan_id,
            step_id,
            operation,
            current.status.value if current is not None else "unknown",
        )
        self._persist(plan_id)
        if current is None:
            return self._response_composer.research_plan_execution_missing(
                request,
                plan_id,
            )
        return self._response_composer.research_plan_execution_status(
            request,
            current,
            self._allowances.get(plan_id),
            self._next_capability(plan_id, current),
        )

    def _restore(self) -> None:
        """Load durable executions, marking mid-flight work interrupted.

        A corrupt or unreadable store raises here rather than being replaced by
        an empty one, because silently discarding it would erase execution
        history on the next write.
        """
        if self._execution_store is None:
            return
        for snapshot in self._execution_store.load():
            restored = snapshot.restored()
            self._restored[restored.plan_id] = restored
            self._events.restored(
                restored.plan_id,
                restored.status.value,
                sum(
                    1
                    for step in restored.steps
                    if step.status is ResearchPlanStepStatus.INTERRUPTED
                ),
            )

    def _charge_elapsed(self, plan_id: str, started_at: datetime) -> None:
        """Add the wall-clock spent inside one attempt to its allowance.

        Charged after the operation resolves, on every path, because time was
        spent whether it succeeded, blocked, or raised.
        """
        allowance = self._allowances.get(plan_id)
        if allowance is None:
            return
        elapsed = (self._clock() - started_at).total_seconds()
        self._allowances[plan_id] = allowance.with_elapsed(elapsed)

    def allowance(self, plan_id: str) -> ResearchExecutionAllowance | None:
        """Return what one execution was approved and has spent, read-only."""
        return self._allowances.get(plan_id)

    def _persist(self, plan_id: str) -> None:
        """Write durable state, never erasing it silently on failure."""
        self._persist_checkpoint(plan_id)

    def _persist_checkpoint(self, plan_id: str) -> bool:
        """Write durable state and say whether it actually landed.

        The answer only matters before an attempt: a caller about to reach a
        provider must not do so on the strength of a write that failed. After a
        result is in hand there is nothing better to do than report the failure,
        which is what the plain persist does.

        A service with no store answers yes. It never promised durability, so
        refusing every advance would be inventing a guarantee rather than
        keeping one.
        """
        if self._execution_store is None:
            return True
        try:
            self._execution_store.save(self._snapshots())
        except ResearchError as error:
            self._events.persistence_failed(plan_id, type(error).__name__)
            return False
        return True

    def _snapshots(self) -> list[ResearchPlanExecutionSnapshot]:
        """Capture live executions, keeping restored history alongside them."""
        recorded_at = self._clock()
        snapshots: list[ResearchPlanExecutionSnapshot] = []
        for plan_id, state in self._executions.items():
            plan = self._plans[plan_id]
            context = self._contexts.get(plan_id, ResearchPlanExecutionContext())
            mission_scope = None
            mission_disclosure = ResearchDisclosure.NONE
            mission_checkpoint = None
            scope = plan.mission_scope
            if (
                scope is not None
                and scope.semantic_policy is not None
                and context.disclosure is scope.semantic_policy.disclosure
            ):
                mission_scope = scope
                mission_disclosure = context.disclosure
                if self._mission_resolver is not None:
                    mission_checkpoint = self._mission_resolver.checkpoint(plan)
            snapshots.append(
                ResearchPlanExecutionSnapshot.capture(
                    state,
                    plan.question,
                    plan.steps,
                    recorded_at,
                    context.research_run_id,
                    self._allowances.get(plan_id),
                    target_plan_digest=(
                        plan_digest(plan) if plan.target_binding is not None else None
                    ),
                    mission_plan_digest=self._mission_digests.get(plan_id),
                    mission_scope=mission_scope,
                    mission_disclosure=mission_disclosure,
                    mission_checkpoint=mission_checkpoint,
                    mission_request_id=self._mission_request_ids.get(plan_id),
                )
            )
        snapshots.extend(
            snapshot
            for plan_id, snapshot in self._restored.items()
            if plan_id not in self._executions
        )
        return snapshots

    def _blocked(
        self,
        request: BrainRequest,
        plan_id: str,
        state: ResearchPlanExecutionState,
        step_id: str,
        detail: str,
        reason: ExecutionBlockReason,
    ) -> BrainResponse:
        """Block a step instead of implying work that never happened."""
        blocked = state.block_step(step_id, detail)
        if not self._commit_outcome(plan_id, state, blocked):
            return self._superseded(request, plan_id, step_id, reason.value)
        self._events.step_blocked(plan_id, step_id, reason)
        self._persist(plan_id)
        return self._response_composer.research_plan_execution_status(
            request,
            blocked,
        )

    @staticmethod
    def _optional_run_id(request: BrainRequest) -> str | None:
        """Read the optional explicit research run binding for this execution."""
        value = request.metadata.get("research_run_id")
        if value is None:
            return None
        if not isinstance(value, str):
            raise ResearchError("Research execution run ID must be text.")
        return value

    @staticmethod
    def _mission_request_id(value: str | None) -> str | None:
        if value is None:
            return None
        if (
            not isinstance(value, str)
            or not value.strip()
            or len(value.strip()) > MAX_MISSION_REQUEST_ID_CHARACTERS
        ):
            raise ResearchError("Mission request ID is invalid.")
        return value.strip()

    @staticmethod
    def _normalized_plan_id(request: BrainRequest) -> str:
        value = request.metadata.get("research_plan_id")
        if not isinstance(value, str) or not value.strip():
            raise ResearchError("Research plan execution ID cannot be empty.")
        return value.strip()


#: A resumable execution is one that was started and has not closed. Cancelled,
#: completed and failed executions are absent on purpose: restarting a process
#: is not an event that reopens them.
_RESUMABLE_EXECUTION_STATUSES = frozenset(
    {
        ResearchPlanExecutionStatus.RUNNING,
        ResearchPlanExecutionStatus.INTERRUPTED,
    }
)


#: The statuses that end a continuation on sight. Running is absent because it
#: is the only one that means carrying on is still an option; ready is absent
#: because an unstarted execution has nothing to continue and is refused by the
#: ordinary advance instead.
_CONTINUATION_HALTS = {
    ResearchPlanExecutionStatus.COMPLETED: (ResearchContinuationStopReason.COMPLETED),
    ResearchPlanExecutionStatus.FAILED: ResearchContinuationStopReason.FAILED,
    ResearchPlanExecutionStatus.BLOCKED: ResearchContinuationStopReason.BLOCKED,
    ResearchPlanExecutionStatus.INTERRUPTED: (
        ResearchContinuationStopReason.INTERRUPTED
    ),
    ResearchPlanExecutionStatus.CANCELLED: (ResearchContinuationStopReason.CANCELLED),
}
