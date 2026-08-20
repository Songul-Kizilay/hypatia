"""Cognitive orchestration entry point."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from brain.BrainContext import BrainContext
from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from brain.BrainRouter import BrainRouter
from cognition.LLMConversationHistoryBuilder import (
    build_llm_conversation_history,
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
from knowledge.KnowledgeContextPrompt import build_knowledge_context_prompt
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
    load_bounded_learned_memory_context,
    load_current_selected_bounded_learned_memory_context,
    load_current_selected_learned_memory_context,
    load_learned_memory_context,
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
from research.ResearchRunManager import ResearchRunManager
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSourceCandidate import ResearchSourceCandidate
from research.ResearchSourceDiscoveryProvider import ResearchSourceDiscoveryProvider
from research.ResearchSourceFetcher import ResearchSourceFetcher
from response.ResponseComposer import ResponseComposer
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
        research_source_fetcher: ResearchSourceFetcher | None = None,
        research_run_manager: ResearchRunManager | None = None,
        research_source_discovery_provider: (
            ResearchSourceDiscoveryProvider | None
        ) = None,
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
        self._research_source_fetcher = research_source_fetcher
        self._research_run_manager = research_run_manager
        self._research_source_discovery_provider = research_source_discovery_provider
        self._hybrid_semantic_memory_ranker = HybridSemanticMemoryRanker()
        self._router = BrainRouter()

    def process(self, request: BrainRequest) -> BrainResponse:
        """Process a request using the currently supported cognitive intent."""
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

        if self._is_research_run_list_request(request):
            return self._process_research_run_list(request)

        if self._is_research_evidence_record_request(request):
            return self._process_research_evidence_record(request)

        if self._is_research_evidence_list_request(request):
            return self._process_research_evidence_list(request)

        if self._is_research_run_status_preview_request(request):
            return self._process_research_run_status_preview(request)

        if self._is_research_run_status_update_request(request):
            return self._process_research_run_status_update(request)

        if self._is_research_source_discover_request(request):
            return self._process_research_source_discover(request)

        if self._is_research_source_load_request(request):
            return self._process_research_source_load(request)

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
    def _is_research_run_create_request(request: BrainRequest) -> bool:
        """Recognize only an explicit structured research-run creation request."""
        return request.metadata.get("intent") == "research_run_create"

    @staticmethod
    def _is_research_run_list_request(request: BrainRequest) -> bool:
        """Recognize the explicit structured research-run catalog request."""
        return request.metadata.get("intent") == "research_run_list"

    @staticmethod
    def _is_research_evidence_record_request(request: BrainRequest) -> bool:
        """Recognize one explicit indexed-chunk evidence selection."""
        return request.metadata.get("intent") == "research_evidence_record"

    @staticmethod
    def _is_research_evidence_list_request(request: BrainRequest) -> bool:
        """Recognize one explicit read-only research evidence catalog request."""
        return request.metadata.get("intent") == "research_evidence_list"

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
        return self._response_composer.research_run_create_success(request, run)

    def _process_research_run_list(self, request: BrainRequest) -> BrainResponse:
        if self._research_run_manager is None:
            return self._response_composer.research_run_failure(
                request,
                "Research run persistence is unavailable.",
                intent="research_run_list",
            )
        return self._response_composer.research_run_list_success(
            request,
            self._research_run_manager.list(),
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

    def _process_research_evidence_list(self, request: BrainRequest) -> BrainResponse:
        run_id = request.metadata.get("research_run_id")
        if not isinstance(run_id, str) or not run_id.strip():
            return self._response_composer.research_evidence_list_failure(
                request,
                "A research run ID is required.",
            )
        if self._research_run_manager is None:
            return self._response_composer.research_evidence_list_failure(
                request,
                "Research run persistence is unavailable.",
            )
        try:
            run = self._research_run_manager.get(run_id)
        except ResearchError:
            return self._response_composer.research_evidence_list_failure(
                request,
                "Research run was not found.",
            )
        return self._response_composer.research_evidence_list_success(request, run)

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

        provider = self._research_source_discovery_provider
        try:
            candidates = provider.discover(run.question, limit=5)
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
        except ResearchError:
            try:
                self._research_run_manager.record_failure(
                    normalized_run_id,
                    "source_discovery",
                    "Research source discovery failed.",
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

    def _process_research_source_load(self, request: BrainRequest) -> BrainResponse:
        """Acquire and index one explicit source without LLM or memory side effects."""
        url = request.metadata.get("research_url")
        if not isinstance(url, str) or not url.strip():
            return self._response_composer.research_source_load_failure(
                request,
                "A research source URL is required.",
            )
        if self._research_source_fetcher is None:
            return self._response_composer.research_source_load_failure(
                request,
                "Internet research source loading is unavailable.",
            )
        run_id_value = request.metadata.get("research_run_id")
        run_id = run_id_value.strip() if isinstance(run_id_value, str) else ""
        if run_id_value is not None and not run_id:
            return self._response_composer.research_source_load_failure(
                request,
                "A valid research run ID is required.",
            )
        if run_id and self._research_run_manager is None:
            return self._response_composer.research_source_load_failure(
                request,
                "Research run persistence is unavailable.",
            )
        if run_id:
            assert self._research_run_manager is not None
            try:
                selected_run = self._research_run_manager.get(run_id)
            except ResearchError:
                return self._response_composer.research_source_load_failure(
                    request,
                    "Research run was not found.",
                )
            if selected_run.status.terminal:
                return self._response_composer.research_source_load_failure(
                    request,
                    "Research run is closed and cannot accept new sources.",
                )
        try:
            source = self._research_source_fetcher.fetch(url.strip())
            document = self._knowledge_engine.add_document(source.to_document())
        except (ResearchError, KnowledgeError) as error:
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
                    return self._response_composer.research_source_load_failure(
                        request,
                        (
                            "Research source failed and its audit record "
                            "could not be saved."
                        ),
                    )
            return self._response_composer.research_source_load_failure(
                request,
                f"Research source could not be loaded: {error}",
            )
        run = None
        if run_id and self._research_run_manager is not None:
            try:
                run = self._research_run_manager.add_source(
                    run_id,
                    source,
                    document.document_id,
                )
            except ResearchError:
                try:
                    self._knowledge_engine.remove_document(document.document_id)
                except KnowledgeError:
                    return self._response_composer.research_source_load_failure(
                        request,
                        "Research source audit failed and knowledge rollback failed.",
                    )
                return self._response_composer.research_source_load_failure(
                    request,
                    (
                        "Research source audit could not be saved; "
                        "knowledge was rolled back."
                    ),
                )
        loaded_document = next(
            reference
            for reference in self._knowledge_engine.documents()
            if reference.document_id == document.document_id
        )
        return self._response_composer.research_source_load_success(
            request,
            loaded_document,
            run=run,
        )

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
                build_knowledge_context_prompt(query, results, citations)
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

    def _process_semantic_recall_status(self, request: BrainRequest) -> BrainResponse:
        """Expose derived semantic-index health without querying or mutating it."""
        runtime = self._semantic_memory_index_runtime
        if runtime is None:
            return self._response_composer.semantic_recall_status(
                request,
                runtime_state="disabled",
                indexed_memory_records=None,
                embedding_dimension=None,
                last_update_error=None,
            )

        index = runtime.current()
        if index is None:
            return self._response_composer.semantic_recall_status(
                request,
                runtime_state="initializing",
                indexed_memory_records=None,
                embedding_dimension=None,
                last_update_error=runtime.last_update_error(),
            )

        return self._response_composer.semantic_recall_status(
            request,
            runtime_state="ready",
            indexed_memory_records=index.count(),
            embedding_dimension=index.dimension,
            last_update_error=runtime.last_update_error(),
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

        if context.intent == "message" and self._llm_provider is not None:
            try:
                history = build_llm_conversation_history(
                    tuple(self._memory_manager.all()),
                    session_id,
                    max_turns=self._llm_history_max_turns,
                )
                if self._learned_memory_selector is not None:
                    if self._learned_memory_context_limit is None:
                        learned_memory_context = (
                            load_current_selected_learned_memory_context(
                                memory_manager=self._memory_manager,
                                source_text=request.message,
                                selector=self._learned_memory_selector,
                            )
                        )
                    else:
                        learned_memory_context = (
                            load_current_selected_bounded_learned_memory_context(
                                memory_manager=self._memory_manager,
                                source_text=request.message,
                                selector=self._learned_memory_selector,
                                limit=self._learned_memory_context_limit,
                            )
                        )
                elif self._learned_memory_context_limit is None:
                    learned_memory_context = load_learned_memory_context(
                        self._memory_manager
                    )
                else:
                    learned_memory_context = load_bounded_learned_memory_context(
                        self._memory_manager,
                        self._learned_memory_context_limit,
                    )
                provider_prompt = build_learned_memory_augmented_prompt(
                    user_message=request.message,
                    learned_memory_context=learned_memory_context,
                )
                response = BrainResponse(
                    message=self._llm_provider.generate(
                        provider_prompt,
                        history=history,
                    ),
                    request_id=request.request_id,
                    intent="message",
                    memory_count=0,
                )
                try:
                    batch = self._learned_memory_candidate_extractor.extract(
                        request.message
                    )
                except LearnedMemoryCandidateExtractionError:
                    batch = None
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
