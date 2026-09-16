"""One explicitly authorized goal start; no execution loop or new run store."""

from dataclasses import replace
from threading import Lock

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from cognition.FailureMemoryApplicationService import FailureMemoryApplicationService
from cognition.ResearchAutonomyApplicationService import (
    RESEARCH_AUTONOMY_RUN_INTENT,
    ResearchAutonomyApplicationService,
)
from cognition.ResearchPlanAuthorizationApplicationService import (
    ResearchPlanAuthorizationApplicationService,
)
from cognition.ResearchPlanExecutionApplicationService import (
    ResearchPlanExecutionApplicationService,
)
from core.CancellationSignal import CancellationToken
from core.Exceptions import ResearchError
from llm.LLMEndpointPolicy import is_loopback_llm_endpoint
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchDisclosure import ResearchDisclosure
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchExecutionAllowance import ResearchExecutionAllowance
from research.ResearchMissionScope import (
    COMPARISON_POLICY,
    SEMANTIC_POLICY,
    ResearchMissionScope,
)
from research.ResearchPlan import ResearchPlan
from research.ResearchPlanDigest import plan_digest
from research.ResearchPlanDraftPreview import ResearchPlanDraftPreview
from research.ResearchPlanDraftService import ResearchPlanDraftService
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepCapability import ResearchPlanStepCapability as Cap
from research.ResearchRunManager import ResearchRunManager
from research.ResearchTeachingReport import teaching_report
from research.SemanticMissionPolicy import SemanticMissionPolicy
from research.StartsResearchPlanExecution import ResearchPlanExecutionStartRefusal

RESEARCH_GOAL_START_INTENT = "research_goal_start"
OPENING_SCOPE = "local_search_and_selected_provider_discovery"
EVIDENCE_SCOPE = "selected_provider_reference_evidence"
COMPARISON_SCOPE = "selected_provider_reference_comparison"
LEARNING_SCOPE = "bounded_semantic_learning_research"
MISSION_RECOVERY_START_INTENT = "research_mission_recovery_start"
MISSION_COMPARISON_REVIEW_INTENT = "research_mission_comparison_review"


