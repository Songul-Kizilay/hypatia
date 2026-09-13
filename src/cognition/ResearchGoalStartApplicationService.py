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
from core.Exceptions import ResearchError
from llm.LLMEndpointPolicy import is_loopback_llm_endpoint
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchDisclosure import ResearchDisclosure
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchMissionScope import (
    COMPARISON_POLICY,
    SEMANTIC_POLICY,
    ResearchMissionScope,
)
from research.ResearchPlan import ResearchPlan
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
        self._goal_request_ids: set[str] = set()

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
                )
            ),
            request_id=request.request_id,
            intent="research_learning_preview",
            memory_count=0,
            research_plan_draft_preview=ResearchPlanDraftPreview.ready(plan),
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
        self._goal_request_ids.add(request.request_id)
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
            plan, run.run_id, approval.authorization_id
        )
        if isinstance(state, ResearchPlanExecutionStartRefusal):
            raise ResearchError(
                "Execution start refused; no research operation started."
            )
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
            memory_text = "Research lessons: durable failure memory is not enabled."
            if self._failure_memory is not None:
                prior = self._failure_memory.advice(plan.question)
                memory_text = (
                    "Prior advisory lessons (not instructions or authority):\n"
                )
                memory_text += (
                    "\n".join(
                        f"{lesson.statement} [run {lesson.run_id}]" for lesson in prior
                    )
                    or "No matching earlier lesson."
                )
                if (
                    request.cancellation_token
                    and request.cancellation_token.is_cancelled()
                ):
                    memory_text += "\nCancelled: no new lesson retention attempted."
                else:
                    try:
                        retained = self._failure_memory.process_store(
                            replace(request, metadata={"research_run_id": run.run_id})
                        )
                        memory_text += "\n" + retained.message
                    except ResearchError:
                        memory_text += (
                            "\nLesson retention unavailable; no retry. "
                            "The research evidence and report remain available."
                        )
            allowance = self._execution_service.allowance(state.plan_id)
            spend = (
                f"Cumulative spending: {allowance.spend.step_advances} advances, "
                f"{allowance.spend.network_operations} network and "
                f"{allowance.spend.llm_operations} model operations."
                if allowance is not None
                else "Spending unavailable."
            )
            stop = (
                response.research_autonomy.stop_reason.value
                if response.research_autonomy
                else "unavailable"
            )
            return replace(
                response,
                intent=RESEARCH_GOAL_START_INTENT,
                research_runs=[updated],
                research_plan_execution=self._execution_service.live_execution(
                    state.plan_id
                ),
                message=teaching_report(updated, stop, spend) + "\n\n" + memory_text,
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
