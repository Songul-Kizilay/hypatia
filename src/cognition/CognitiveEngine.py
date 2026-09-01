"""Cognitive orchestration entry point."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from brain.BrainContext import BrainContext
from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from brain.BrainRouter import BrainRouter
from cognition.BackgroundResearchSchedulerApplicationService import (
    BackgroundResearchSchedulerApplicationService,
)
from cognition.CalibrationApplicationService import (
    CalibrationApplicationService,
)
from cognition.ConversationResearchClaimGuard import (
    ConversationResearchClaimGuard,
)
from cognition.CuriosityApplicationService import (
    CuriosityApplicationService,
)
from cognition.FailureMemoryApplicationService import (
    FailureMemoryApplicationService,
)
from cognition.HypothesisApplicationService import (
    HypothesisApplicationService,
)
from cognition.KnowledgeReconciliationApplicationService import (
    KnowledgeReconciliationApplicationService,
)
from cognition.LearnedMemoryAuditApplicationService import (
    LearnedMemoryAuditApplicationService,
)
from cognition.LearnedMemoryContextService import LearnedMemoryContextService
from cognition.LLMConversationHistoryBuilder import (
    build_llm_conversation_history,
)
from cognition.PairedProviderQualityApplicationService import (
    PairedProviderQualityApplicationService,
)
from cognition.ProviderComparisonApplicationService import (
    ProviderComparisonApplicationService,
)
from cognition.ProviderQualityApplicationService import (
    ProviderQualityApplicationService,
)
from cognition.ReflectionApplicationService import (
    ReflectionApplicationService,
)
from cognition.ResearchAuthoredHistoryApplicationService import (
    ResearchAuthoredHistoryApplicationService,
)
from cognition.ResearchAutonomyApplicationService import (
    ResearchAutonomyApplicationService,
)
from cognition.ResearchHonestyApplicationService import (
    ResearchHonestyApplicationService,
)
from cognition.ResearchOverviewApplicationService import (
    ResearchOverviewApplicationService,
)
from cognition.ResearchPlanAuthorizationApplicationService import (
    ResearchPlanAuthorizationApplicationService,
)
from cognition.ResearchPlanExecutionApplicationService import (
    ResearchPlanExecutionApplicationService,
)
from cognition.ResearchPlanPreviewApplicationService import (
    ResearchPlanPreviewApplicationService,
)
from cognition.ResearchSourceAcceptanceService import (
    ResearchSourceAcceptanceService,
)
from cognition.SecurityAgentApplicationService import (
    SecurityAgentApplicationService,
)
from cognition.SourceIngestionEvents import (
    IngestionFailureKind,
    SourceIngestionEvents,
)
from cognition.SourceReputationApplicationService import (
    SourceReputationApplicationService,
)
from cognition.VulnerabilityGraphApplicationService import (
    VulnerabilityGraphApplicationService,
)
from core.Exceptions import (
    KnowledgeError,
    MemoryError,
    PlannerError,
    ResearchError,
    SessionDeleteEventError,
    SessionError,
)
from eventbus.EventBus import EventBus
from knowledge.KnowledgeCitation import KnowledgeCitation
from knowledge.KnowledgeContextPrompt import (
    KNOWLEDGE_CONTEXT_SYSTEM_INSTRUCTION,
    build_knowledge_context_prompt,
)
from knowledge.KnowledgeEngine import KnowledgeEngine
from llm.LLMProvider import LLMError, LLMProvider
from memory.HybridSemanticMemoryRanker import HybridSemanticMemoryRanker
from memory.LearnedMemoryCandidateExtractionError import (
    LearnedMemoryCandidateExtractionError,
)
from memory.LearnedMemoryCandidateExtractor import LearnedMemoryCandidateExtractor
from memory.LearnedMemoryCandidatePersistence import (
    persist_learned_memory_candidate_batch,
)
from memory.LearnedMemoryContext import (
    build_learned_memory_augmented_prompt,
)
from memory.LearnedMemorySelector import LearnedMemorySelector
from memory.MemoryManager import MemoryManager
from memory.MemoryRecord import MemoryRecord
from memory.NoOpLearnedMemoryCandidateExtractor import (
    NoOpLearnedMemoryCandidateExtractor,
)
from memory.SemanticMemoryIndexRuntime import SemanticMemoryIndexRuntime
from memory.SemanticMemoryMatch import SemanticMemoryMatch
from memory.SessionMemoryPolicy import SessionMemoryPolicy
from research.AcceptedSourceListingStepOperation import (
    AcceptedSourceListingStepOperation,
)
from research.BackgroundTaskStore import BackgroundTaskStore
from research.ClaimContradictionStepOperation import (
    ClaimContradictionStepOperation,
)
from research.ClaimCreationStepOperation import ClaimCreationStepOperation
from research.CuriosityQuestionStore import CuriosityQuestionStore
from research.EvidenceIntegrityCheckStepOperation import (
    EvidenceIntegrityCheckStepOperation,
)
from research.EvidenceRecordingStepOperation import (
    EvidenceRecordingStepOperation,
)
from research.FailureLessonStore import FailureLessonStore
from research.HypothesisStore import HypothesisStore
from research.LocalKnowledgeSearchStepOperation import (
    LocalKnowledgeSearchStepOperation,
)
from research.ReflectionReportStore import ReflectionReportStore
from research.ResearchClaimContradictionCandidate import (
    ResearchClaimContradictionCandidate,
)
from research.ResearchClaimContradictionProposalPreview import (
    ResearchClaimContradictionProposalPreview,
)
from research.ResearchClaimContradictionProposalProvider import (
    ResearchClaimContradictionProposalError,
    ResearchClaimContradictionProposalProvider,
)
from research.ResearchClaimRecord import ResearchClaimRecord
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchEvidenceIntegrityAuditor import ResearchEvidenceIntegrityAuditor
from research.ResearchExecutionStore import ResearchExecutionStore
from research.ResearchFailureLesson import ResearchFailureLesson
from research.ResearchPlanAuthorizationStore import (
    ResearchPlanAuthorizationStore,
)
from research.ResearchPlanDraftService import ResearchPlanDraftService
from research.ResearchPlanOperationRegistry import (
    ResearchPlanOperationRegistry,
)
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchRun import ResearchRun
from research.ResearchRunCompletionStepOperation import (
    ResearchRunCompletionStepOperation,
)
from research.ResearchRunManager import ResearchRunManager
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSourceCandidate import ResearchSourceCandidate
from research.ResearchSourceContentRestorationStatus import (
    ResearchSourceContentRestorationStatus,
)
from research.ResearchSourceContentStore import ResearchSourceContentStore
from research.ResearchSourceDiscoveryProvider import ResearchSourceDiscoveryProvider
from research.ResearchSourceFetcher import ResearchSourceFetcher
from research.SourceAcceptStepOperation import SourceAcceptStepOperation
from research.SourceAssessmentStepOperation import (
    SourceAssessmentStepOperation,
)
from research.SourceComparisonStepOperation import (
    SourceComparisonStepOperation,
)
from research.SourceDiscoveryStepOperation import SourceDiscoveryStepOperation
from research.SourceFetchStepOperation import SourceFetchStepOperation
from research.SourceIdentity import identity_of
from research.SourceLoadStage import SourceLoadStage
from response.ResponseComposer import ResponseComposer
from security.VulnerabilityGraphStore import VulnerabilityGraphStore
from session.SessionCreateService import SessionCreateService
from session.SessionDeletePreviewService import SessionDeletePreviewService
from session.SessionDeleteService import SessionDeleteService
from session.SessionManager import SessionManager
from session.SessionRecord import SessionRecord
from session.SessionRenameTransactionService import SessionRenameTransactionService
from session.SessionUseService import SessionUseService

if TYPE_CHECKING:
    from planner.Planner import Planner


LLM_CONVERSATION_HISTORY_MAX_TURNS = 8
KNOWLEDGE_CONTEXT_MAX_RESULTS = 3
RESEARCH_CLAIM_CONTRADICTION_PROPOSAL_LIMIT = 10
RESEARCH_CLAIM_CONTRADICTION_PROPOSAL_MAX_CLAIMS = 50


class CognitiveEngine:
    """Coordinates the first knowledge-backed cognitive request flow."""

    def __init__(
        self,
        knowledge_engine: KnowledgeEngine,
        memory_manager: MemoryManager,
        planner: Planner,
        event_bus: EventBus,
        response_composer: ResponseComposer,
        session_manager: SessionManager,
        session_rename_service: SessionRenameTransactionService,
        llm_provider: LLMProvider | None = None,
        llm_history_max_turns: int | None = None,
        learned_memory_candidate_extractor: (
            LearnedMemoryCandidateExtractor | None
        ) = None,
        learned_memory_context_limit: int | None = None,
        learned_memory_selector: LearnedMemorySelector | None = None,
        semantic_memory_index_runtime: SemanticMemoryIndexRuntime | None = None,
        chat_semantic_memory_enabled: bool = False,
        research_source_fetcher: ResearchSourceFetcher | None = None,
        research_run_manager: ResearchRunManager | None = None,
        research_execution_store: ResearchExecutionStore | None = None,
        background_task_store: BackgroundTaskStore | None = None,
        curiosity_question_store: CuriosityQuestionStore | None = None,
        reflection_report_store: ReflectionReportStore | None = None,
        failure_lesson_store: FailureLessonStore | None = None,
        hypothesis_store: HypothesisStore | None = None,
        plan_authorization_store: ResearchPlanAuthorizationStore | None = None,
        vulnerability_graph_store: VulnerabilityGraphStore | None = None,
        research_source_discovery_provider: (
            ResearchSourceDiscoveryProvider | None
        ) = None,
        research_source_discovery_providers: (
            dict[ResearchDiscoveryProviderName, ResearchSourceDiscoveryProvider] | None
        ) = None,
        research_claim_contradiction_proposal_provider: (
            ResearchClaimContradictionProposalProvider | None
        ) = None,
        research_source_content_store: ResearchSourceContentStore | None = None,
        research_source_content_restoration_status: (
            ResearchSourceContentRestorationStatus | None
        ) = None,
        research_evidence_integrity_auditor: (
            ResearchEvidenceIntegrityAuditor | None
        ) = None,
        research_plan_draft_service: ResearchPlanDraftService | None = None,
    ) -> None:
        if llm_history_max_turns is not None and (
            isinstance(llm_history_max_turns, bool) or llm_history_max_turns <= 0
        ):
            raise ValueError(
                "llm_history_max_turns must be a positive integer or None."
            )
        self._knowledge_engine = knowledge_engine
        self._memory_manager = memory_manager
        self._planner = planner
        self._event_bus = event_bus
        self._response_composer = response_composer
        self._session_manager = session_manager
        self._session_create_service = SessionCreateService(session_manager)
        self._session_delete_preview_service = SessionDeletePreviewService(
            session_manager,
            memory_manager,
        )
        self._session_delete_service = SessionDeleteService(
            session_manager,
            memory_manager,
        )
        self._session_use_service = SessionUseService(session_manager)
        self._session_rename_service = session_rename_service
        self._llm_provider = llm_provider
        self._llm_history_max_turns = (
            LLM_CONVERSATION_HISTORY_MAX_TURNS
            if llm_history_max_turns is None
            else llm_history_max_turns
        )
        self._learned_memory_candidate_extractor = (
            learned_memory_candidate_extractor
            if learned_memory_candidate_extractor is not None
            else NoOpLearnedMemoryCandidateExtractor()
        )
        self._learned_memory_context_limit = learned_memory_context_limit
        self._learned_memory_selector = learned_memory_selector
        self._semantic_memory_index_runtime = semantic_memory_index_runtime
        self._chat_semantic_memory_enabled = chat_semantic_memory_enabled
        self._research_source_fetcher = research_source_fetcher
        self._research_source_acceptance_service = ResearchSourceAcceptanceService(
            knowledge_engine,
            research_run_manager,
            research_source_content_store,
            event_bus=event_bus,
        )
        self._research_run_manager = research_run_manager
        self._research_source_discovery_provider = research_source_discovery_provider
        self._research_source_discovery_providers = (
            research_source_discovery_providers or {}
        )
        self._research_claim_contradiction_proposal_provider = (
            research_claim_contradiction_proposal_provider
        )
        self._research_source_content_store = research_source_content_store
        self._research_overview_service = ResearchOverviewApplicationService(
            response_composer,
            research_run_manager,
            research_source_content_restoration_status,
            research_evidence_integrity_auditor,
        )
        self._research_authored_history_service = (
            ResearchAuthoredHistoryApplicationService(
                response_composer,
                research_run_manager,
            )
        )
        self._learned_memory_audit_service = LearnedMemoryAuditApplicationService(
            memory_manager,
            response_composer,
        )
        operation_registry = ResearchPlanOperationRegistry(
            {
                ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH: (
                    LocalKnowledgeSearchStepOperation(knowledge_engine)
                ),
            }
        )
        if research_run_manager is not None:
            operation_registry.register(
                ResearchPlanStepCapability.ACCEPTED_SOURCE_LISTING,
                AcceptedSourceListingStepOperation(research_run_manager),
            )
            operation_registry.register(
                ResearchPlanStepCapability.EVIDENCE_RECORDING,
                EvidenceRecordingStepOperation(
                    knowledge_engine,
                    research_run_manager,
                ),
            )
            operation_registry.register(
                ResearchPlanStepCapability.SOURCE_ASSESSMENT,
                SourceAssessmentStepOperation(research_run_manager),
            )
            operation_registry.register(
                ResearchPlanStepCapability.CLAIM_CREATION,
                ClaimCreationStepOperation(research_run_manager),
            )
            operation_registry.register(
                ResearchPlanStepCapability.CLAIM_CONTRADICTION,
                ClaimContradictionStepOperation(research_run_manager),
            )
            operation_registry.register(
                ResearchPlanStepCapability.SOURCE_COMPARISON,
                SourceComparisonStepOperation(research_run_manager),
            )
            operation_registry.register(
                ResearchPlanStepCapability.RESEARCH_RUN_COMPLETION,
                ResearchRunCompletionStepOperation(research_run_manager),
            )
            if research_evidence_integrity_auditor is not None:
                operation_registry.register(
                    ResearchPlanStepCapability.EVIDENCE_INTEGRITY_CHECK,
                    EvidenceIntegrityCheckStepOperation(
                        research_evidence_integrity_auditor,
                        research_run_manager,
                    ),
                )
            if research_source_discovery_provider is not None:
                operation_registry.register(
                    ResearchPlanStepCapability.SOURCE_DISCOVERY,
                    SourceDiscoveryStepOperation(
                        research_source_discovery_provider,
                        research_run_manager,
                        providers=research_source_discovery_providers,
                    ),
                )
            if research_source_fetcher is not None:
                operation_registry.register(
                    ResearchPlanStepCapability.SOURCE_FETCH,
                    SourceFetchStepOperation(
                        research_source_fetcher,
                        research_run_manager,
                    ),
                )
                operation_registry.register(
                    ResearchPlanStepCapability.SOURCE_ACCEPT,
                    SourceAcceptStepOperation(
                        research_source_fetcher,
                        self._research_source_acceptance_service,
                        research_run_manager,
                    ),
                )
        # Built before execution so it can be handed over as the narrow
        # consumption port. Approval still imports no execution or scheduling
        # service: the dependency runs one way, from execution to approval.
        self._plan_authorization_service: (
            ResearchPlanAuthorizationApplicationService | None
        ) = None
        if research_run_manager is not None:
            self._plan_authorization_service = (
                ResearchPlanAuthorizationApplicationService(
                    research_run_manager,
                    response_composer,
                    authorization_store=plan_authorization_store,
                    event_bus=event_bus,
                )
            )

        self._research_plan_execution_service = ResearchPlanExecutionApplicationService(
            response_composer,
            operation_registry=operation_registry,
            event_bus=event_bus,
            execution_store=research_execution_store,
            # Attached wherever approvals are kept, which is the same condition
            # under which any start control exists. With approvals kept, a plan
            # can only start by spending one.
            authorization_consumer=(
                self._plan_authorization_service
                if plan_authorization_store is not None
                else None
            ),
        )
        self._research_autonomy_service = ResearchAutonomyApplicationService(
            self._research_plan_execution_service,
            response_composer,
            event_bus=event_bus,
        )
        self._background_research_scheduler = (
            BackgroundResearchSchedulerApplicationService(
                self._research_autonomy_service,
                response_composer,
                executions=self._research_plan_execution_service,
                task_store=background_task_store,
                event_bus=event_bus,
            )
        )
        self._research_honesty_service = ResearchHonestyApplicationService(
            response_composer,
            run_manager=research_run_manager,
        )
        self._conversation_research_claim_guard = ConversationResearchClaimGuard()
        self._curiosity_service: CuriosityApplicationService | None = None
        if research_run_manager is not None:
            self._curiosity_service = CuriosityApplicationService(
                research_run_manager,
                response_composer,
                question_store=curiosity_question_store,
                hypothesis_store=hypothesis_store,
                authorization_service=self._plan_authorization_service,
                execution_starter=self._research_plan_execution_service,
                event_bus=event_bus,
            )
        self._reflection_service: ReflectionApplicationService | None = None
        if research_run_manager is not None:
            self._reflection_service = ReflectionApplicationService(
                research_run_manager,
                response_composer,
                report_store=reflection_report_store,
                hypothesis_store=hypothesis_store,
                event_bus=event_bus,
            )
        self._failure_memory_service: FailureMemoryApplicationService | None = None
        if research_run_manager is not None:
            self._failure_memory_service = FailureMemoryApplicationService(
                research_run_manager,
                response_composer,
                lesson_store=failure_lesson_store,
                hypothesis_store=hypothesis_store,
                event_bus=event_bus,
            )
        self._calibration_service: CalibrationApplicationService | None = None
        if research_run_manager is not None:
            self._calibration_service = CalibrationApplicationService(
                research_run_manager,
                response_composer,
                event_bus=event_bus,
            )
        self._source_reputation_service: SourceReputationApplicationService | None = (
            None
        )
        self._provider_quality_service: ProviderQualityApplicationService | None = None
        self._paired_provider_quality_service: (
            PairedProviderQualityApplicationService | None
        ) = None
        self._provider_comparison_service: (
            ProviderComparisonApplicationService | None
        ) = None
        if research_run_manager is not None:
            self._source_reputation_service = SourceReputationApplicationService(
                research_run_manager,
                response_composer,
                event_bus=event_bus,
            )
            self._provider_quality_service = ProviderQualityApplicationService(
                research_run_manager,
                response_composer,
                event_bus=event_bus,
            )
            self._paired_provider_quality_service = (
                PairedProviderQualityApplicationService(
                    research_run_manager,
                    response_composer,
                    event_bus=event_bus,
                )
            )
            self._provider_comparison_service = ProviderComparisonApplicationService(
                research_run_manager,
                response_composer,
                event_bus=event_bus,
            )
        self._hypothesis_service: HypothesisApplicationService | None = None
        if research_run_manager is not None:
            self._hypothesis_service = HypothesisApplicationService(
                research_run_manager,
                response_composer,
                hypothesis_store=hypothesis_store,
                event_bus=event_bus,
            )
        self._vulnerability_graph_service = VulnerabilityGraphApplicationService(
            response_composer,
            graph_store=vulnerability_graph_store,
            event_bus=event_bus,
        )
        self._security_agent_service: SecurityAgentApplicationService | None = None
        if research_run_manager is not None:
            self._security_agent_service = SecurityAgentApplicationService(
                research_run_manager,
                response_composer,
                event_bus=event_bus,
            )
        self._research_plan_preview_service = ResearchPlanPreviewApplicationService(
            response_composer,
            research_plan_draft_service,
        )
        self._source_ingestion_events = SourceIngestionEvents(event_bus)
        self._knowledge_reconciliation_service = (
            KnowledgeReconciliationApplicationService(
                knowledge_engine,
                response_composer,
                run_manager=research_run_manager,
                event_bus=event_bus,
            )
        )
        self._hybrid_semantic_memory_ranker = HybridSemanticMemoryRanker()
        self._router = BrainRouter()

    def process(self, request: BrainRequest) -> BrainResponse:
        """Process a request using the currently supported cognitive intent."""
        if self._is_undeclared_live_information_request(request):
            return self._process_conversation(request)
        intent = self._router.detect_intent(request)
        if intent == "conversation_search":
            return self._process_conversation_search(request)
        if intent == "session_search":
            return self._process_session_search(request)
        if intent == "session_activity":
            return self._process_session_activity(request)
        if intent == "session_active":
            return self._response_composer.session_active(
                request,
                self._session_manager.get_active(),
            )
        if intent == "session_help":
            return self._response_composer.session_help(request)
        if intent == "session_rename_help":
            return self._response_composer.session_rename_help(request)
        if intent == "session_rename_candidates":
            return self._process_session_rename_candidates(request)
        if intent == "session_rename_target_check":
            return self._process_session_rename_target_check(request)
        if intent == "session_rename":
            return self._process_session_rename(request)
        if intent == "session_rename_preview":
            return self._process_session_rename_preview(request)
        if intent == "session_delete_preview":
            return self._process_session_delete_preview(request)
        if intent == "session_delete":
            return self._process_session_delete(request)

        if self._is_research_run_create_request(request):
            return self._process_research_run_create(request)

        if self._research_overview_service.is_run_list_request(request):
            return self._research_overview_service.process_run_list(request)

        if self._learned_memory_audit_service.is_audit_request(request):
            return self._learned_memory_audit_service.process_audit(request)

        if self._research_plan_preview_service.is_draft_preview_request(request):
            return self._research_plan_preview_service.process_draft_preview(request)

        if self._research_plan_execution_service.is_start_request(request):
            return self._research_plan_execution_service.process_start(request)

        if self._research_plan_execution_service.is_status_request(request):
            return self._research_plan_execution_service.process_status(request)

        if self._research_plan_execution_service.is_cancel_request(request):
            return self._research_plan_execution_service.process_cancel(request)

        if self._research_plan_execution_service.is_continue_request(request):
            return self._research_plan_execution_service.process_continue(request)
        if self._research_plan_execution_service.is_recover_request(request):
            return self._research_plan_execution_service.process_recover(request)
        if self._research_plan_execution_service.is_resolve_request(request):
            return self._research_plan_execution_service.process_resolve(request)
        if self._research_plan_execution_service.is_advance_request(request):
            return self._research_plan_execution_service.process_advance(request)

        if self._research_autonomy_service.is_run_request(request):
            return self._research_autonomy_service.process_run(request)

        scheduler = self._background_research_scheduler
        if scheduler.is_create_request(request):
            return scheduler.process_create(request)

        if scheduler.is_pause_request(request):
            return scheduler.process_pause(request)

        if scheduler.is_resume_request(request):
            return scheduler.process_resume(request)

        if scheduler.is_cancel_request(request):
            return scheduler.process_cancel(request)

        if scheduler.is_list_request(request):
            return scheduler.process_list(request)

        if scheduler.is_worker_cycle_request(request):
            return scheduler.process_worker_cycle(request)

        if self._is_curiosity_request(request):
            return self._process_curiosity(request)

        if self._is_reflection_request(request):
            return self._process_reflection(request)

        if self._is_failure_memory_request(request):
            return self._process_failure_memory(request)

        if self._is_plan_authorization_request(request):
            return self._process_plan_authorization(request)

        if CalibrationApplicationService.is_request(request):
            return self._process_calibration(request)

        if SourceReputationApplicationService.is_report_request(request):
            return self._process_source_reputation(request)
        if (
            self._provider_quality_service is not None
            and self._provider_quality_service.is_report_request(request)
        ):
            return self._provider_quality_service.process_report(request)
        if (
            self._paired_provider_quality_service is not None
            and self._paired_provider_quality_service.is_report_request(request)
        ):
            return self._paired_provider_quality_service.process_report(request)
        if (
            self._provider_comparison_service is not None
            and self._provider_comparison_service.is_report_request(request)
        ):
            return self._provider_comparison_service.process_report(request)

        if self._is_hypothesis_request(request):
            return self._process_hypothesis(request)

        if self._is_vulnerability_graph_request(request):
            return self._process_vulnerability_graph(request)

        if self._is_knowledge_reconciliation_request(request):
            return self._process_knowledge_reconciliation(request)

        if SecurityAgentApplicationService.is_audit_request(request):
            return self._process_security_posture(request)

        if self._is_research_run_markdown_export_verify_request(request):
            return self._process_research_run_markdown_export_verify(request)

        if self._is_research_run_markdown_export_save_request(request):
            return self._process_research_run_markdown_export_save(request)

        if self._is_research_run_markdown_export_preview_request(request):
            return self._process_research_run_markdown_export_preview(request)

        if self._is_research_evidence_record_request(request):
            return self._process_research_evidence_record(request)

        if self._research_overview_service.is_evidence_list_request(request):
            return self._research_overview_service.process_evidence_list(request)

        authored_history = self._research_authored_history_service
        if authored_history.is_claim_preview_request(request):
            return authored_history.process_claim_preview(request)

        if self._is_research_claim_write_preview_request(request):
            return self._process_research_claim_write_preview(request)

        if self._is_research_claim_record_request(request):
            return self._process_research_claim_record(request)

        if self._is_research_claim_contradiction_preview_request(request):
            return self._process_research_claim_contradiction_preview(request)

        if self._is_research_claim_contradiction_proposal_request(request):
            return self._process_research_claim_contradiction_proposal(request)

        if self._is_research_claim_contradiction_write_preview_request(request):
            return self._process_research_claim_contradiction_write_preview(request)

        if self._is_research_claim_contradiction_record_request(request):
            return self._process_research_claim_contradiction_record(request)

        if authored_history.is_source_comparison_preview_request(request):
            return authored_history.process_source_comparison_preview(request)

        if self._is_research_source_comparison_note_write_preview_request(request):
            return self._process_research_source_comparison_note_write_preview(request)

        if self._is_research_source_comparison_note_record_request(request):
            return self._process_research_source_comparison_note_record(request)

        if authored_history.is_source_assessment_preview_request(request):
            return authored_history.process_source_assessment_preview(request)

        if self._is_research_source_assessment_write_preview_request(request):
            return self._process_research_source_assessment_write_preview(request)

        if self._is_research_source_assessment_record_request(request):
            return self._process_research_source_assessment_record(request)

        if self._is_research_run_status_preview_request(request):
            return self._process_research_run_status_preview(request)

        if self._is_research_run_status_update_request(request):
            return self._process_research_run_status_update(request)

        if self._is_research_source_discover_request(request):
            return self._process_research_source_discover(request)

        if self._is_research_source_candidate_acceptance_preview_request(request):
            return self._process_research_source_candidate_acceptance_preview(request)

        if self._is_research_source_candidate_accept_request(request):
            return self._process_research_source_candidate_accept(request)

        if self._is_research_source_load_request(request):
            return self._process_research_source_load(request)

        research_overview = self._research_overview_service
        if research_overview.is_source_content_restoration_status_request(request):
            return research_overview.process_source_content_restoration_status(request)

        if research_overview.is_evidence_integrity_status_request(request):
            return research_overview.process_evidence_integrity_status(request)

        if self._is_knowledge_load_request(request):
            return self._process_knowledge_load(request)

        if self._is_ask_knowledge_request(request):
            return self._process_ask_knowledge(request)

        if self._is_knowledge_context_request(request):
            return self._process_knowledge_context(request)

        if self._is_knowledge_graph_request(request):
            return self._process_knowledge_graph(request)

        if self._is_knowledge_list_request(request):
            return self._process_knowledge_list(request)

        if self._is_knowledge_relation_list_request(request):
            return self._process_knowledge_relation_list(request)

        if self._is_knowledge_relation_preview_request(request):
            return self._process_knowledge_relation_preview(request)

        if self._is_knowledge_relation_apply_request(request):
            return self._process_knowledge_relation_apply(request)

        if self._is_knowledge_relation_removal_preview_request(request):
            return self._process_knowledge_relation_removal_preview(request)

        if self._is_knowledge_relation_remove_request(request):
            return self._process_knowledge_relation_remove(request)

        if self._is_search_request(request):
            query = self._search_query(request)
            if not query:
                response = self._response_composer.search_failure(
                    request,
                    "A search query is required.",
                )
                self._remember_search(request, response, query)
                return response

            try:
                knowledge_results = self._knowledge_engine.search(query)
            except KnowledgeError as error:
                response = self._response_composer.search_failure(
                    request,
                    f"Knowledge search failed: {error}",
                )
                self._remember_search(request, response, query)
                return response

            response = self._response_composer.search_success(
                request,
                knowledge_results,
            )
            self._remember_search(request, response, query)
            return response

        if self._is_plan_request(request):
            goal = self._plan_goal(request)
            if not goal:
                return self._response_composer.plan_failure(
                    request,
                    "A planning goal is required.",
                )

            try:
                plan = self._planner.create_plan(goal)
            except PlannerError as error:
                return self._response_composer.plan_failure(
                    request,
                    f"Planning failed: {error}",
                )

            return self._response_composer.plan_success(request, plan)

        if self._is_recall_request(request):
            try:
                session_id = self._resolve_session_id(request)
                query = self._recall_query(request)
                if not query:
                    return self._response_composer.recall_failure(
                        request,
                        "A recall query is required.",
                    )

                records = self._memory_manager.search(
                    query,
                    tags={"brain", "conversation"},
                    limit=None,
                )
                session_records = [
                    record
                    for record in records
                    if record.metadata.get("session_id", "default") == session_id
                ]
            except SessionError as error:
                return self._response_composer.session_failure(request, str(error))
            except MemoryError as error:
                return self._response_composer.recall_failure(request, str(error))
            return self._response_composer.recall_success(request, session_records[:5])

        if self._is_semantic_recall_status_request(request):
            return self._process_semantic_recall_status(request)

        if self._is_semantic_recall_retry_request(request):
            return self._process_semantic_recall_retry(request)

        if self._is_semantic_recall_request(request):
            return self._process_semantic_recall(request)

        if intent in {"session_create", "session_list", "session_use"}:
            return self._process_session_command(request, intent)
        if intent == "session_overview":
            return self._process_session_overview(request)
        if intent == "session_details":
            return self._process_session_details(request)
        if intent == "session_recent":
            return self._process_session_recent(request)
        if intent == "recent_conversations":
            return self._process_recent_conversations(request)

        return self._process_conversation(request)

    def _is_undeclared_live_information_request(self, request: BrainRequest) -> bool:
        """Return whether plain chat asked for information only research provides.

        Gated on the absence of a declared intent, so every explicit structured
        request keeps its existing route. The check runs before the message
        prefixes because "search the internet" is a request for the live web,
        not a command to search the local knowledge base, and answering it from
        local chunks would be its own quiet misdirection.
        """
        if request.metadata.get("intent") is not None:
            return False
        return self._research_honesty_service.detect(request).detected

    @staticmethod
    def _is_search_request(request: BrainRequest) -> bool:
        declared_intent = request.metadata.get("intent")
        normalized_message = request.message.casefold().strip()
        return (
            declared_intent == "search"
            or normalized_message == "search"
            or normalized_message.startswith("search ")
        )

    @staticmethod
    def _is_knowledge_context_request(request: BrainRequest) -> bool:
        declared_intent = request.metadata.get("intent")
        normalized_message = request.message.casefold().strip()
        return (
            declared_intent == "knowledge_context"
            or normalized_message == "knowledge context"
            or normalized_message.startswith("knowledge context ")
        )

    @staticmethod
    def _is_knowledge_load_request(request: BrainRequest) -> bool:
        """Recognize only an explicit structured local-source request."""
        return request.metadata.get("intent") == "knowledge_load"

    @staticmethod
    def _is_research_source_load_request(request: BrainRequest) -> bool:
        """Recognize only an explicit structured internet-source request."""
        return request.metadata.get("intent") == "research_source_load"

    @staticmethod
    def _is_research_source_discover_request(request: BrainRequest) -> bool:
        """Recognize only an explicit structured source-discovery request."""
        return request.metadata.get("intent") == "research_source_discover"

    @staticmethod
    def _is_research_source_candidate_acceptance_preview_request(
        request: BrainRequest,
    ) -> bool:
        """Recognize only an explicit candidate acceptance preview."""
        return (
            request.metadata.get("intent")
            == "research_source_candidate_acceptance_preview"
        )

    @staticmethod
    def _is_research_source_candidate_accept_request(request: BrainRequest) -> bool:
        """Recognize only an explicit confirmed candidate acceptance."""
        return request.metadata.get("intent") == "research_source_candidate_accept"

    @staticmethod
    def _is_research_run_create_request(request: BrainRequest) -> bool:
        """Recognize only an explicit structured research-run creation request."""
        return request.metadata.get("intent") == "research_run_create"

    @staticmethod
    def _is_research_run_markdown_export_preview_request(
        request: BrainRequest,
    ) -> bool:
        """Recognize one explicit no-write terminal-run export preview."""
        return request.metadata.get("intent") == "research_run_markdown_export_preview"

    @staticmethod
    def _is_research_run_markdown_export_save_request(request: BrainRequest) -> bool:
        """Recognize one explicit revalidating new-file export request."""
        return request.metadata.get("intent") == "research_run_markdown_export_save"

    @staticmethod
    def _is_research_run_markdown_export_verify_request(request: BrainRequest) -> bool:
        """Recognize one explicit read-only local export integrity request."""
        return request.metadata.get("intent") == "research_run_markdown_export_verify"

    @staticmethod
    def _is_research_evidence_record_request(request: BrainRequest) -> bool:
        """Recognize one explicit indexed-chunk evidence selection."""
        return request.metadata.get("intent") == "research_evidence_record"

    @staticmethod
    def _is_research_claim_write_preview_request(request: BrainRequest) -> bool:
        """Recognize one no-write evidence-linked claim preview."""
        return request.metadata.get("intent") == "research_claim_write_preview"

    @staticmethod
    def _is_research_claim_record_request(request: BrainRequest) -> bool:
        """Recognize one separately confirmed authored claim write."""
        return request.metadata.get("intent") == "research_claim_record"

    @staticmethod
    def _is_research_claim_contradiction_preview_request(
        request: BrainRequest,
    ) -> bool:
        """Recognize one explicit read-only claim-contradiction request."""
        return request.metadata.get("intent") == "research_claim_contradiction_preview"

    @staticmethod
    def _is_research_claim_contradiction_proposal_request(
        request: BrainRequest,
    ) -> bool:
        return request.metadata.get("intent") == "research_claim_contradiction_proposal"

    @staticmethod
    def _is_research_claim_contradiction_write_preview_request(
        request: BrainRequest,
    ) -> bool:
        """Recognize one no-write claim-contradiction preview."""
        return (
            request.metadata.get("intent")
            == "research_claim_contradiction_write_preview"
        )

    @staticmethod
    def _is_research_claim_contradiction_record_request(
        request: BrainRequest,
    ) -> bool:
        """Recognize one separately confirmed claim-contradiction write."""
        return request.metadata.get("intent") == "research_claim_contradiction_record"

    @staticmethod
    def _is_research_source_comparison_note_write_preview_request(
        request: BrainRequest,
    ) -> bool:
        """Recognize a no-write authored comparison-note confirmation preview."""
        return (
            request.metadata.get("intent")
            == "research_source_comparison_note_write_preview"
        )

    @staticmethod
    def _is_research_source_comparison_note_record_request(
        request: BrainRequest,
    ) -> bool:
        """Recognize one separately confirmed comparison-note write."""
        return (
            request.metadata.get("intent") == "research_source_comparison_note_record"
        )

    @staticmethod
    def _is_research_source_assessment_write_preview_request(
        request: BrainRequest,
    ) -> bool:
        """Recognize one explicit no-write assessment confirmation preview."""
        return (
            request.metadata.get("intent") == "research_source_assessment_write_preview"
        )

    @staticmethod
    def _is_research_source_assessment_record_request(request: BrainRequest) -> bool:
        """Recognize one separately confirmed authored assessment write."""
        return request.metadata.get("intent") == "research_source_assessment_record"

    @staticmethod
    def _is_research_run_status_preview_request(request: BrainRequest) -> bool:
        """Recognize one explicit read-only lifecycle transition preview."""
        return request.metadata.get("intent") == "research_run_status_preview"

    @staticmethod
    def _is_research_run_status_update_request(request: BrainRequest) -> bool:
        """Recognize one explicit lifecycle transition mutation."""
        return request.metadata.get("intent") == "research_run_status_update"

    def _process_research_run_create(self, request: BrainRequest) -> BrainResponse:
        question = request.metadata.get("research_question")
        if not isinstance(question, str) or not question.strip():
            return self._response_composer.research_run_failure(
                request,
                "A research question is required.",
            )
        if self._research_run_manager is None:
            return self._response_composer.research_run_failure(
                request,
                "Research run persistence is unavailable.",
            )
        try:
            run = self._research_run_manager.create(question)
        except ResearchError:
            return self._response_composer.research_run_failure(
                request,
                "Research run could not be created.",
            )
        return self._response_composer.research_run_create_success(
            request,
            run,
            self._prior_lessons(question),
        )

    def _prior_lessons(self, question: str) -> tuple[ResearchFailureLesson, ...]:
        """Offer what previously went wrong on a similar question, if anything.

        Deliberately unable to fail its caller. The run is already persisted by
        the time this is asked, so an advisory read that raised would report a
        failure for work that actually succeeded — the misleading-success class
        this layer keeps closing. Advice is worth having; it is not worth
        lying about a saved run to get it.
        """
        service = self._failure_memory_service
        if service is None:
            return ()
        try:
            return service.advice(question)
        except Exception:
            # Broad on purpose. Any narrower clause is a bet about which
            # failures advice can have, and losing that bet costs a saved run.
            return ()

    def _process_research_run_markdown_export_preview(
        self,
        request: BrainRequest,
    ) -> BrainResponse:
        run_id = request.metadata.get("research_run_id")
        failure = self._response_composer.research_run_markdown_export_preview_failure
        if not isinstance(run_id, str) or not run_id.strip():
            return failure(request, "A research run ID is required.")
        if self._research_run_manager is None:
            return failure(request, "Research run persistence is unavailable.")
        try:
            preview = self._research_run_manager.preview_markdown_export(run_id)
        except ResearchError:
            return failure(
                request,
                "A terminal research run could not be previewed for export.",
            )
        return self._response_composer.research_run_markdown_export_preview_success(
            request,
            preview,
        )

    def _process_research_run_markdown_export_save(
        self,
        request: BrainRequest,
    ) -> BrainResponse:
        run_id = request.metadata.get("research_run_id")
        raw_updated_at = request.metadata.get("research_export_snapshot_updated_at")
        content_sha256 = request.metadata.get("research_export_content_sha256")
        destination_path = request.metadata.get("research_export_destination_path")
        failure = self._response_composer.research_run_markdown_export_save_failure
        if not isinstance(run_id, str) or not run_id.strip():
            return failure(request, "A research run ID is required.")
        if not isinstance(raw_updated_at, str) or not raw_updated_at.strip():
            return failure(request, "A research export snapshot time is required.")
        try:
            expected_updated_at = datetime.fromisoformat(raw_updated_at.strip())
        except ValueError:
            return failure(request, "Research export snapshot time is invalid.")
        if expected_updated_at.utcoffset() is None:
            return failure(request, "Research export snapshot time is invalid.")
        if not isinstance(content_sha256, str) or not content_sha256.strip():
            return failure(request, "A research export fingerprint is required.")
        if not isinstance(destination_path, str) or not destination_path.strip():
            return failure(request, "A research export destination is required.")
        if self._research_run_manager is None:
            return failure(request, "Research run persistence is unavailable.")
        try:
            result = self._research_run_manager.save_markdown_export(
                run_id,
                destination_path,
                expected_snapshot_updated_at=expected_updated_at,
                expected_content_sha256=content_sha256,
            )
        except ResearchError:
            return failure(
                request,
                "Research Markdown export could not be saved; no file was replaced.",
            )
        return self._response_composer.research_run_markdown_export_save_success(
            request,
            result,
        )

    def _process_research_run_markdown_export_verify(
        self,
        request: BrainRequest,
    ) -> BrainResponse:
        run_id = request.metadata.get("research_run_id")
        source_path = request.metadata.get("research_export_source_path")
        failure = self._response_composer.research_run_markdown_export_verify_failure
        if not isinstance(run_id, str) or not run_id.strip():
            return failure(request, "A research run ID is required.")
        if not isinstance(source_path, str) or not source_path.strip():
            return failure(request, "A research export verification file is required.")
        if self._research_run_manager is None:
            return failure(request, "Research run persistence is unavailable.")
        try:
            verification = self._research_run_manager.verify_markdown_export(
                run_id,
                source_path,
            )
        except ResearchError:
            return failure(
                request,
                "Research Markdown export could not be verified; no data was changed.",
            )
        return self._response_composer.research_run_markdown_export_verify_success(
            request,
            verification,
        )

    def _process_research_evidence_record(
        self,
        request: BrainRequest,
    ) -> BrainResponse:
        run_id = request.metadata.get("research_run_id")
        chunk_id = request.metadata.get("research_chunk_id")
        note = request.metadata.get("research_evidence_note")
        if not isinstance(run_id, str) or not run_id.strip():
            return self._response_composer.research_evidence_record_failure(
                request,
                "A research run ID is required.",
            )
        if not isinstance(chunk_id, str) or not chunk_id.strip():
            return self._response_composer.research_evidence_record_failure(
                request,
                "A research chunk ID is required.",
            )
        if not isinstance(note, str) or not note.strip():
            return self._response_composer.research_evidence_record_failure(
                request,
                "A research evidence note is required.",
            )
        if self._research_run_manager is None:
            return self._response_composer.research_evidence_record_failure(
                request,
                "Research run persistence is unavailable.",
            )
        try:
            chunk = self._knowledge_engine.get_chunk(chunk_id.strip())
        except KnowledgeError:
            return self._response_composer.research_evidence_record_failure(
                request,
                "Research evidence chunk was not found.",
            )
        try:
            run = self._research_run_manager.add_evidence(
                run_id.strip(),
                chunk,
                note,
            )
        except ResearchError:
            return self._response_composer.research_evidence_record_failure(
                request,
                "Research evidence could not be saved.",
            )
        return self._response_composer.research_evidence_record_success(request, run)

    def _process_research_claim_write_preview(
        self,
        request: BrainRequest,
    ) -> BrainResponse:
        """Preview exact authored claim metadata without mutation."""
        return self._process_research_claim_write(request, preview_only=True)

    def _process_research_claim_record(self, request: BrainRequest) -> BrainResponse:
        """Revalidate and commit one separately confirmed claim."""
        return self._process_research_claim_write(request, preview_only=False)

    def _process_research_claim_write(
        self,
        request: BrainRequest,
        *,
        preview_only: bool,
    ) -> BrainResponse:
        intent = (
            "research_claim_write_preview" if preview_only else "research_claim_record"
        )
        failure = self._response_composer.research_claim_write_failure
        values = self._research_claim_write_values(request)
        if values is None:
            return failure(
                request,
                "A run ID, explicit evidence IDs, authored claim text, and valid "
                "epistemic state are required.",
                intent=intent,
            )
        if self._research_run_manager is None:
            return failure(
                request,
                "Research run persistence is unavailable.",
                intent=intent,
            )
        try:
            if preview_only:
                preview = self._research_run_manager.preview_claim_write(*values)
                return self._response_composer.research_claim_write_preview_success(
                    request,
                    preview,
                )
            run = self._research_run_manager.record_claim(*values)
        except ResearchError:
            return failure(
                request,
                "Research claim could not be validated or saved.",
                intent=intent,
            )
        return self._response_composer.research_claim_record_success(request, run)

    @staticmethod
    def _research_claim_write_values(
        request: BrainRequest,
    ) -> tuple[str, list[str], str, str, str, str | None] | None:
        run_id = request.metadata.get("research_run_id")
        evidence_ids = request.metadata.get("research_claim_evidence_ids")
        text = request.metadata.get("research_claim_text")
        epistemic_state = request.metadata.get("research_claim_epistemic_state")
        confidence = request.metadata.get(
            "research_claim_confidence",
            "unassessed",
        )
        supersedes_claim_id = request.metadata.get("research_claim_supersedes_id")
        if (
            not isinstance(run_id, str)
            or not run_id.strip()
            or not isinstance(evidence_ids, list)
            or not evidence_ids
            or not all(
                isinstance(evidence_id, str) and evidence_id.strip()
                for evidence_id in evidence_ids
            )
            or len(evidence_ids)
            != len({evidence_id.strip() for evidence_id in evidence_ids})
            or not isinstance(text, str)
            or not text.strip()
            or not isinstance(epistemic_state, str)
            or not epistemic_state.strip()
            or not isinstance(confidence, str)
            or not confidence.strip()
            or (
                supersedes_claim_id is not None
                and (
                    not isinstance(supersedes_claim_id, str)
                    or not supersedes_claim_id.strip()
                )
            )
        ):
            return None
        return (
            run_id,
            evidence_ids,
            text,
            epistemic_state,
            confidence,
            supersedes_claim_id,
        )

    def _process_research_claim_contradiction_preview(
        self,
        request: BrainRequest,
    ) -> BrainResponse:
        """Read persisted contradiction history without providers or mutation."""
        run_id = request.metadata.get("research_run_id")
        failure = self._response_composer.research_claim_contradiction_preview_failure
        if not isinstance(run_id, str) or not run_id.strip():
            return failure(request, "A research run ID is required.")
        if self._research_run_manager is None:
            return failure(request, "Research run persistence is unavailable.")
        try:
            preview = self._research_run_manager.preview_claim_contradictions(run_id)
        except ResearchError:
            return failure(request, "Research run was not found.")
        return self._response_composer.research_claim_contradiction_preview_success(
            request,
            preview,
        )

    def _process_research_claim_contradiction_proposal(
        self,
        request: BrainRequest,
    ) -> BrainResponse:
        """Request bounded review candidates without changing research state."""
        failure = self._response_composer.research_claim_contradiction_proposal_failure
        run_id = request.metadata.get("research_run_id")
        if not isinstance(run_id, str) or not run_id.strip():
            return failure(request, "A research run ID is required.")
        if self._research_run_manager is None:
            return failure(request, "Research run persistence is unavailable.")
        try:
            run = self._research_run_manager.get(run_id.strip())
        except ResearchError:
            return failure(request, "Research run was not found.")

        current_claims = self._current_research_claims(run.claims)
        provider = self._research_claim_contradiction_proposal_provider
        if len(current_claims) < 2:
            preview = ResearchClaimContradictionProposalPreview(
                run_id=run.run_id,
                question=run.question,
                run_status=run.status,
                snapshot_updated_at=run.updated_at,
                provider_name="not_required",
                claims=current_claims,
                candidates=(),
                reason="At least two current claims are required for suggestions.",
            )
            return (
                self._response_composer.research_claim_contradiction_proposal_success(
                    request,
                    preview,
                )
            )
        if len(current_claims) > RESEARCH_CLAIM_CONTRADICTION_PROPOSAL_MAX_CLAIMS:
            return failure(
                request,
                "Research claim contradiction suggestions support at most 50 "
                "current claims per run.",
            )
        if provider is None:
            return failure(
                request,
                "Research claim contradiction suggestions are unavailable.",
            )
        if self._request_cancelled(request):
            return failure(
                request, "Research claim contradiction suggestion cancelled."
            )
        try:
            provider_name = provider.provider_name
            if not isinstance(provider_name, str) or not provider_name.strip():
                raise ResearchClaimContradictionProposalError(
                    "Research contradiction proposal provider identity is invalid."
                )
            proposed_candidates = provider.propose(
                run.question,
                current_claims,
                limit=RESEARCH_CLAIM_CONTRADICTION_PROPOSAL_LIMIT,
            )
            if self._request_cancelled(request):
                return failure(
                    request,
                    "Research claim contradiction suggestion cancelled.",
                )
            candidates = self._validate_research_claim_contradiction_candidates(
                run,
                current_claims,
                proposed_candidates,
            )
            latest_run = self._research_run_manager.get(run.run_id)
            if latest_run != run:
                return failure(
                    request,
                    (
                        "Research run changed while contradiction suggestions "
                        "were generated."
                    ),
                )
            preview = ResearchClaimContradictionProposalPreview(
                run_id=run.run_id,
                question=run.question,
                run_status=run.status,
                snapshot_updated_at=run.updated_at,
                provider_name=provider_name,
                claims=current_claims,
                candidates=tuple(candidates),
                reason=(
                    f"{len(candidates)} possible contradiction candidate"
                    f"{'s' if len(candidates) != 1 else ''} require manual review."
                    if candidates
                    else "No new possible contradiction candidates were proposed."
                ),
            )
        except ResearchClaimContradictionProposalError, ResearchError:
            return failure(
                request,
                "Research claim contradiction suggestions could not be generated.",
            )
        return self._response_composer.research_claim_contradiction_proposal_success(
            request,
            preview,
        )

    @staticmethod
    def _current_research_claims(
        claims: tuple[ResearchClaimRecord, ...],
    ) -> tuple[ResearchClaimRecord, ...]:
        superseded_ids = {
            claim.supersedes_claim_id
            for claim in claims
            if claim.supersedes_claim_id is not None
        }
        return tuple(claim for claim in claims if claim.claim_id not in superseded_ids)

    @staticmethod
    def _validate_research_claim_contradiction_candidates(
        run: ResearchRun,
        claims: tuple[ResearchClaimRecord, ...],
        candidates: object,
    ) -> list[ResearchClaimContradictionCandidate]:
        if (
            not isinstance(candidates, list)
            or len(candidates) > RESEARCH_CLAIM_CONTRADICTION_PROPOSAL_LIMIT
            or not all(
                isinstance(candidate, ResearchClaimContradictionCandidate)
                for candidate in candidates
            )
        ):
            raise ResearchError(
                "Research claim contradiction provider returned invalid candidates."
            )
        claims_by_id = {claim.claim_id: claim for claim in claims}
        existing_pairs = {
            frozenset(contradiction.claim_ids)
            for contradiction in run.claim_contradictions
        }
        seen_pairs: set[frozenset[str]] = set()
        accepted: list[ResearchClaimContradictionCandidate] = []
        for candidate in candidates:
            if any(claim_id not in claims_by_id for claim_id in candidate.claim_ids):
                raise ResearchError(
                    "Research claim contradiction candidate references an "
                    "invalid claim."
                )
            expected_evidence_ids = tuple(
                dict.fromkeys(
                    evidence_id
                    for claim_id in candidate.claim_ids
                    for evidence_id in claims_by_id[claim_id].evidence_ids
                )
            )
            pair_key = frozenset(candidate.claim_ids)
            if candidate.evidence_ids != expected_evidence_ids:
                raise ResearchError(
                    "Research claim contradiction candidate provenance is invalid."
                )
            if pair_key in existing_pairs:
                continue
            if pair_key in seen_pairs:
                raise ResearchError(
                    "Research claim contradiction candidate pair is duplicated."
                )
            seen_pairs.add(pair_key)
            accepted.append(candidate)
        return accepted

    def _process_research_claim_contradiction_write_preview(
        self,
        request: BrainRequest,
    ) -> BrainResponse:
        """Preview exact authored relationship metadata without mutation."""
        return self._process_research_claim_contradiction_write(
            request,
            preview_only=True,
        )

    def _process_research_claim_contradiction_record(
        self,
        request: BrainRequest,
    ) -> BrainResponse:
        """Revalidate and commit one separately confirmed contradiction."""
        return self._process_research_claim_contradiction_write(
            request,
            preview_only=False,
        )

    def _process_research_claim_contradiction_write(
        self,
        request: BrainRequest,
        *,
        preview_only: bool,
    ) -> BrainResponse:
        intent = (
            "research_claim_contradiction_write_preview"
            if preview_only
            else "research_claim_contradiction_record"
        )
        failure = self._response_composer.research_claim_contradiction_write_failure
        values = self._research_claim_contradiction_write_values(request)
        if values is None:
            return failure(
                request,
                "A run ID, exactly two distinct claim IDs, and a user-authored "
                "contradiction note are required.",
                intent=intent,
            )
        if self._research_run_manager is None:
            return failure(
                request,
                "Research run persistence is unavailable.",
                intent=intent,
            )
        try:
            if preview_only:
                preview = self._research_run_manager.preview_claim_contradiction_write(
                    *values
                )
                compose_preview = (
                    self._response_composer.research_claim_contradiction_write_preview_success
                )
                return compose_preview(request, preview)
            run = self._research_run_manager.record_claim_contradiction(*values)
        except ResearchError:
            return failure(
                request,
                "Research claim contradiction could not be validated or saved.",
                intent=intent,
            )
        return self._response_composer.research_claim_contradiction_record_success(
            request,
            run,
        )

    @staticmethod
    def _research_claim_contradiction_write_values(
        request: BrainRequest,
    ) -> tuple[str, list[str], str] | None:
        run_id = request.metadata.get("research_run_id")
        claim_ids = request.metadata.get("research_claim_contradiction_claim_ids")
        note = request.metadata.get("research_claim_contradiction_note")
        if (
            not isinstance(run_id, str)
            or not run_id.strip()
            or not isinstance(claim_ids, list)
            or len(claim_ids) != 2
            or not all(
                isinstance(claim_id, str) and claim_id.strip() for claim_id in claim_ids
            )
            or len({claim_id.strip() for claim_id in claim_ids}) != 2
            or not isinstance(note, str)
            or not note.strip()
        ):
            return None
        return run_id, claim_ids, note

    def _process_research_source_comparison_note_write_preview(
        self,
        request: BrainRequest,
    ) -> BrainResponse:
        """Preview exact persisted references without writing a note."""
        return self._process_research_source_comparison_note_write(
            request,
            preview_only=True,
        )

    def _process_research_source_comparison_note_record(
        self,
        request: BrainRequest,
    ) -> BrainResponse:
        """Revalidate and commit one separately confirmed authored note."""
        return self._process_research_source_comparison_note_write(
            request,
            preview_only=False,
        )

    def _process_research_source_comparison_note_write(
        self,
        request: BrainRequest,
        *,
        preview_only: bool,
    ) -> BrainResponse:
        intent = (
            "research_source_comparison_note_write_preview"
            if preview_only
            else "research_source_comparison_note_record"
        )
        failure = self._response_composer.research_source_comparison_note_failure
        values = self._research_source_comparison_note_values(request)
        if values is None:
            return failure(
                request,
                "A run ID, 2 to 5 source IDs, explicit evidence IDs, current "
                "assessment IDs, and authored comparison text are required.",
                intent=intent,
            )
        if self._research_run_manager is None:
            return failure(
                request,
                "Research run persistence is unavailable.",
                intent=intent,
            )
        try:
            if preview_only:
                preview = (
                    self._research_run_manager.preview_source_comparison_note_write(
                        *values
                    )
                )
                compose_preview = (
                    self._response_composer.research_source_comparison_note_write_preview_success
                )
                return compose_preview(
                    request,
                    preview,
                )
            run = self._research_run_manager.record_source_comparison_note(*values)
        except ResearchError:
            return failure(
                request,
                "Research comparison note could not be validated or saved.",
                intent=intent,
            )
        return self._response_composer.research_source_comparison_note_record_success(
            request,
            run,
        )

    @staticmethod
    def _research_source_comparison_note_values(
        request: BrainRequest,
    ) -> tuple[str, list[str], list[str], list[str], str] | None:
        run_id = request.metadata.get("research_run_id")
        document_ids = request.metadata.get("research_source_document_ids")
        evidence_ids = request.metadata.get("research_comparison_evidence_ids")
        assessment_ids = request.metadata.get("research_comparison_assessment_ids")
        text = request.metadata.get("research_comparison_note_text")
        if (
            not isinstance(run_id, str)
            or not run_id.strip()
            or not isinstance(document_ids, list)
            or not 2 <= len(document_ids) <= 5
            or not isinstance(evidence_ids, list)
            or not evidence_ids
            or not isinstance(assessment_ids, list)
            or not assessment_ids
            or not isinstance(text, str)
            or not text.strip()
        ):
            return None
        values = (document_ids, evidence_ids, assessment_ids)
        if any(
            not all(isinstance(value, str) and value.strip() for value in items)
            or len(items) != len({value.strip() for value in items})
            for items in values
        ):
            return None
        return run_id, document_ids, evidence_ids, assessment_ids, text

    def _process_research_source_assessment_write_preview(
        self,
        request: BrainRequest,
    ) -> BrainResponse:
        """Preview explicit evidence and authored text without side effects."""
        return self._process_research_source_assessment_write(
            request,
            preview_only=True,
        )

    def _process_research_source_assessment_record(
        self,
        request: BrainRequest,
    ) -> BrainResponse:
        """Revalidate and commit one separately confirmed assessment."""
        return self._process_research_source_assessment_write(
            request,
            preview_only=False,
        )

    def _process_research_source_assessment_write(
        self,
        request: BrainRequest,
        *,
        preview_only: bool,
    ) -> BrainResponse:
        intent = (
            "research_source_assessment_write_preview"
            if preview_only
            else "research_source_assessment_record"
        )
        failure = self._response_composer.research_source_assessment_write_failure
        values = self._research_source_assessment_write_values(request)
        if values is None:
            return failure(
                request,
                "A run ID, accepted source document ID, explicit evidence IDs, and "
                "assessment text are required.",
                intent=intent,
            )
        if self._research_run_manager is None:
            return failure(
                request,
                "Research run persistence is unavailable.",
                intent=intent,
            )
        try:
            if preview_only:
                preview = self._research_run_manager.preview_source_assessment_write(
                    *values
                )
                compose_preview = (
                    self._response_composer.research_source_assessment_write_preview_success
                )
                return compose_preview(
                    request,
                    preview,
                )
            run = self._research_run_manager.record_source_assessment(*values)
        except ResearchError:
            return failure(
                request,
                "Research source assessment could not be validated or saved.",
                intent=intent,
            )
        return self._response_composer.research_source_assessment_record_success(
            request,
            run,
        )

    def _selected_discovery_provider(
        self,
        request: BrainRequest,
    ) -> ResearchSourceDiscoveryProvider:
        """Return the provider this request explicitly named, or the default.

        The name is resolved through a closed vocabulary and nothing else. A
        provider is a network destination, so a request naming one this build
        cannot reach fails rather than falling back: silently searching
        somewhere the operator did not choose is worse than not searching.

        There is no automatic second attempt against the other provider either.
        If NVD refuses, that is reported as NVD refusing — hiding it behind a
        Crossref result would answer a question nobody asked.
        """
        requested = request.metadata.get("research_discovery_provider")
        if requested is None:
            assert self._research_source_discovery_provider is not None
            return self._research_source_discovery_provider
        if not isinstance(requested, str):
            raise ResearchError("Research discovery provider must be text.")
        try:
            name = ResearchDiscoveryProviderName(requested)
        except ValueError as error:
            raise ResearchError("Research discovery provider is unknown.") from error
        provider = self._research_source_discovery_providers.get(name)
        if provider is None:
            raise ResearchError("Research discovery provider is not available.")
        return provider

    @staticmethod
    def _research_source_assessment_write_values(
        request: BrainRequest,
    ) -> tuple[str, str, list[str], str, str | None, str, str, str, str, str] | None:
        run_id = request.metadata.get("research_run_id")
        document_id = request.metadata.get("research_source_document_id")
        evidence_ids = request.metadata.get("research_assessment_evidence_ids")
        text = request.metadata.get("research_assessment_text")
        supersedes_assessment_id = request.metadata.get(
            "research_assessment_supersedes_id"
        )
        information_trust = request.metadata.get(
            "research_information_trust",
            "unassessed",
        )
        # Absent means the operator did not answer, which is `unknown`. It is
        # never read as a favourable default: a request that says nothing about
        # usefulness must not produce a record claiming the source was useful.
        judgement = tuple(
            request.metadata.get(f"research_source_{name}", "unknown")
            for name in ("usefulness", "applicability", "independence")
        ) + (
            request.metadata.get("research_source_publication_status", "unknown"),
        )
        if not all(isinstance(value, str) and value.strip() for value in judgement):
            return None
        if (
            not isinstance(run_id, str)
            or not run_id.strip()
            or not isinstance(document_id, str)
            or not document_id.strip()
            or not isinstance(evidence_ids, list)
            or not evidence_ids
            or not all(
                isinstance(evidence_id, str) and evidence_id.strip()
                for evidence_id in evidence_ids
            )
            or not isinstance(text, str)
            or not text.strip()
            or not isinstance(information_trust, str)
            or not information_trust.strip()
            or (
                supersedes_assessment_id is not None
                and (
                    not isinstance(supersedes_assessment_id, str)
                    or not supersedes_assessment_id.strip()
                )
            )
        ):
            return None
        return (
            run_id,
            document_id,
            evidence_ids,
            text,
            supersedes_assessment_id,
            information_trust,
            *judgement,
        )

    def _process_research_run_status_preview(
        self,
        request: BrainRequest,
    ) -> BrainResponse:
        values = self._research_run_status_values(request)
        if values is None:
            return self._response_composer.research_run_status_failure(
                request,
                "A valid research run ID and target status are required.",
                intent="research_run_status_preview",
            )
        if self._research_run_manager is None:
            return self._response_composer.research_run_status_failure(
                request,
                "Research run persistence is unavailable.",
                intent="research_run_status_preview",
            )
        run_id, target_status = values
        try:
            preview = self._research_run_manager.preview_status_transition(
                run_id,
                target_status,
            )
        except ResearchError:
            return self._response_composer.research_run_status_failure(
                request,
                "Research run was not found.",
                intent="research_run_status_preview",
            )
        return self._response_composer.research_run_status_preview_success(
            request,
            preview,
        )

    def _process_research_run_status_update(
        self,
        request: BrainRequest,
    ) -> BrainResponse:
        values = self._research_run_status_values(request)
        if values is None:
            return self._response_composer.research_run_status_failure(
                request,
                "A valid research run ID and target status are required.",
            )
        if self._research_run_manager is None:
            return self._response_composer.research_run_status_failure(
                request,
                "Research run persistence is unavailable.",
            )
        run_id, target_status = values
        try:
            run = self._research_run_manager.transition_status(
                run_id,
                target_status,
            )
        except ResearchError:
            return self._response_composer.research_run_status_failure(
                request,
                "Research run status could not be updated.",
            )
        return self._response_composer.research_run_status_update_success(request, run)

    @staticmethod
    def _research_run_status_values(
        request: BrainRequest,
    ) -> tuple[str, ResearchRunStatus] | None:
        run_id = request.metadata.get("research_run_id")
        target_value = request.metadata.get("research_target_status")
        if (
            not isinstance(run_id, str)
            or not run_id.strip()
            or not isinstance(target_value, str)
        ):
            return None
        try:
            target_status = ResearchRunStatus(target_value.strip().casefold())
        except ValueError:
            return None
        return run_id.strip(), target_status

    def _process_research_source_discover(
        self,
        request: BrainRequest,
    ) -> BrainResponse:
        """Persist provider metadata results without fetching candidate content."""
        run_id = request.metadata.get("research_run_id")
        if not isinstance(run_id, str) or not run_id.strip():
            return self._response_composer.research_source_discovery_failure(
                request,
                "A research run ID is required.",
            )
        if self._research_run_manager is None:
            return self._response_composer.research_source_discovery_failure(
                request,
                "Research run persistence is unavailable.",
            )
        if self._research_source_discovery_provider is None:
            return self._response_composer.research_source_discovery_failure(
                request,
                "Research source discovery is unavailable.",
            )

        normalized_run_id = run_id.strip()
        try:
            run = self._research_run_manager.get(normalized_run_id)
        except ResearchError:
            return self._response_composer.research_source_discovery_failure(
                request,
                "Research run was not found.",
            )
        if run.status.terminal:
            return self._response_composer.research_source_discovery_failure(
                request,
                "Research run is closed and cannot discover new sources.",
            )

        try:
            provider = self._selected_discovery_provider(request)
        except ResearchError:
            return self._response_composer.research_source_discovery_failure(
                request,
                "Research source discovery provider is unavailable.",
            )
        if self._request_cancelled(request):
            return self._response_composer.research_source_discovery_failure(
                request,
                "Research source discovery was cancelled.",
            )
        try:
            candidates = provider.discover(run.question, limit=5)
            if self._request_cancelled(request):
                return self._response_composer.research_source_discovery_failure(
                    request,
                    "Research source discovery was cancelled.",
                )
            if (
                not isinstance(candidates, list)
                or len(candidates) > 5
                or not all(
                    isinstance(candidate, ResearchSourceCandidate)
                    for candidate in candidates
                )
            ):
                raise ResearchError(
                    "Research source discovery provider returned invalid candidates."
                )
            if self._request_cancelled(request):
                return self._response_composer.research_source_discovery_failure(
                    request,
                    "Research source discovery was cancelled.",
                )
        except ResearchError:
            if self._request_cancelled(request):
                return self._response_composer.research_source_discovery_failure(
                    request,
                    "Research source discovery was cancelled.",
                )
            try:
                self._research_run_manager.record_failure(
                    normalized_run_id,
                    "source_discovery",
                    "Research source discovery failed.",
                    provider=provider.provider_name,
                )
            except ResearchError:
                return self._response_composer.research_source_discovery_failure(
                    request,
                    (
                        "Research source discovery and its audit record "
                        "could not be saved."
                    ),
                )
            return self._response_composer.research_source_discovery_failure(
                request,
                "Research source discovery failed.",
            )

        try:
            updated = self._research_run_manager.add_discovery(
                normalized_run_id,
                run.question,
                provider.provider_name,
                candidates,
            )
        except ResearchError:
            return self._response_composer.research_source_discovery_failure(
                request,
                "Research source discovery audit could not be saved.",
            )
        return self._response_composer.research_source_discovery_success(
            request,
            updated,
        )

    def _process_research_source_candidate_acceptance_preview(
        self,
        request: BrainRequest,
    ) -> BrainResponse:
        """Preview a persisted candidate without fetching or changing state."""
        failure_response = (
            self._response_composer.research_source_candidate_acceptance_preview_failure
        )
        values = self._research_source_candidate_values(request)
        if values is None:
            return failure_response(
                request,
                "A research run ID, discovery ID, and candidate URL are required.",
            )
        if self._research_run_manager is None:
            return failure_response(
                request,
                "Research run persistence is unavailable.",
            )
        try:
            preview = self._research_run_manager.preview_candidate_acceptance(*values)
        except ResearchError as error:
            return failure_response(request, str(error))
        success_response = (
            self._response_composer.research_source_candidate_acceptance_preview_success
        )
        return success_response(
            request,
            preview,
        )

    def _process_research_source_candidate_accept(
        self,
        request: BrainRequest,
    ) -> BrainResponse:
        """Revalidate a confirmed candidate before using the guarded loader."""
        values = self._research_source_candidate_values(request)
        if values is None:
            return self._response_composer.research_source_load_failure(
                request,
                "A research run ID, discovery ID, and candidate URL are required.",
                intent="research_source_candidate_accept",
            )
        if self._research_run_manager is None:
            return self._response_composer.research_source_load_failure(
                request,
                "Research run persistence is unavailable.",
                intent="research_source_candidate_accept",
            )
        try:
            preview = self._research_run_manager.preview_candidate_acceptance(*values)
        except ResearchError as error:
            return self._response_composer.research_source_load_failure(
                request,
                str(error),
                intent="research_source_candidate_accept",
            )
        if not preview.allowed:
            return self._response_composer.research_source_load_failure(
                request,
                preview.reason,
                intent="research_source_candidate_accept",
            )
        return self._process_research_source_load(
            request,
            response_intent="research_source_candidate_accept",
        )

    @staticmethod
    def _research_source_candidate_values(
        request: BrainRequest,
    ) -> tuple[str, str, str] | None:
        run_id = request.metadata.get("research_run_id")
        discovery_id = request.metadata.get("research_discovery_id")
        candidate_url = request.metadata.get("research_url")
        if not (
            isinstance(run_id, str)
            and run_id.strip()
            and isinstance(discovery_id, str)
            and discovery_id.strip()
            and isinstance(candidate_url, str)
            and candidate_url.strip()
        ):
            return None
        return run_id.strip(), discovery_id.strip(), candidate_url.strip()

    def _process_research_source_load(
        self,
        request: BrainRequest,
        *,
        response_intent: str = "research_source_load",
    ) -> BrainResponse:
        """Acquire and index one explicit source without LLM or memory side effects.

        Each real transition is announced on the event bus. The identifier ties
        one attempt's events together, so a subscriber can follow a single load
        without inferring which events belong to it.
        """
        attempt_id = str(uuid4())
        events = self._source_ingestion_events.for_attempt(attempt_id)
        events.validation_started()
        url = request.metadata.get("research_url")
        if not isinstance(url, str) or not url.strip():
            events.failed(
                SourceLoadStage.NOT_ATTEMPTED,
                IngestionFailureKind.VALIDATION_REFUSED,
            )
            return self._response_composer.research_source_load_failure(
                request,
                "A research source URL is required.",
                intent=response_intent,
            )
        resource = identity_of(url)
        if self._research_source_fetcher is None:
            events.failed(
                SourceLoadStage.NOT_ATTEMPTED,
                IngestionFailureKind.VALIDATION_REFUSED,
                resource_identity=resource,
            )
            return self._response_composer.research_source_load_failure(
                request,
                "Internet research source loading is unavailable.",
                intent=response_intent,
            )
        run_id_value = request.metadata.get("research_run_id")
        run_id = run_id_value.strip() if isinstance(run_id_value, str) else ""
        if run_id_value is not None and not run_id:
            events.failed(
                SourceLoadStage.NOT_ATTEMPTED,
                IngestionFailureKind.VALIDATION_REFUSED,
                resource_identity=resource,
            )
            return self._response_composer.research_source_load_failure(
                request,
                "A valid research run ID is required.",
                intent=response_intent,
            )
        if run_id and self._research_run_manager is None:
            events.failed(
                SourceLoadStage.NOT_ATTEMPTED,
                IngestionFailureKind.RUN_UNAVAILABLE,
                resource_identity=resource,
                run_id=run_id,
            )
            return self._response_composer.research_source_load_failure(
                request,
                "Research run persistence is unavailable.",
                intent=response_intent,
            )
        if run_id:
            assert self._research_run_manager is not None
            try:
                selected_run = self._research_run_manager.get(run_id)
            except ResearchError:
                events.failed(
                    SourceLoadStage.NOT_ATTEMPTED,
                    IngestionFailureKind.RUN_UNAVAILABLE,
                    resource_identity=resource,
                    run_id=run_id,
                )
                return self._response_composer.research_source_load_failure(
                    request,
                    "Research run was not found.",
                    intent=response_intent,
                )
            if selected_run.status.terminal:
                events.failed(
                    SourceLoadStage.NOT_ATTEMPTED,
                    IngestionFailureKind.RUN_UNAVAILABLE,
                    resource_identity=resource,
                    run_id=run_id,
                )
                return self._response_composer.research_source_load_failure(
                    request,
                    "Research run is closed and cannot accept new sources.",
                    intent=response_intent,
                )
        if self._request_cancelled(request):
            events.cancelled(resource_identity=resource, run_id=run_id)
            return self._response_composer.research_source_load_failure(
                request,
                "Research source loading was cancelled.",
                intent=response_intent,
            )
        events.validation_completed(resource, run_id=run_id)
        try:
            events.fetch_started(resource, run_id=run_id)
            source = self._research_source_fetcher.fetch(url.strip())
            events.fetch_completed(resource, run_id=run_id)
            if self._request_cancelled(request):
                events.cancelled(resource_identity=resource, run_id=run_id)
                return self._response_composer.research_source_load_failure(
                    request,
                    "Research source loading was cancelled.",
                    intent=response_intent,
                )
            result = self._research_source_acceptance_service.accept(
                source,
                run_id,
                attempt_id=attempt_id,
            )
        except (ResearchError, KnowledgeError) as error:
            if isinstance(error, ResearchError) and self._request_cancelled(request):
                events.cancelled(resource_identity=resource, run_id=run_id)
                return self._response_composer.research_source_load_failure(
                    request,
                    "Research source loading was cancelled.",
                    intent=response_intent,
                )
            fetch_refused = isinstance(error, ResearchError)
            if run_id and self._research_run_manager is not None:
                audit_reason = (
                    "Research source acquisition failed."
                    if isinstance(error, ResearchError)
                    else "Research source indexing failed."
                )
                try:
                    self._research_run_manager.record_failure(
                        run_id,
                        "source_load",
                        audit_reason,
                    )
                except ResearchError:
                    events.failed(
                        (
                            SourceLoadStage.FETCH_REFUSED
                            if fetch_refused
                            else SourceLoadStage.INDEX_FAILED
                        ),
                        (
                            IngestionFailureKind.FETCH_REFUSED
                            if fetch_refused
                            else IngestionFailureKind.INDEX_FAILED
                        ),
                        resource_identity=resource,
                        run_id=run_id,
                        safe_failure_recorded=False,
                    )
                    return self._response_composer.research_source_load_failure(
                        request,
                        (
                            "Research source failed and its audit record "
                            "could not be saved."
                        ),
                        intent=response_intent,
                    )
                safe_failure_recorded = True
            else:
                safe_failure_recorded = False
            if fetch_refused:
                events.failed(
                    SourceLoadStage.FETCH_REFUSED,
                    IngestionFailureKind.FETCH_REFUSED,
                    resource_identity=resource,
                    run_id=run_id,
                    safe_failure_recorded=safe_failure_recorded,
                )
            return self._response_composer.research_source_load_failure(
                request,
                f"Research source could not be loaded: {error}",
                intent=response_intent,
            )
        if not result.accepted:
            return self._response_composer.research_source_load_failure(
                request,
                result.failure_reason,
                intent=response_intent,
            )
        loaded_document = next(
            reference
            for reference in self._knowledge_engine.documents()
            if reference.document_id == result.document_id
        )
        return self._response_composer.research_source_load_success(
            request,
            loaded_document,
            run=result.run,
            stage=result.stage,
            intent=response_intent,
        )

    @staticmethod
    def _request_cancelled(request: BrainRequest) -> bool:
        token = request.cancellation_token
        return token is not None and token.is_cancelled()

    def _process_knowledge_load(self, request: BrainRequest) -> BrainResponse:
        """Load one user-selected local source without LLM or memory side effects."""
        path = request.metadata.get("knowledge_path")
        if not isinstance(path, str) or not path.strip():
            return self._response_composer.knowledge_load_failure(
                request,
                "A local knowledge source path is required.",
            )
        try:
            document = self._knowledge_engine.load(path.strip())
        except KnowledgeError as error:
            return self._response_composer.knowledge_load_failure(
                request,
                f"Local knowledge source could not be loaded: {error}",
            )
        loaded_document = next(
            reference
            for reference in self._knowledge_engine.documents()
            if reference.document_id == document.document_id
        )
        return self._response_composer.knowledge_load_success(
            request,
            loaded_document,
        )

    @staticmethod
    def _is_ask_knowledge_request(request: BrainRequest) -> bool:
        declared_intent = request.metadata.get("intent")
        normalized_message = request.message.casefold().strip()
        return (
            declared_intent == "ask_knowledge"
            or normalized_message == "ask knowledge"
            or normalized_message.startswith("ask knowledge ")
        )

    @staticmethod
    def _ask_knowledge_query(request: BrainRequest) -> str:
        if request.metadata.get("intent") == "ask_knowledge":
            return request.message.strip()
        return request.message[len("ask knowledge") :].strip()

    def _process_ask_knowledge(self, request: BrainRequest) -> BrainResponse:
        """Answer an explicit local-knowledge request without conversation mutation."""
        query = self._ask_knowledge_query(request)
        if not query:
            return self._response_composer.ask_knowledge_failure(
                request, "An ask knowledge query is required."
            )
        if self._llm_provider is None:
            return self._response_composer.ask_knowledge_failure(
                request, "A language-model runtime is required for ask knowledge."
            )
        try:
            results = self._knowledge_engine.search(query)[
                :KNOWLEDGE_CONTEXT_MAX_RESULTS
            ]
        except KnowledgeError as error:
            return self._response_composer.ask_knowledge_failure(
                request, f"Knowledge retrieval failed: {error}"
            )
        if not results:
            return self._response_composer.ask_knowledge_failure(
                request, "No matching local knowledge was found."
            )
        citations = [KnowledgeCitation.from_chunk(result) for result in results]
        try:
            answer = self._llm_provider.generate(
                build_knowledge_context_prompt(query, results, citations),
                system_instruction=KNOWLEDGE_CONTEXT_SYSTEM_INSTRUCTION,
            )
        except LLMError as error:
            return self._response_composer.ask_knowledge_failure(request, str(error))
        return self._response_composer.ask_knowledge_success(
            request, answer, results, citations
        )

    @staticmethod
    def _knowledge_context_query(request: BrainRequest) -> str:
        if request.metadata.get("intent") == "knowledge_context":
            return request.message.strip()
        return request.message[len("knowledge context") :].strip()

    def _process_knowledge_context(self, request: BrainRequest) -> BrainResponse:
        """Return bounded local context without mutating conversation memory."""
        query = self._knowledge_context_query(request)
        if not query:
            return self._response_composer.knowledge_context_failure(
                request,
                "A knowledge context query is required.",
            )
        try:
            results = self._knowledge_engine.search(query)
        except KnowledgeError as error:
            return self._response_composer.knowledge_context_failure(
                request,
                f"Knowledge context failed: {error}",
            )
        return self._response_composer.knowledge_context_success(
            request,
            results[:KNOWLEDGE_CONTEXT_MAX_RESULTS],
        )

    @staticmethod
    def _is_knowledge_graph_request(request: BrainRequest) -> bool:
        declared_intent = request.metadata.get("intent")
        normalized_message = request.message.casefold().strip()
        return (
            declared_intent == "knowledge_graph"
            or normalized_message == "knowledge graph"
            or normalized_message.startswith("knowledge graph ")
        )

    @staticmethod
    def _knowledge_graph_query(request: BrainRequest) -> str:
        if request.metadata.get("intent") == "knowledge_graph":
            return request.message.strip()
        return request.message[len("knowledge graph") :].strip()

    def _process_knowledge_graph(self, request: BrainRequest) -> BrainResponse:
        """Inspect deterministic local source structure without memory or LLM use."""
        query = self._knowledge_graph_query(request)
        if not query:
            return self._response_composer.knowledge_graph_failure(
                request, "A knowledge graph query is required."
            )
        try:
            results = self._knowledge_engine.search(query)[
                :KNOWLEDGE_CONTEXT_MAX_RESULTS
            ]
            graph_view = self._knowledge_engine.graph_for_chunks(results)
        except KnowledgeError as error:
            return self._response_composer.knowledge_graph_failure(
                request, f"Knowledge graph failed: {error}"
            )
        return self._response_composer.knowledge_graph_success(
            request, results, graph_view
        )

    @staticmethod
    def _is_knowledge_list_request(request: BrainRequest) -> bool:
        return (
            request.metadata.get("intent") == "knowledge_list"
            or request.message.casefold().strip() == "list knowledge"
        )

    def _process_knowledge_list(self, request: BrainRequest) -> BrainResponse:
        """List local source identities without LLM or memory mutation."""
        return self._response_composer.knowledge_list_success(
            request, self._knowledge_engine.documents()
        )

    @staticmethod
    def _is_knowledge_relation_list_request(request: BrainRequest) -> bool:
        return (
            request.metadata.get("intent") == "knowledge_relation_list"
            or request.message.casefold().strip() == "list knowledge relations"
        )

    def _process_knowledge_relation_list(self, request: BrainRequest) -> BrainResponse:
        """List active explicit relations without mutating graph or memory state."""
        return self._response_composer.knowledge_relation_list_success(
            request, self._knowledge_engine.relations()
        )

    @staticmethod
    def _is_knowledge_relation_preview_request(request: BrainRequest) -> bool:
        normalized_message = request.message.casefold().strip()
        return (
            request.metadata.get("intent") == "knowledge_relation_preview"
            or normalized_message == "preview knowledge relation"
            or normalized_message.startswith("preview knowledge relation ")
        )

    @staticmethod
    def _knowledge_relation_preview_ids(
        request: BrainRequest,
    ) -> tuple[str, str] | None:
        value = (
            request.message.strip()
            if request.metadata.get("intent") == "knowledge_relation_preview"
            else request.message[len("preview knowledge relation") :].strip()
        )
        parts = value.split(" -- ")
        if len(parts) != 2 or not all(part.strip() for part in parts):
            return None
        return parts[0].strip(), parts[1].strip()

    def _process_knowledge_relation_preview(
        self,
        request: BrainRequest,
    ) -> BrainResponse:
        """Validate an explicit document relationship without changing graph state."""
        document_ids = self._knowledge_relation_preview_ids(request)
        if document_ids is None:
            return self._response_composer.knowledge_relation_preview_failure(
                request,
                "Knowledge relation preview format: preview knowledge relation "
                "<source_document_id> -- <target_document_id>",
            )
        try:
            preview = self._knowledge_engine.preview_document_relation(*document_ids)
        except KnowledgeError as error:
            return self._response_composer.knowledge_relation_preview_failure(
                request, f"Knowledge relation preview failed: {error}"
            )
        return self._response_composer.knowledge_relation_preview_success(
            request, preview
        )

    @staticmethod
    def _is_knowledge_relation_apply_request(request: BrainRequest) -> bool:
        normalized_message = request.message.casefold().strip()
        return (
            request.metadata.get("intent") == "knowledge_relation_apply"
            or normalized_message == "apply knowledge relation"
            or normalized_message.startswith("apply knowledge relation ")
        )

    @staticmethod
    def _knowledge_relation_apply_ids(
        request: BrainRequest,
    ) -> tuple[str, str] | None:
        value = (
            request.message.strip()
            if request.metadata.get("intent") == "knowledge_relation_apply"
            else request.message[len("apply knowledge relation") :].strip()
        )
        parts = value.split(" -- ")
        if len(parts) != 2 or not all(part.strip() for part in parts):
            return None
        return parts[0].strip(), parts[1].strip()

    def _process_knowledge_relation_apply(
        self,
        request: BrainRequest,
    ) -> BrainResponse:
        """Apply one explicit local document relationship without memory writes."""
        document_ids = self._knowledge_relation_apply_ids(request)
        if document_ids is None:
            return self._response_composer.knowledge_relation_apply_failure(
                request,
                "Knowledge relation apply format: apply knowledge relation "
                "<source_document_id> -- <target_document_id>",
            )
        try:
            application = self._knowledge_engine.apply_document_relation(*document_ids)
        except KnowledgeError as error:
            return self._response_composer.knowledge_relation_apply_failure(
                request, f"Knowledge relation apply failed: {error}"
            )
        return self._response_composer.knowledge_relation_apply_success(
            request, application
        )

    @staticmethod
    def _is_knowledge_relation_removal_preview_request(request: BrainRequest) -> bool:
        normalized_message = request.message.casefold().strip()
        return (
            request.metadata.get("intent") == "knowledge_relation_removal_preview"
            or normalized_message == "preview remove knowledge relation"
            or normalized_message.startswith("preview remove knowledge relation ")
        )

    @staticmethod
    def _knowledge_relation_removal_preview_ids(
        request: BrainRequest,
    ) -> tuple[str, str] | None:
        value = (
            request.message.strip()
            if request.metadata.get("intent") == "knowledge_relation_removal_preview"
            else request.message[len("preview remove knowledge relation") :].strip()
        )
        parts = value.split(" -- ")
        if len(parts) != 2 or not all(part.strip() for part in parts):
            return None
        return parts[0].strip(), parts[1].strip()

    def _process_knowledge_relation_removal_preview(
        self,
        request: BrainRequest,
    ) -> BrainResponse:
        """Preview an explicit relation removal without changing graph state."""
        document_ids = self._knowledge_relation_removal_preview_ids(request)
        if document_ids is None:
            return self._response_composer.knowledge_relation_removal_preview_failure(
                request,
                "Knowledge relation removal preview format: preview remove "
                "knowledge relation <source_document_id> -- <target_document_id>",
            )
        try:
            preview = self._knowledge_engine.preview_document_relation_removal(
                *document_ids
            )
        except KnowledgeError as error:
            return self._response_composer.knowledge_relation_removal_preview_failure(
                request, f"Knowledge relation removal preview failed: {error}"
            )
        return self._response_composer.knowledge_relation_removal_preview_success(
            request, preview
        )

    @staticmethod
    def _is_knowledge_relation_remove_request(request: BrainRequest) -> bool:
        normalized_message = request.message.casefold().strip()
        return (
            request.metadata.get("intent") == "knowledge_relation_remove"
            or normalized_message == "remove knowledge relation"
            or normalized_message.startswith("remove knowledge relation ")
        )

    @staticmethod
    def _knowledge_relation_remove_ids(
        request: BrainRequest,
    ) -> tuple[str, str] | None:
        value = (
            request.message.strip()
            if request.metadata.get("intent") == "knowledge_relation_remove"
            else request.message[len("remove knowledge relation") :].strip()
        )
        parts = value.split(" -- ")
        if len(parts) != 2 or not all(part.strip() for part in parts):
            return None
        return parts[0].strip(), parts[1].strip()

    def _process_knowledge_relation_remove(
        self,
        request: BrainRequest,
    ) -> BrainResponse:
        """Remove one explicit local relationship without conversation writes."""
        document_ids = self._knowledge_relation_remove_ids(request)
        if document_ids is None:
            return self._response_composer.knowledge_relation_remove_failure(
                request,
                "Knowledge relation remove format: remove knowledge relation "
                "<source_document_id> -- <target_document_id>",
            )
        try:
            revocation = self._knowledge_engine.remove_document_relation(*document_ids)
        except KnowledgeError as error:
            return self._response_composer.knowledge_relation_remove_failure(
                request, f"Knowledge relation remove failed: {error}"
            )
        return self._response_composer.knowledge_relation_remove_success(
            request, revocation
        )

    @staticmethod
    def _search_query(request: BrainRequest) -> str:
        if request.metadata.get("intent") == "search":
            return request.message.strip()
        return request.message[7:].strip()

    @staticmethod
    def _is_plan_request(request: BrainRequest) -> bool:
        declared_intent = request.metadata.get("intent")
        normalized_message = request.message.casefold().strip()
        return (
            declared_intent == "plan"
            or normalized_message == "plan"
            or normalized_message.startswith("plan ")
        )

    @staticmethod
    def _plan_goal(request: BrainRequest) -> str:
        if request.metadata.get("intent") == "plan":
            return request.message.strip()
        return request.message[5:].strip()

    @staticmethod
    def _is_recall_request(request: BrainRequest) -> bool:
        declared_intent = request.metadata.get("intent")
        normalized_message = request.message.casefold().strip()
        return (
            declared_intent == "recall"
            or normalized_message == "recall"
            or normalized_message.startswith("recall ")
        )

    @staticmethod
    def _recall_query(request: BrainRequest) -> str:
        if request.metadata.get("intent") == "recall":
            return request.message.strip()
        return request.message[7:].strip()

    @staticmethod
    def _is_semantic_recall_request(request: BrainRequest) -> bool:
        declared_intent = request.metadata.get("intent")
        normalized_message = request.message.casefold().strip()
        return (
            declared_intent == "semantic_recall"
            or normalized_message == "semantic recall"
            or normalized_message.startswith("semantic recall ")
        )

    @staticmethod
    def _is_semantic_recall_status_request(request: BrainRequest) -> bool:
        """Return whether a request asks for a read-only semantic status view."""
        return (
            request.metadata.get("intent") == "semantic_recall_status"
            or request.message.casefold().strip() == "semantic recall status"
        )

    @staticmethod
    def _is_semantic_recall_retry_request(request: BrainRequest) -> bool:
        """Return whether a request explicitly asks for a full semantic retry."""
        return (
            request.metadata.get("intent") == "semantic_recall_retry"
            or request.message.casefold().strip() == "semantic recall retry"
        )

    def _process_semantic_recall_status(self, request: BrainRequest) -> BrainResponse:
        """Expose derived semantic-index health without querying or mutating it."""
        runtime = self._semantic_memory_index_runtime
        if runtime is None:
            return self._response_composer.semantic_recall_status(
                request,
                runtime_state="disabled",
                indexed_memory_records=None,
                embedding_dimension=None,
                last_rebuild_error=None,
                last_update_error=None,
            )

        index = runtime.current()
        if runtime.is_stopped():
            return self._response_composer.semantic_recall_status(
                request,
                runtime_state="stopped",
                indexed_memory_records=None,
                embedding_dimension=None,
                last_rebuild_error=runtime.last_rebuild_error(),
                last_update_error=runtime.last_update_error(),
            )
        if runtime.is_rebuilding():
            return self._response_composer.semantic_recall_status(
                request,
                runtime_state="refreshing" if index is not None else "initializing",
                indexed_memory_records=index.count() if index is not None else None,
                embedding_dimension=index.dimension if index is not None else None,
                last_rebuild_error=runtime.last_rebuild_error(),
                last_update_error=runtime.last_update_error(),
            )
        if runtime.is_updating():
            return self._response_composer.semantic_recall_status(
                request,
                runtime_state="updating",
                indexed_memory_records=index.count() if index is not None else None,
                embedding_dimension=index.dimension if index is not None else None,
                last_rebuild_error=runtime.last_rebuild_error(),
                last_update_error=runtime.last_update_error(),
            )
        if index is None:
            last_rebuild_error = runtime.last_rebuild_error()
            return self._response_composer.semantic_recall_status(
                request,
                runtime_state=(
                    "unavailable" if last_rebuild_error is not None else "initializing"
                ),
                indexed_memory_records=None,
                embedding_dimension=None,
                last_rebuild_error=last_rebuild_error,
                last_update_error=runtime.last_update_error(),
            )

        return self._response_composer.semantic_recall_status(
            request,
            runtime_state="ready",
            indexed_memory_records=index.count(),
            embedding_dimension=index.dimension,
            last_rebuild_error=runtime.last_rebuild_error(),
            last_update_error=runtime.last_update_error(),
        )

    def _process_semantic_recall_retry(self, request: BrainRequest) -> BrainResponse:
        """Retry one complete bounded rebuild only after an explicit request."""
        runtime = self._semantic_memory_index_runtime
        if runtime is None:
            return self._response_composer.semantic_recall_retry_failure(
                request,
                "Semantic recall runtime is disabled.",
            )
        start_result = runtime.start_refresh(self._memory_manager)
        if start_result == "started":
            return self._response_composer.semantic_recall_retry_started(
                request,
                already_running=False,
            )
        if start_result == "already_running":
            return self._response_composer.semantic_recall_retry_started(
                request,
                already_running=True,
            )
        if start_result == "stopped":
            return self._response_composer.semantic_recall_retry_failure(
                request,
                "Semantic recall runtime is stopped.",
            )
        return self._response_composer.semantic_recall_retry_failure(
            request,
            "Semantic recall retry could not be started.",
        )

    @staticmethod
    def _semantic_recall_query(request: BrainRequest) -> str:
        if request.metadata.get("intent") == "semantic_recall":
            return request.message.strip()
        return request.message[len("semantic recall") :].strip()

    def _process_semantic_recall(self, request: BrainRequest) -> BrainResponse:
        """Use opt-in semantic results and fall back to lexical recall safely."""
        try:
            session_id = self._resolve_session_id(request)
            query = self._semantic_recall_query(request)
            if not query:
                return self._response_composer.semantic_recall_failure(
                    request,
                    "A semantic recall query is required.",
                )
        except SessionError as error:
            return self._response_composer.session_failure(request, str(error))

        runtime = self._semantic_memory_index_runtime
        if runtime is not None:
            try:
                matches = runtime.search(query, limit=None)
                semantic_records = self._semantic_session_records(matches, session_id)
            except MemoryError:
                semantic_records = []
            if semantic_records:
                try:
                    lexical_records = self._lexical_recall_records(query, session_id)
                except MemoryError:
                    lexical_records = []
                if lexical_records:
                    hybrid_records = self._hybrid_session_records(
                        semantic_records,
                        lexical_records,
                        session_id,
                    )
                    if hybrid_records:
                        return self._response_composer.semantic_recall_success(
                            request,
                            hybrid_records[:5],
                            retrieval="hybrid",
                        )
                return self._response_composer.semantic_recall_success(
                    request,
                    semantic_records[:5],
                    retrieval="semantic",
                )

        try:
            lexical_records = self._lexical_recall_records(query, session_id)
        except MemoryError as error:
            return self._response_composer.semantic_recall_failure(request, str(error))
        return self._response_composer.semantic_recall_success(
            request,
            [(record, None) for record in lexical_records[:5]],
            retrieval="lexical fallback",
        )

    def _semantic_session_records(
        self,
        matches: tuple[SemanticMemoryMatch, ...],
        session_id: str,
    ) -> list[tuple[MemoryRecord, float]]:
        records: list[tuple[MemoryRecord, float]] = []
        for match in matches:
            record = self._memory_manager.get(match.memory_id)
            if record is None or not self._is_session_conversation_record(
                record, session_id
            ):
                continue
            records.append((record, match.score))
        return records

    def _hybrid_session_records(
        self,
        semantic_records: list[tuple[MemoryRecord, float]],
        lexical_records: list[MemoryRecord],
        session_id: str,
    ) -> list[tuple[MemoryRecord, float]]:
        """Fuse already session-scoped candidates, then re-check live records."""
        ranked_matches = self._hybrid_semantic_memory_ranker.rank(
            tuple(
                SemanticMemoryMatch(memory_id=record.memory_id, score=score)
                for record, score in semantic_records
            ),
            tuple(lexical_records),
        )
        records: list[tuple[MemoryRecord, float]] = []
        for match in ranked_matches:
            record = self._memory_manager.get(match.memory_id)
            if record is None or not self._is_session_conversation_record(
                record, session_id
            ):
                continue
            records.append((record, match.score))
        return records

    def _lexical_recall_records(
        self,
        query: str,
        session_id: str,
    ) -> list[MemoryRecord]:
        records = self._memory_manager.search(
            query,
            tags={"brain", "conversation"},
            limit=None,
        )
        return [
            record
            for record in records
            if self._is_session_conversation_record(record, session_id)
        ]

    @staticmethod
    def _is_session_conversation_record(record: MemoryRecord, session_id: str) -> bool:
        return {"brain", "conversation"}.issubset(record.tags) and record.metadata.get(
            "session_id", "default"
        ) == session_id

    def _process_conversation(self, request: BrainRequest) -> BrainResponse:
        """Process the deterministic greeting and message conversation flow."""
        try:
            session_id = self._resolve_session_id(request)
        except SessionError as error:
            return self._response_composer.session_failure(request, str(error))

        context = BrainContext(request=request)
        self._event_bus.emit(
            "brain.request.received",
            {"request_id": request.request_id, "message": request.message},
            source="brain",
        )
        context.intent = self._router.detect_intent(request)
        self._event_bus.emit(
            "brain.intent.detected",
            {"request_id": request.request_id, "intent": context.intent},
            source="brain",
        )

        live_information_kind = self._research_honesty_service.detect(request)
        if live_information_kind.detected:
            response = self._research_honesty_service.process(
                request,
                live_information_kind,
            )
        elif context.intent == "message" and self._llm_provider is not None:
            try:
                history = build_llm_conversation_history(
                    tuple(self._memory_manager.all()),
                    session_id,
                    max_turns=self._llm_history_max_turns,
                )
                learned_memory_context = self._learned_memory_context_service(
                    request
                ).build(self._memory_manager, request.message)
                provider_prompt = build_learned_memory_augmented_prompt(
                    user_message=request.message,
                    learned_memory_context=learned_memory_context,
                )
                generated = self._llm_provider.generate(
                    provider_prompt,
                    history=history,
                )
                response = BrainResponse(
                    message=self._conversation_research_claim_guard.annotate(
                        generated,
                        self._research_honesty_service.summary(),
                    ),
                    request_id=request.request_id,
                    intent="message",
                    memory_count=0,
                )
                try:
                    batch = self._learned_memory_candidate_extractor.extract(
                        request.message
                    )
                except LearnedMemoryCandidateExtractionError as error:
                    batch = None
                    self._emit_learned_memory_extraction_failure(request, error)
                if batch is not None:
                    persist_learned_memory_candidate_batch(
                        self._memory_manager,
                        batch,
                    )
            except LLMError as error:
                response = BrainResponse(
                    message=str(error),
                    request_id=request.request_id,
                    intent="message",
                    memory_count=0,
                    success=False,
                )
                self._event_bus.emit(
                    "brain.response.ready",
                    {"request_id": response.request_id, "intent": response.intent},
                    source="brain",
                )
                return response
        else:
            response = (
                self._response_composer.greeting(request)
                if context.intent == "greeting"
                else self._response_composer.message(request)
            )
        memory_metadata = {
            "request_id": request.request_id,
            "intent": response.intent,
            "user_message": request.message,
            "assistant_message": response.message,
        }
        memory_metadata["session_id"] = session_id
        self._memory_manager.add(
            f"User: {request.message}\nHypatia: {response.message}",
            metadata=memory_metadata,
            tags={"brain", "conversation"},
        )
        self._event_bus.emit(
            "brain.response.ready",
            {"request_id": response.request_id, "intent": response.intent},
            source="brain",
        )
        return response

    def _learned_memory_context_service(
        self,
        request: BrainRequest,
    ) -> LearnedMemoryContextService:
        """Build the per-turn context service for the current configuration."""
        semantic_runtime = (
            self._semantic_memory_index_runtime
            if self._chat_semantic_memory_enabled
            else None
        )
        return LearnedMemoryContextService(
            selector=self._learned_memory_selector,
            context_limit=self._learned_memory_context_limit,
            semantic_runtime=semantic_runtime,
            on_semantic_failure=(
                lambda cause: self._emit_chat_semantic_memory_failure(request, cause)
            ),
        )

    def _emit_chat_semantic_memory_failure(
        self,
        request: BrainRequest,
        cause: str,
    ) -> None:
        """Report a bounded semantic-query failure without exposing content."""
        self._event_bus.emit(
            "brain.chat_semantic_memory.query_failed",
            {"request_id": request.request_id, "cause": cause},
            source="brain",
        )

    def _emit_learned_memory_extraction_failure(
        self,
        request: BrainRequest,
        error: LearnedMemoryCandidateExtractionError,
    ) -> None:
        """Report a bounded extraction failure without exposing any content."""
        cause = error.__cause__
        self._event_bus.emit(
            "brain.learned_memory.extraction_failed",
            {
                "request_id": request.request_id,
                "cause": type(cause).__name__ if cause is not None else "unknown",
            },
            source="brain",
        )

    def _resolve_session_id(self, request: BrainRequest) -> str:
        value = request.metadata.get("session_id")

        if value is None or (isinstance(value, str) and not value.strip()):
            return self._session_manager.get_active().session_id

        if not isinstance(value, str):
            raise SessionError("session_id must be a string.")

        normalized = value.strip()
        if not self._session_manager.exists(normalized):
            raise SessionError(f"Unknown session: {normalized}")
        return normalized

    def _process_session_command(
        self,
        request: BrainRequest,
        intent: str,
    ) -> BrainResponse:
        try:
            if intent == "session_create":
                result = self._session_create_service.create(
                    self._session_command_id(request, "create session")
                )
                if result.created:
                    return self._response_composer.session_created(
                        request,
                        result.session,
                    )
                return self._response_composer.session_exists(request, result.session)
            if intent == "session_list":
                return self._response_composer.sessions_list(
                    request,
                    self._session_manager.list(),
                    self._session_manager.get_active(),
                )
            session = self._session_use_service.use(
                self._session_command_id(request, "use session")
            )
            return self._response_composer.session_activated(request, session)
        except SessionError as error:
            if intent == "session_create":
                return self._response_composer.session_create_failure(
                    request, str(error)
                )
            return self._response_composer.session_failure(request, str(error))

    def _process_session_rename(self, request: BrainRequest) -> BrainResponse:
        """Execute an explicit session rename without conversation side effects."""
        try:
            source_session_id, target_session_id = self._session_rename_parts(request)
            result = self._session_rename_service.rename(
                source_session_id,
                target_session_id,
            )
        except (SessionError, MemoryError, ValueError, RuntimeError) as error:
            return self._response_composer.session_rename_failure(request, str(error))
        return self._response_composer.session_renamed(request, result)

    def _process_session_rename_preview(self, request: BrainRequest) -> BrainResponse:
        """Preview an explicit session rename without any side effects."""
        try:
            source_session_id, target_session_id = self._session_rename_parts(
                request,
                command_prefix="preview rename session",
            )
            preview = self._session_rename_service.preview(
                source_session_id,
                target_session_id,
            )
        except (SessionError, MemoryError, ValueError, RuntimeError) as error:
            return self._response_composer.session_rename_preview_failure(
                request,
                str(error),
            )
        return self._response_composer.session_rename_preview(request, preview)

    def _process_session_delete_preview(self, request: BrainRequest) -> BrainResponse:
        """Preview a deletion without changing either store or emitting events."""
        try:
            (
                session_id,
                memory_ids,
                decision_status,
                decision_reason,
            ) = self._session_delete_preview_service.preview(
                self._session_command_id(request, "preview delete session")
            )
        except (SessionError, MemoryError, ValueError, RuntimeError) as error:
            return self._response_composer.session_delete_preview_failure(
                request,
                str(error),
            )
        return self._response_composer.session_delete_preview(
            request,
            session_id,
            memory_ids,
            decision_status,
            decision_reason,
        )

    def _process_session_delete(self, request: BrainRequest) -> BrainResponse:
        """Execute a delete only when the service confirms its commit."""
        try:
            result = self._session_delete_service.delete(
                self._session_command_id(request, "delete session")
            )
        except SessionDeleteEventError as error:
            if error.result.committed is not True:
                raise ValueError(
                    "Session delete event failure result must be committed."
                ) from error
            return self._response_composer.session_delete_event_failure(
                request,
                error.result,
            )
        except (SessionError, MemoryError, ValueError, RuntimeError) as error:
            return self._response_composer.session_delete_failure(
                request,
                str(error),
            )
        if result.committed is not True:
            raise ValueError("Session delete result must be committed.")
        return self._response_composer.session_deleted(request, result)

    def _process_session_rename_candidates(
        self, request: BrainRequest
    ) -> BrainResponse:
        """List source sessions that are eligible for an explicit rename."""
        sessions = [
            session
            for session in self._session_manager.list()
            if session.session_id != "default"
        ]
        active_session_id = self._session_manager.get_active().session_id
        return self._response_composer.session_rename_candidates(
            request,
            sessions,
            active_session_id,
        )

    def _process_session_rename_target_check(
        self, request: BrainRequest
    ) -> BrainResponse:
        """Check whether an explicit rename target is unused without side effects."""
        try:
            target_session_id = self._session_rename_target_id(request)
        except ValueError as error:
            return self._response_composer.session_rename_target_check_failure(
                request,
                str(error),
            )
        return self._response_composer.session_rename_target_check(
            request,
            target_session_id,
            not self._session_manager.exists(target_session_id),
        )

    def _process_session_overview(self, request: BrainRequest) -> BrainResponse:
        """Return a read-only overview of registered session conversations."""
        try:
            sessions = self._session_manager.list()
            conversation_counts = {session.session_id: 0 for session in sessions}

            for record in self._memory_manager.all():
                for session_id in conversation_counts:
                    if SessionMemoryPolicy.matches(record, session_id):
                        conversation_counts[session_id] += 1
                        break
            active_session_id = self._session_manager.get_active().session_id
        except MemoryError as error:
            return self._response_composer.session_overview_failure(request, str(error))

        return self._response_composer.session_overview(
            request,
            sessions,
            conversation_counts,
            active_session_id,
        )

    def _process_session_details(self, request: BrainRequest) -> BrainResponse:
        """Return a read-only conversation count for one command-selected session."""
        try:
            session_id = self._session_details_id(request)
            if not self._session_manager.exists(session_id):
                raise SessionError(f"Unknown session: {session_id}")
            session = self._session_record(session_id)
            conversation_count = sum(
                1
                for record in self._memory_manager.all()
                if SessionMemoryPolicy.matches(record, session_id)
            )
        except (SessionError, MemoryError, ValueError) as error:
            return self._response_composer.session_details_failure(request, str(error))
        return self._response_composer.session_details(
            request,
            session,
            conversation_count,
            self._session_manager.get_active().session_id == session_id,
        )

    def _process_session_activity(self, request: BrainRequest) -> BrainResponse:
        """Return a read-only first-and-last activity summary for one session."""
        try:
            session_id = self._session_activity_id(request)
            if not self._session_manager.exists(session_id):
                raise SessionError(f"Unknown session: {session_id}")
            session = self._session_record(session_id)
            records = [
                record
                for record in self._memory_manager.all()
                if SessionMemoryPolicy.matches(record, session_id)
            ]
            activity_times = [
                record.created_at for record in records if record.created_at is not None
            ]
            if activity_times:
                first_activity = min(activity_times)
                last_activity = max(activity_times)
            else:
                first_activity = None
                last_activity = None
        except (SessionError, MemoryError, ValueError) as error:
            return self._response_composer.session_activity_failure(request, str(error))
        return self._response_composer.session_activity(
            request,
            session,
            len(records),
            first_activity,
            last_activity,
        )

    def _process_session_recent(self, request: BrainRequest) -> BrainResponse:
        """Return five newest normal conversations for a command-selected session."""
        try:
            session_id = self._session_recent_id(request)
            if not self._session_manager.exists(session_id):
                raise SessionError(f"Unknown session: {session_id}")
            session = self._session_record(session_id)
            records = [
                record
                for record in self._memory_manager.all()
                if SessionMemoryPolicy.matches(record, session_id)
            ]
            recent_records = sorted(
                records,
                key=self._record_created_at,
                reverse=True,
            )[:5]
        except (SessionError, MemoryError, ValueError) as error:
            return self._response_composer.session_recent_failure(request, str(error))
        if not recent_records:
            return self._response_composer.session_recent_empty(request, session)
        return self._response_composer.session_recent(request, recent_records, session)

    def _process_session_search(self, request: BrainRequest) -> BrainResponse:
        """Find matching conversations for a command-selected session."""
        try:
            session_id, query = self._session_search_parts(request)
            if not self._session_manager.exists(session_id):
                raise SessionError(f"Unknown session: {session_id}")
            session = self._session_record(session_id)
            matching_records = [
                record
                for record in self._memory_manager.search(query, limit=None)
                if SessionMemoryPolicy.matches(record, session_id)
            ][:5]
        except (SessionError, MemoryError, ValueError) as error:
            return self._response_composer.session_search_failure(request, str(error))
        if not matching_records:
            return self._response_composer.session_search_empty(
                request,
                session,
                query,
            )
        return self._response_composer.session_search_results(
            request,
            session,
            query,
            matching_records,
        )

    def _process_recent_conversations(self, request: BrainRequest) -> BrainResponse:
        """Return recent normal conversation records for the resolved session."""
        try:
            session_id = self._resolve_session_id(request)
            limit = self._recent_conversation_limit(request)
            session = self._session_record(session_id)
            records = [
                record
                for record in self._memory_manager.all()
                if {"brain", "conversation"}.issubset(record.tags)
                and record.metadata.get("session_id", "default") == session_id
            ]
            recent_records = sorted(
                records,
                key=self._record_created_at,
                reverse=True,
            )[:limit]
        except (SessionError, MemoryError, ValueError) as error:
            return self._response_composer.recent_conversations_failure(
                request,
                str(error),
            )
        if not recent_records:
            return self._response_composer.recent_conversations_empty(request, session)
        return self._response_composer.recent_conversations(
            request,
            recent_records,
            session,
        )

    def _process_source_reputation(self, request: BrainRequest) -> BrainResponse:
        """Route the reputation intent, which reads and gates nothing."""
        service = self._source_reputation_service
        if service is None:
            return self._response_composer.source_reputation_rejected(
                request,
                "Research run persistence is unavailable.",
            )
        try:
            return service.process_report(request)
        except ResearchError as error:
            return self._response_composer.source_reputation_rejected(
                request,
                str(error),
            )

    @staticmethod
    def _is_hypothesis_request(request: BrainRequest) -> bool:
        """Return whether this request addresses the hypothesis engine."""
        service = HypothesisApplicationService
        return (
            service.is_propose_request(request)
            or service.is_support_request(request)
            or service.is_oppose_request(request)
            or service.is_test_evidence_request(request)
            or service.is_retract_relation_request(request)
            or service.is_history_request(request)
            or service.is_withdraw_request(request)
            or service.is_list_request(request)
        )

    def _process_hypothesis(self, request: BrainRequest) -> BrainResponse:
        """Route one hypothesis intent. There is deliberately no confirm."""
        service = self._hypothesis_service
        if service is None:
            return self._response_composer.hypothesis_rejected(
                request,
                "Research run persistence is unavailable.",
            )
        try:
            if service.is_propose_request(request):
                return service.process_propose(request)
            if service.is_support_request(request):
                return service.process_support(request)
            if service.is_oppose_request(request):
                return service.process_oppose(request)
            if service.is_test_evidence_request(request):
                return service.process_test_evidence(request)
            if service.is_retract_relation_request(request):
                return service.process_retract_relation(request)
            if service.is_history_request(request):
                return service.process_history(request)
            if service.is_withdraw_request(request):
                return service.process_withdraw(request)
            return service.process_list(request)
        except ResearchError as error:
            return self._response_composer.hypothesis_rejected(request, str(error))

    @staticmethod
    def _is_vulnerability_graph_request(request: BrainRequest) -> bool:
        """Return whether this request addresses the weakness taxonomy."""
        service = VulnerabilityGraphApplicationService
        return (
            service.is_family_record_request(request)
            or service.is_relation_record_request(request)
            or service.is_neighbourhood_request(request)
            or service.is_family_list_request(request)
        )

    def _process_vulnerability_graph(self, request: BrainRequest) -> BrainResponse:
        """Route one taxonomy intent. Nothing here targets a system."""
        service = self._vulnerability_graph_service
        try:
            if service.is_family_record_request(request):
                return service.process_family_record(request)
            if service.is_relation_record_request(request):
                return service.process_relation_record(request)
            if service.is_neighbourhood_request(request):
                return service.process_neighbourhood(request)
            return service.process_family_list(request)
        except ResearchError as error:
            return self._response_composer.vulnerability_graph_rejected(
                request,
                str(error),
            )

    def _process_security_posture(self, request: BrainRequest) -> BrainResponse:
        """Route the audit intent, which reads and contacts nothing."""
        service = self._security_agent_service
        if service is None:
            return self._response_composer.security_posture_rejected(
                request,
                "Research run persistence is unavailable.",
            )
        try:
            return service.process_audit(request)
        except ResearchError as error:
            return self._response_composer.security_posture_rejected(
                request,
                str(error),
            )

    @staticmethod
    def _is_knowledge_reconciliation_request(request: BrainRequest) -> bool:
        """Return whether this request addresses knowledge reconciliation."""
        service = KnowledgeReconciliationApplicationService
        return service.is_report_request(request) or service.is_knowledge_only_request(
            request
        )

    def _process_knowledge_reconciliation(
        self,
        request: BrainRequest,
    ) -> BrainResponse:
        """Route one reconciliation intent. Both of them only read."""
        service = self._knowledge_reconciliation_service
        if service.is_knowledge_only_request(request):
            return service.process_knowledge_only(request)
        return service.process_report(request)

    def _process_calibration(self, request: BrainRequest) -> BrainResponse:
        """Route the calibration intent, which reads and never writes."""
        service = self._calibration_service
        preparing_revision = CalibrationApplicationService.is_revision_prepare_request(
            request
        )
        reject = (
            self._response_composer.research_claim_revision_preparation_rejected
            if preparing_revision
            else self._response_composer.research_calibration_rejected
        )
        if service is None:
            return reject(
                request,
                "Research run persistence is unavailable.",
            )
        try:
            if preparing_revision:
                return service.process_revision_prepare(request)
            return service.process_report(request)
        except ResearchError as error:
            return reject(
                request,
                str(error),
            )

    @staticmethod
    def _is_plan_authorization_request(request: BrainRequest) -> bool:
        """Return whether this request addresses recording a human approval."""
        service = ResearchPlanAuthorizationApplicationService
        return (
            service.is_preview_request(request)
            or service.is_confirm_request(request)
            or service.is_list_request(request)
        )

    def _process_plan_authorization(self, request: BrainRequest) -> BrainResponse:
        """Route one approval intent. Nothing here starts research."""
        service = self._plan_authorization_service
        if service is None:
            return self._response_composer.research_plan_authorization_rejected(
                request,
                "Research plan approval is unavailable.",
            )
        try:
            if service.is_preview_request(request):
                return service.process_preview(request)
            if service.is_confirm_request(request):
                return service.process_confirm(request)
            return service.process_list(request)
        except ResearchError as error:
            return self._response_composer.research_plan_authorization_rejected(
                request,
                str(error),
            )

    @staticmethod
    def _is_failure_memory_request(request: BrainRequest) -> bool:
        """Return whether this request addresses failure memory."""
        service = FailureMemoryApplicationService
        return (
            service.is_preview_request(request)
            or service.is_store_request(request)
            or service.is_list_request(request)
            or service.is_recall_request(request)
            or service.is_hypothesis_store_request(request)
        )

    def _process_failure_memory(self, request: BrainRequest) -> BrainResponse:
        """Route one failure-memory intent, which never performs research."""
        service = self._failure_memory_service
        if service is None:
            return self._response_composer.failure_memory_rejected(
                request,
                "Research run persistence is unavailable.",
            )
        try:
            if service.is_preview_request(request):
                return service.process_preview(request)
            if service.is_store_request(request):
                return service.process_store(request)
            if service.is_hypothesis_store_request(request):
                return service.process_hypothesis_store(request)
            if service.is_recall_request(request):
                return service.process_recall(request)
            return service.process_list(request)
        except ResearchError as error:
            return self._response_composer.failure_memory_rejected(
                request,
                str(error),
            )

    @staticmethod
    def _is_reflection_request(request: BrainRequest) -> bool:
        """Return whether this request addresses the reflection engine."""
        service = ReflectionApplicationService
        return (
            service.is_preview_request(request)
            or service.is_store_request(request)
            or service.is_list_request(request)
        )

    def _process_reflection(self, request: BrainRequest) -> BrainResponse:
        """Route one reflection intent, which never performs research."""
        service = self._reflection_service
        if service is None:
            return self._response_composer.research_reflection_rejected(
                request,
                "Research run persistence is unavailable.",
            )
        try:
            if service.is_preview_request(request):
                return service.process_preview(request)
            if service.is_store_request(request):
                return service.process_store(request)
            return service.process_list(request)
        except ResearchError as error:
            return self._response_composer.research_reflection_rejected(
                request,
                str(error),
            )

    @staticmethod
    def _is_curiosity_request(request: BrainRequest) -> bool:
        """Return whether this request addresses the curiosity engine."""
        service = CuriosityApplicationService
        return (
            service.is_gap_detect_request(request)
            or service.is_question_preview_request(request)
            or service.is_question_store_request(request)
            or service.is_question_list_request(request)
            or service.is_question_accept_request(request)
            or service.is_question_dismiss_request(request)
            or service.is_prepare_proposal_request(request)
            or service.is_authorize_proposal_request(request)
            or service.is_start_authorized_proposal_request(request)
        )

    def _process_curiosity(self, request: BrainRequest) -> BrainResponse:
        """Route one curiosity intent, which never performs research."""
        service = self._curiosity_service
        if service is None:
            return self._response_composer.curiosity_rejected(
                request,
                "Research run persistence is unavailable.",
            )
        try:
            if service.is_gap_detect_request(request):
                return service.process_gap_detect(request)
            if service.is_question_preview_request(request):
                return service.process_question_preview(request)
            if service.is_question_store_request(request):
                return service.process_question_store(request)
            if service.is_question_list_request(request):
                return service.process_question_list(request)
            if service.is_question_accept_request(request):
                return service.process_question_accept(request)
            if service.is_prepare_proposal_request(request):
                return service.process_prepare_proposal(request)
            if service.is_authorize_proposal_request(request):
                return service.process_authorize_proposal(request)
            if service.is_start_authorized_proposal_request(request):
                return service.process_start_authorized_proposal(request)
            if service.is_resume_execution_request(request):
                return service.process_resume_execution(request)
            return service.process_question_dismiss(request)
        except ResearchError as error:
            return self._response_composer.curiosity_rejected(request, str(error))

    def _process_conversation_search(self, request: BrainRequest) -> BrainResponse:
        """Find matching normal conversation records in the resolved session."""
        try:
            query = self._conversation_search_query(request)
            session_id = self._resolve_session_id(request)
            records = self._memory_manager.search(query, limit=None)
            matching_records = [
                record
                for record in records
                if {"brain", "conversation"}.issubset(record.tags)
                and record.metadata.get("session_id", "default") == session_id
            ][:5]
            session = self._session_record(session_id)
        except (SessionError, MemoryError, ValueError) as error:
            return self._response_composer.conversation_search_failure(
                request,
                str(error),
            )
        if not matching_records:
            return self._response_composer.conversation_search_empty(request, session)
        return self._response_composer.conversation_search_results(
            request,
            matching_records,
            session,
        )

    @staticmethod
    def _conversation_search_query(request: BrainRequest) -> str:
        """Return the non-empty user-provided conversation search query."""
        query = request.message.strip()[len("search conversations") :].strip()
        if not query:
            raise ValueError("Search query must not be empty.")
        return query

    @staticmethod
    def _session_details_id(request: BrainRequest) -> str:
        """Return the non-empty, command-selected session ID without metadata."""
        session_id = request.message.strip()[len("session details") :].strip()
        if not session_id:
            raise ValueError("Session ID must not be empty.")
        return session_id

    @staticmethod
    def _session_recent_id(request: BrainRequest) -> str:
        """Return the complete non-empty session-recent command suffix."""
        session_id = request.message.strip()[len("session recent") :].strip()
        if not session_id:
            raise ValueError("Session ID must not be empty.")
        return session_id

    @staticmethod
    def _session_activity_id(request: BrainRequest) -> str:
        """Return the complete non-empty session-activity command suffix."""
        session_id = request.message.strip()[len("session activity") :].strip()
        if not session_id:
            raise ValueError("Session ID must not be empty.")
        return session_id

    @staticmethod
    def _session_search_parts(request: BrainRequest) -> tuple[str, str]:
        """Return validated session-search command fields without metadata access."""
        remainder = request.message.strip()[len("session search") :]
        session_part, separator, query_part = remainder.partition(" -- ")
        if not separator:
            if remainder.endswith(" --"):
                session_part = remainder[:-3]
                query_part = ""
            else:
                raise ValueError("Search query separator is required: --")

        session_id = session_part.strip()
        if not session_id:
            raise ValueError("Session ID must not be empty.")

        query = query_part.strip()
        if not query:
            raise ValueError("Search query must not be empty.")
        return session_id, query

    @staticmethod
    def _session_rename_parts(
        request: BrainRequest,
        *,
        command_prefix: str = "rename session",
    ) -> tuple[str, str]:
        """Return validated source and target IDs from an explicit rename command."""
        remainder = request.message.strip()[len(command_prefix) :]
        source_part, separator, target_part = remainder.partition(" -- ")
        if not separator:
            if remainder.endswith(" --"):
                source_part = remainder[:-3]
                target_part = ""
            else:
                raise ValueError("Session rename separator is required: --")

        source_session_id = source_part.strip()
        if not source_session_id:
            raise ValueError("Session source ID must not be empty.")
        target_session_id = target_part.strip()
        if not target_session_id:
            raise ValueError("Session target ID must not be empty.")
        return source_session_id, target_session_id

    @staticmethod
    def _session_rename_target_id(request: BrainRequest) -> str:
        """Return the validated target ID from an explicit availability command."""
        target_session_id = request.message.strip()[
            len("check rename target") :
        ].strip()
        if not target_session_id:
            raise ValueError("Session target ID must not be empty.")
        return target_session_id

    @staticmethod
    def _recent_conversation_limit(request: BrainRequest) -> int:
        """Return the validated optional count from a recent-conversations command."""
        remainder = request.message.strip()[len("recent conversations") :].strip()
        if not remainder:
            return 5

        try:
            limit = int(remainder)
        except ValueError as error:
            raise ValueError("Count must be an integer.") from error

        if not 1 <= limit <= 20:
            raise ValueError("Count must be between 1 and 20.")
        return limit

    def _session_record(self, session_id: str) -> SessionRecord:
        """Return the registry record for an already resolved session ID."""
        return next(
            session
            for session in self._session_manager.list()
            if session.session_id == session_id
        )

    @staticmethod
    def _record_created_at(record: MemoryRecord) -> datetime:
        """Return a deterministic ordering timestamp for a memory record."""
        return record.created_at or datetime.min.replace(tzinfo=UTC)

    @staticmethod
    def _session_command_id(request: BrainRequest, command: str) -> str:
        return request.message.strip()[len(command) :].strip()

    def _remember_search(
        self,
        request: BrainRequest,
        response: BrainResponse,
        query: str,
    ) -> None:
        """Store a compact search exchange without affecting the response."""
        try:
            self._memory_manager.add(
                f"User: {request.message}\nHypatia: {response.message}",
                metadata={
                    "intent": "search",
                    "query": query,
                    "result_count": len(response.knowledge_results),
                    "success": response.success,
                },
                tags={"cognition", "knowledge-search", "conversation"},
            )
        except MemoryError:
            pass
