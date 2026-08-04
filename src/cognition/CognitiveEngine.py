"""Cognitive orchestration entry point."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from brain.BrainContext import BrainContext
from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from brain.BrainRouter import BrainRouter
from core.Exceptions import KnowledgeError, MemoryError, PlannerError
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.MemoryManager import MemoryManager
from response.ResponseComposer import ResponseComposer

if TYPE_CHECKING:
    from planner.Planner import Planner


class CognitiveEngine:
    """Coordinates the first knowledge-backed cognitive request flow."""

    _DEFAULT_SESSION_ID = "default"

    def __init__(
        self,
        knowledge_engine: KnowledgeEngine,
        memory_manager: MemoryManager,
        planner: Planner,
        event_bus: EventBus,
        response_composer: ResponseComposer,
    ) -> None:
        self._knowledge_engine = knowledge_engine
        self._memory_manager = memory_manager
        self._planner = planner
        self._event_bus = event_bus
        self._response_composer = response_composer
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
            except ValueError:
                return self._session_failure(request)

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
                if record.metadata.get("session_id", self._DEFAULT_SESSION_ID)
                == session_id
            ]
            return self._response_composer.recall_success(request, session_records[:5])

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
        except ValueError:
            return self._session_failure(request)

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

        if value is None:
            return self._DEFAULT_SESSION_ID

        if not isinstance(value, str):
            raise ValueError("session_id must be a string.")

        normalized = value.strip()
        return normalized or self._DEFAULT_SESSION_ID

    def _session_failure(self, request: BrainRequest) -> BrainResponse:
        response = self._response_composer.message(request)
        return replace(
            response,
            message="session_id must be a string.",
            success=False,
        )

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
