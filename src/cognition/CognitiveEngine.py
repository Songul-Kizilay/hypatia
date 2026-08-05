"""Cognitive orchestration entry point."""

from __future__ import annotations

from typing import TYPE_CHECKING

from brain.BrainContext import BrainContext
from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from brain.BrainRouter import BrainRouter
from core.Exceptions import KnowledgeError, MemoryError, PlannerError, SessionError
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.MemoryManager import MemoryManager
from response.ResponseComposer import ResponseComposer
from session.SessionManager import SessionManager

if TYPE_CHECKING:
    from planner.Planner import Planner


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
    ) -> None:
        self._knowledge_engine = knowledge_engine
        self._memory_manager = memory_manager
        self._planner = planner
        self._event_bus = event_bus
        self._response_composer = response_composer
        self._session_manager = session_manager
        self._router = BrainRouter()

    def process(self, request: BrainRequest) -> BrainResponse:
        """Process a request using the currently supported cognitive intent."""
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
            except SessionError as error:
                return self._response_composer.session_failure(request, str(error))

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
            return self._response_composer.recall_success(request, session_records[:5])

        session_intent = self._router.detect_intent(request)
        if session_intent in {"session_create", "session_list", "session_use"}:
            return self._process_session_command(request, session_intent)

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

        response = (
            self._response_composer.greeting(request)
            if context.intent == "greeting"
            else self._response_composer.message(request)
        )
        memory_metadata = {
            "request_id": request.request_id,
            "intent": response.intent,
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
                result = self._session_manager.create(
                    self._session_command_id(request, "create session")
                )
                if result.created:
                    return self._response_composer.session_created(
                        request, result.session
                    )
                return self._response_composer.session_exists(request, result.session)
            if intent == "session_list":
                return self._response_composer.sessions_list(
                    request,
                    self._session_manager.list(),
                    self._session_manager.get_active(),
                )
            session = self._session_manager.set_active(
                self._session_command_id(request, "use session")
            )
            return self._response_composer.session_activated(request, session)
        except SessionError as error:
            return self._response_composer.session_failure(request, str(error))

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