class ResearchGoalStartApplicationService:
    """The human-facing start boundary; never passed into the scheduler."""

    def __init__(
        self,
        execution: ResearchPlanExecutionApplicationService,
        autonomy: ResearchAutonomyApplicationService,
        *,
        research_run_manager: ResearchRunManager | None,
        authorizations: ResearchPlanAuthorizationApplicationService | None,
        discovery_providers: frozenset[ResearchDiscoveryProviderName],
        evidence_available: bool = False,
        semantic_destination: tuple[str, str] | None = None,
        failure_memory: FailureMemoryApplicationService | None = None,
    ) -> None:
        self._execution_service = execution
        self._autonomy = autonomy
        self._runs = research_run_manager
        self._authorizations = authorizations
        self._discovery_providers = discovery_providers
        self._evidence_available = evidence_available
        self._semantic_destination = semantic_destination
        self._failure_memory = failure_memory
        self._goal_lock = Lock()
        self._mission_recovery_attempted = False
        # The autonomy stop reason of each mission this session ran or resumed,
        # so its report can be re-rendered from canonical state after a review.
        self._mission_stop_reasons: dict[str, str] = {}
        self._goal_request_ids = set(
            self._execution_service.restored_mission_request_ids()
        )

    @staticmethod
    def is_goal_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") in {
            RESEARCH_GOAL_START_INTENT,
            "research_learning_preview",
        }

    def process_goal(self, request: BrainRequest) -> BrainResponse:
        """One human goal-start action approves a bounded derivation template.

        Consent names the selected provider, scope and cumulative budget.
        Only the semantic learning scope can disclose its own later evidence to
        the exact approved model. Targets remain excluded. No new execution loop
        or store is introduced. The research run stays collecting, not verified.
        """
        if not self._goal_lock.acquire(blocking=False):
            return self._goal_refusal(request, "Another goal start is in progress.")
        try:
            if request.metadata.get("intent") == "research_learning_preview":
                return self._preview_learning(request)
            return self._start_goal(request)
        except ResearchError as error:
            return self._goal_refusal(request, str(error))
        finally:
            self._goal_lock.release()

    def _preview_learning(self, request: BrainRequest) -> BrainResponse:
        """Configuration disclosure and inert canonical plan; no approval/write/call."""
        if self._semantic_destination is None:
            raise ResearchError(
                "Configure and enable a model before semantic research."
            )
        if set(request.metadata) != {
            "intent",
            "discovery_provider",
            "research_autonomy_budget",
        }:
            raise ResearchError("Unsupported learning preview inputs.")
        endpoint, model = self._semantic_destination
        policy = SemanticMissionPolicy(
            endpoint,
            model,
            (
                ResearchDisclosure.LOCAL_ONLY
                if is_loopback_llm_endpoint(endpoint)
                else ResearchDisclosure.REMOTE_PERMITTED
            ),
        )
        preview = ResearchPlanDraftService().preview_question(
            request.message, request.metadata["discovery_provider"]
        )
        if preview.plan is None:
            raise ResearchError(preview.reason)
        provider = preview.plan.steps[1].discovery_provider
        if provider is None or provider not in self._discovery_providers:
            raise ResearchError("Selected discovery provider is unavailable.")
        scope = ResearchMissionScope(
            provider,
            source_policy=SEMANTIC_POLICY,
            max_sources=3,
            semantic_policy=policy,
        )
        plan = self._mission_plan(preview.plan, scope)
        budget = request.metadata.get("research_autonomy_budget")
        if (
            not isinstance(budget, ResearchAutonomyBudget)
            or self._authorizations is None
            or not self._authorizations.budget_fit_for(plan, budget).sufficient
        ):
            raise ResearchError(
                "Approval storage or sufficient mission budget unavailable."
            )
        return BrainResponse(
            message="\n".join(
                (
                    "Bounded text research — preview only; no calls or approval yet.",
                    f"Question: {plan.question}; provider: {scope.provider.value}.",
                    *policy.lines(),
                    f"Maximum: {budget.max_step_advances} advances, "
                    f"{budget.max_network_operations} network, "
                    f"{budget.max_llm_operations} "
                    f"model operations, {budget.max_seconds:g} seconds.",
                    "One confirmation starts the bounded journey. "
                    "No intermediate Continue. No target testing. "
                    "Results remain tentative and may be incomplete.",
                    *self._preview_advice_lines(plan.question),
                )
            ),
            request_id=request.request_id,
            intent="research_learning_preview",
            memory_count=0,
            research_plan_draft_preview=ResearchPlanDraftPreview.ready(plan),
        )

    def _preview_advice_lines(self, question: str) -> tuple[str, ...]:
        """Show matching prior lessons before approval, as advice only.

        The same read-only recall the report uses after a mission. It derives,
        stores and spends nothing, and it changes neither the plan nor the
        permission being previewed.
        """
        if self._failure_memory is None:
            return ()
        prior = self._failure_memory.advice(question)
        if not prior:
            return ()
        return (
            "Prior advisory lessons for this question (advice only; not "
            "instructions, authority or evidence):",
            *(f"{lesson.statement} [run {lesson.run_id}]" for lesson in prior),
        )

    @staticmethod
    def _mission_plan(
        plan: ResearchPlan, mission_scope: ResearchMissionScope
    ) -> ResearchPlan:
        policy = mission_scope.semantic_policy
        return replace(
            plan,
            steps=plan.steps
            + tuple(
                ResearchPlanStep(
                    step_id=f"mission-{index}-{capability.value}",
                    instruction=(
                        "Derive from this mission's preceding observation only: "
                        + capability.value
                    ),
                    capability=capability,
                    semantic_mission_policy=(
                        policy
                        if capability is Cap.SEMANTIC_EVIDENCE_COMPARISON
                        else None
                    ),
                )
                for index, capability in enumerate(mission_scope.capabilities[2:])
            ),
            mission_scope=mission_scope,
        )

    @classmethod
    def _rebuild_mission_plan(
        cls, question: str, mission_scope: ResearchMissionScope
    ) -> ResearchPlan:
        """Recreate a content-identical plan; its fresh instance ID is ignored."""
        preview = ResearchPlanDraftService().preview_question(
            question, mission_scope.provider.value
        )
        if preview.plan is None:
            raise ResearchError("Mission recovery cannot rebuild its approved plan.")
        return cls._mission_plan(preview.plan, mission_scope)

    def resume_restored_learning_missions(
        self, cancellation_token: CancellationToken | None = None
    ) -> tuple[str, ...]:
        """Resume only durable, exact semantic missions after application restart.

        This is intentionally not a generic resume path. A legacy snapshot or a
        checkpoint with transient preview/model output stays visible and stopped.
        """
        with self._goal_lock:
            if self._mission_recovery_attempted:
                return ()
            self._mission_recovery_attempted = True
        resumed: list[str] = []
        for snapshot in self._execution_service.restored_mission_executions():
            if cancellation_token is not None and cancellation_token.is_cancelled():
                # Cancelled before this mission: it stays restored and visible,
                # and the once-per-process pass does not reopen on request.
                self._execution_service.record_mission_recovery_refusal(
                    snapshot.plan_id,
                    "Startup mission recovery was cancelled before this mission; "
                    "no source or model call was replayed.",
                )
                continue
            if refusal := self._recovery_precondition_refusal(snapshot):
                self._execution_service.record_mission_recovery_refusal(
                    snapshot.plan_id, refusal
                )
                continue
            scope = snapshot.mission_scope
            assert scope is not None
            assert snapshot.research_run_id is not None
            assert snapshot.allowance is not None
            try:
                plan = self._rebuild_mission_plan(snapshot.question, scope)
                if plan_digest(plan) != snapshot.mission_plan_digest:
                    continue
                state = self._execution_service.rebind_restored(
                    plan,
                    snapshot.research_run_id,
                    snapshot.plan_id,
                )
                if isinstance(state, ResearchPlanExecutionStartRefusal):
                    self._execution_service.record_mission_recovery_refusal(
                        snapshot.plan_id,
                        state.reason,
                    )
                    continue
                allowance = snapshot.allowance
                remaining = ResearchAutonomyBudget(
                    max_step_advances=allowance.remaining_step_advances,
                    max_network_operations=allowance.remaining_network_operations,
                    max_llm_operations=allowance.remaining_llm_operations,
                    max_seconds=allowance.remaining_seconds,
                )
                resume = BrainRequest(
                    message="Resume exact durable research mission",
                    source="restart_recovery",
                    request_id=f"restart:{snapshot.plan_id}",
                    cancellation_token=cancellation_token,
                    metadata={
                        "intent": RESEARCH_AUTONOMY_RUN_INTENT,
                        "research_plan_id": snapshot.plan_id,
                        "research_autonomy_budget": remaining,
                    },
                )
                response = self._autonomy.process_run(resume)
                self._retain_recovered_report(
                    resume, snapshot.question, snapshot.research_run_id, response
                )
                resumed.append(snapshot.plan_id)
            except ResearchError as error:
                # The snapshot remains restored and status-reportable. A restart
                # cannot transform a mismatch into new provider/model authority.
                self._execution_service.record_mission_recovery_refusal(
                    snapshot.plan_id,
                    str(error),
                )
                continue
        return tuple(resumed)

    @staticmethod
    def is_mission_recovery_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == MISSION_RECOVERY_START_INTENT

    def process_mission_recovery(self, request: BrainRequest) -> BrainResponse:
        """Run the one startup recovery pass a deferring caller postponed.

        This is the same exact-mission resume that initialization would have
        performed, not a new permission: it runs at most once per process, uses
        each mission's remaining recorded allowance, and a repeat does nothing.
        """
        already_attempted = self._mission_recovery_attempted
        token = request.cancellation_token
        resumed = self.resume_restored_learning_missions(token)
        if already_attempted:
            message = (
                "Startup mission recovery already ran in this session; nothing "
                "was resumed again."
            )
        else:
            message = (
                f"Startup mission recovery finished: {len(resumed)} mission(s) "
                "resumed within their recorded allowance. Use Missions recovered "
                "at startup to read reports or refusals."
            )
            if token is not None and token.is_cancelled():
                message += (
                    " Recovery was cancelled: spending already recorded is kept "
                    "and remaining missions stay restored without replay."
                )
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent=MISSION_RECOVERY_START_INTENT,
            memory_count=0,
        )

    def _retain_recovered_report(
        self,
        resume: BrainRequest,
        question: str,
        run_id: str,
        response: BrainResponse,
    ) -> None:
        """Keep the report and lessons a live mission would keep for this work.

        Only an autonomy result — the same condition under which a live mission
        renders its report — yields a report.  Rendering reads canonical run,
        checkpoint and allowance state; the report is kept in memory for this
        session only.  Lessons go through the same opted-in failure memory as a
        live mission, whose stable lesson IDs make a repeated retention a no-op.
        Neither calls a provider or model or spends budget.
        """
        if response.research_autonomy is None or self._runs is None:
            return
        plan_id = resume.metadata["research_plan_id"]
        assert isinstance(plan_id, str)
        self._mission_stop_reasons[plan_id] = (
            response.research_autonomy.stop_reason.value
        )
        report = teaching_report(
            self._runs.get(run_id),
            response.research_autonomy.stop_reason.value,
            self._spend_text(plan_id),
            checkpoint=self._execution_service.mission_checkpoint(plan_id),
        )
        self._execution_service.record_mission_recovery_report(
            plan_id,
            report + "\n\n" + self._lesson_text(resume, question, run_id),
        )

    def _lesson_text(self, request: BrainRequest, question: str, run_id: str) -> str:
        """Show prior advice, then retain this run's lessons once, as advice only."""
        if self._failure_memory is None:
            return "Research lessons: durable failure memory is not enabled."
        prior = self._failure_memory.advice(question)
        memory_text = "Prior advisory lessons (not instructions or authority):\n"
        memory_text += (
            "\n".join(f"{lesson.statement} [run {lesson.run_id}]" for lesson in prior)
            or "No matching earlier lesson."
        )
        if request.cancellation_token and request.cancellation_token.is_cancelled():
            return memory_text + "\nCancelled: no new lesson retention attempted."
        try:
            retained = self._failure_memory.process_store(
                replace(request, metadata={"research_run_id": run_id})
            )
        except ResearchError:
            return memory_text + (
                "\nLesson retention unavailable; no retry. "
                "The research evidence and report remain available."
            )
        return memory_text + "\n" + retained.message

    @staticmethod
    def is_mission_comparison_review_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == MISSION_COMPARISON_REVIEW_INTENT

    def process_mission_comparison_review(self, request: BrainRequest) -> BrainResponse:
        """Load one mission's comparison-review target from canonical state only.

        The run, checkpoint note and spend come from the execution service and
        the run store; the report is re-rendered by the existing teaching report,
        so a recorded review changes what it shows only through canonical goal,
        explanation and readiness recomputation.  Nothing is written, fetched,
        resumed or called.
        """

        def refusal(message: str) -> BrainResponse:
            return BrainResponse(
                message=message,
                request_id=request.request_id,
                intent=MISSION_COMPARISON_REVIEW_INTENT,
                memory_count=0,
                success=False,
            )

        plan_id = request.metadata.get("research_plan_id")
        if not isinstance(plan_id, str) or not plan_id.strip():
            return refusal("A mission plan ID is required.")
        plan_id = plan_id.strip()
        if self._runs is None:
            return refusal("Research run persistence is unavailable.")
        execution = self._execution_service
        checkpoint = execution.mission_checkpoint(plan_id)
        allowance = execution.allowance(plan_id)
        stop = self._mission_stop_reasons.get(plan_id, "")
        restored = execution.restored_execution(plan_id)
        if restored is not None:
            # A restored execution was not resumed this session, so no autonomy
            # stop reason exists to recompute its outcome from; it is refused.
            checkpoint = restored.mission_checkpoint
            allowance = restored.allowance
        run_id = execution.mission_run_id(plan_id)
        if checkpoint is None or not run_id or not stop:
            return refusal(
                "This mission's canonical result is unavailable in this session; "
                "no comparison review target was loaded."
            )
        try:
            run = self._runs.get(run_id)
        except ResearchError:
            return refusal("This mission's research run is unavailable.")
        note_id = checkpoint.semantic_note_id
        header = (
            f"Mission comparison review target: plan {plan_id}, run {run.run_id}, "
            f"comparison note {note_id or 'none recorded'}. Nothing is recorded "
            "until an operator review is previewed and confirmed."
        )
        return BrainResponse(
            message=header
            + "\n\n"
            + teaching_report(
                run,
                stop,
                self._spend_text_for(allowance),
                checkpoint=checkpoint,
            ),
            request_id=request.request_id,
            intent=MISSION_COMPARISON_REVIEW_INTENT,
            memory_count=0,
            research_runs=[run],
            research_mission_comparison_note_id=note_id,
        )

    def _spend_text(self, plan_id: str) -> str:
        return self._spend_text_for(self._execution_service.allowance(plan_id))

    @staticmethod
    def _spend_text_for(allowance: ResearchExecutionAllowance | None) -> str:
        return (
            f"Cumulative spending: {allowance.spend.step_advances} advances, "
            f"{allowance.spend.network_operations} network and "
            f"{allowance.spend.llm_operations} model operations."
            if allowance is not None
            else "Spending unavailable."
        )

    def _recovery_precondition_refusal(self, snapshot: object) -> str | None:
        """Explain a restart refusal before rebuilding or spending anything.

        A restored mission with unavailable current composition was already
        fail-closed.  Recording that reason makes the same safe decision
        operator-visible instead of looking like no mission was found.  This
        helper neither changes the snapshot nor retries the work.
        """
        from research.ResearchPlanExecutionSnapshot import ResearchPlanExecutionSnapshot

        if not isinstance(snapshot, ResearchPlanExecutionSnapshot):
            return (
                "Mission recovery record is invalid; no source or model call "
                "was replayed."
            )
        scope = snapshot.mission_scope
        if scope is None or scope.source_policy != SEMANTIC_POLICY:
            return (
                "Mission recovery scope is not a supported bounded semantic "
                "mission; no source or model call was replayed."
            )
        policy = scope.semantic_policy
        if policy is None:
            return (
                "Mission recovery lacks its recorded semantic policy; no source "
                "or model call was replayed."
            )
        if self._runs is None:
            return (
                "Mission recovery lacks durable research-run access; no source "
                "or model call was replayed."
            )
        if self._semantic_destination is None:
            return (
                "Mission recovery has no configured model destination; no source "
                "or model call was replayed."
            )
        if (policy.endpoint, policy.model) != self._semantic_destination:
            return (
                "Configured model destination differs from the exact recorded "
                "mission destination; no source or model call was replayed."
            )
        if snapshot.research_run_id is None:
            return (
                "Mission recovery lacks its recorded research-run binding; no "
                "source or model call was replayed."
            )
        if snapshot.allowance is None:
            return (
                "Mission recovery lacks its recorded cumulative allowance; no "
                "source or model call was replayed."
            )
        return None

    def _start_goal(self, request: BrainRequest) -> BrainResponse:
        allowed = {
            "intent",
            "research_goal_scope",
            "discovery_provider",
            "research_autonomy_budget",
        }
        scope = request.metadata.get("research_goal_scope")
        learning = scope == LEARNING_SCOPE
        if learning:
            allowed.add("semantic_mission_policy")
        if (
            set(request.metadata) != allowed
            or not isinstance(scope, str)
            or scope
            not in {OPENING_SCOPE, EVIDENCE_SCOPE, COMPARISON_SCOPE, LEARNING_SCOPE}
        ):
            raise ResearchError("Goal start requires an explicit supported scope.")
        evidence_mission = scope in {EVIDENCE_SCOPE, COMPARISON_SCOPE, LEARNING_SCOPE}
        comparison_mission = scope == COMPARISON_SCOPE
        if evidence_mission and not self._evidence_available:
            raise ResearchError(
                "Source acquisition is unavailable; mission not started."
            )
        budget = request.metadata.get("research_autonomy_budget")
        if not isinstance(budget, ResearchAutonomyBudget) or (
            not learning and budget.max_llm_operations
        ):
            raise ResearchError(
                "Opening requires an explicit budget with zero model calls."
            )
        policy = request.metadata.get("semantic_mission_policy") if learning else None
        if learning and (
            not isinstance(policy, SemanticMissionPolicy)
            or self._semantic_destination != (policy.endpoint, policy.model)
        ):
            raise ResearchError("Exact approved semantic destination is unavailable.")
        if self._runs is None or self._authorizations is None:
            raise ResearchError("Durable research approval is unavailable.")
        if request.cancellation_token and request.cancellation_token.is_cancelled():
            raise ResearchError("Goal start cancelled before research began.")
        if (
            not isinstance(request.request_id, str)
            or not request.request_id.strip()
            or len(request.request_id) > 200
            or request.request_id in self._goal_request_ids
            or len(self._goal_request_ids) >= 50
        ):
            raise ResearchError(
                "Duplicate goal request or session goal capacity reached."
            )
        try:
            provider = ResearchDiscoveryProviderName(
                request.metadata["discovery_provider"]
            )
        except ValueError, TypeError:
            raise ResearchError("Choose an available research provider.") from None
        if provider not in self._discovery_providers:
            raise ResearchError("Selected research provider is unavailable.")
        preview = ResearchPlanDraftService().preview_question(
            request.message, provider.value
        )
        if preview.plan is None:
            raise ResearchError("Research goal cannot form a valid opening plan.")
        plan = preview.plan
        if evidence_mission:
            mission_scope = (
                ResearchMissionScope(
                    provider, source_policy=COMPARISON_POLICY, max_sources=2
                )
                if comparison_mission
                else ResearchMissionScope(provider)
            )
            if isinstance(policy, SemanticMissionPolicy):
                mission_scope = ResearchMissionScope(
                    provider,
                    source_policy=SEMANTIC_POLICY,
                    max_sources=3,
                    semantic_policy=policy,
                )
            plan = self._mission_plan(plan, mission_scope)
        if not self._authorizations.budget_fit_for(plan, budget).sufficient:
            raise ResearchError("Budget cannot cover the opening; nothing was started.")
        run = self._runs.create(plan.question)
        approval = self._authorizations.record_for_plan(
            plan,
            run.run_id,
            disclosure=(
                policy.disclosure
                if isinstance(policy, SemanticMissionPolicy)
                else ResearchDisclosure.NONE
            ),
            budget=budget,
        )
        if approval is None:
            raise ResearchError(
                "Approval was not saved; no research operation started."
            )
        state = self._execution_service.start_for_plan(
            plan,
            run.run_id,
            approval.authorization_id,
            mission_request_id=request.request_id,
        )
        if isinstance(state, ResearchPlanExecutionStartRefusal):
            raise ResearchError("Execution start refused; " + state.reason)
        # The request becomes a duplicate only after its mission execution has
        # crossed the durable snapshot boundary. A failed start must not claim
        # restart-safe idempotency or prevent an operator from retrying it.
        self._goal_request_ids.add(request.request_id)
        response = self._autonomy.process_run(
            replace(
                request,
                metadata={
                    "intent": RESEARCH_AUTONOMY_RUN_INTENT,
                    "research_plan_id": state.plan_id,
                    "research_autonomy_budget": budget,
                },
            )
        )
        updated = self._runs.get(run.run_id)
        if learning:
            memory_text = self._lesson_text(request, plan.question, run.run_id)
            spend = self._spend_text(state.plan_id)
            stop = (
                response.research_autonomy.stop_reason.value
                if response.research_autonomy
                else "unavailable"
            )
            if response.research_autonomy:
                self._mission_stop_reasons[state.plan_id] = stop
            return replace(
                response,
                intent=RESEARCH_GOAL_START_INTENT,
                research_runs=[updated],
                research_plan_execution=self._execution_service.live_execution(
                    state.plan_id
                ),
                message=(
                    teaching_report(
                        updated,
                        stop,
                        spend,
                        checkpoint=self._execution_service.mission_checkpoint(
                            state.plan_id
                        ),
                    )
                    + "\n\n"
                    + memory_text
                ),
            )
        count = sum(len(record.candidates) for record in updated.discoveries)
        if evidence_mission:
            boundary = (
                "Remaining human boundary: semantic contradiction investigation, "
                "follow-up research, replanning, completion evaluation and a cited "
                "answer are not yet mission-driven.\n"
                if comparison_mission
                else "Remaining human boundary: comparison and contradictions, "
                "follow-up research and replanning are not yet mission-driven. "
                "Completion evaluation and a cited answer remain incomplete.\n"
            )
            comparisons = "\n\n".join(note.text for note in updated.comparison_notes)
            return replace(
                response,
                intent=RESEARCH_GOAL_START_INTENT,
                research_runs=[updated],
                research_plan_execution=self._execution_service.live_execution(
                    state.plan_id
                ),
                message=(
                    "Research incomplete — bounded reference research slice.\n\n"
                    f"Research question: {updated.question}\n"
                    f"Discovery: {count} candidate(s); "
                    f"accepted sources: {len(updated.sources)}; "
                    f"recorded evidence: {len(updated.evidence)}.\n"
                    f"Recorded comparisons: {len(updated.comparison_notes)}.\n"
                    "Evidence validation means exact-source grounding, not truth. "
                    "Selection is lexical matching, not model reasoning.\n"
                    "One original approval and one cumulative execution allowance; "
                    "no derived approval, refetch or caller-side Continue.\n"
                    + boundary
                    + "\n"
                    + comparisons
                    + "\n\n"
                    + "Research trace:\n"
                    + response.message
                ),
            )
        return replace(
            response,
            intent=RESEARCH_GOAL_START_INTENT,
            research_runs=[updated],
            research_plan_execution=self._execution_service.live_execution(
                state.plan_id
            ),
            message=(
                "Research incomplete — autonomous opening only.\n\n"
                f"Research question: {updated.question}\n"
                "Executive answer: insufficient evidence to answer the question.\n"
                f"Discovery: {count} unaccepted candidate(s) from {provider.value}.\n"
                "Evidence quality: no sources fetched or evidence validated here.\n"
                "Conflicts and unknowns: not evaluated, not proven absent.\n"
                "Remaining: source selection/fetch, evidence, comparison, follow-up "
                "research, replanning and a cited answer.\n"
                "Limitation: this opening scope does not authorize those later stages; "
                "no new authority was created from discovery results.\n\n"
                "Research trace:\n" + response.message
            ),
        )

    @staticmethod
    def _goal_refusal(request: BrainRequest, reason: str) -> BrainResponse:
        return BrainResponse(
            message="Research goal not advanced. " + reason,
            request_id=request.request_id,
            intent=RESEARCH_GOAL_START_INTENT,
            memory_count=0,
            success=False,
        )
