"""Cognitive orchestration entry point."""

from __future__ import annotations

from typing import TYPE_CHECKING

from brain.BrainContext import BrainContext
from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from brain.BrainRouter import BrainRouter
from core.Exceptions import KnowledgeError, MemoryError, PlannerError
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.MemoryManager import MemoryManager

if TYPE_CHECKING:
    from planner.Plan import Plan
    from planner.Planner import Planner


class CognitiveEngine:
    """Coordinates the first knowledge-backed cognitive request flow."""

    def __init__(
        self,
        knowledge_engine: KnowledgeEngine,
        memory_manager: MemoryManager,
        planner: Planner,
        event_bus: EventBus,
    ) -> None:
        self._knowledge_engine = knowledge_engine
        self._memory_manager = memory_manager
        self._planner = planner
        self._event_bus = event_bus
        self._router = BrainRouter()

    def process(self, request: BrainRequest) -> BrainResponse:
        """Process a request using the currently supported cognitive intent."""
        if self._is_search_request(request):
            query = self._search_query(request)
            if not query:
                response = BrainResponse(
                    message="A search query is required.",
                    request_id=request.request_id,
                    intent="search",
                    memory_count=0,
                    success=False,
                )
                self._remember_search(request, response, query)
                return response

            try:
                knowledge_results = self._knowledge_engine.search(query)
            except KnowledgeError as error:
                response = BrainResponse(
                    message=f"Knowledge search failed: {error}",
                    request_id=request.request_id,
                    intent="search",
                    memory_count=0,
                    success=False,
                )
                self._remember_search(request, response, query)
                return response

            response = BrainResponse(
                message=(
                    f"I found {len(knowledge_results)} matching knowledge chunks."
                ),
                request_id=request.request_id,
                intent="search",
                memory_count=0,
                knowledge_results=knowledge_results,
            )
            self._remember_search(request, response, query)
            return response

        if self._is_plan_request(request):
            goal = self._plan_goal(request)
            if not goal:
                return BrainResponse(
                    message="A planning goal is required.",
                    request_id=request.request_id,
                    intent="plan",
                    memory_count=0,
                    success=False,
                )

            try:
                plan = self._planner.create_plan(goal)
            except PlannerError as error:
                return BrainResponse(
                    message=f"Planning failed: {error}",
                    request_id=request.request_id,
                    intent="plan",
                    memory_count=0,
                    success=False,
                )

            return BrainResponse(
                message=self._format_plan(plan),
                request_id=request.request_id,
                intent="plan",
                memory_count=0,
            )

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
    def _format_plan(plan: Plan) -> str:
        task_lines = "\n".join(f"{task.order}. {task.title}" for task in plan.tasks)
        return f"Plan created for: {plan.goal.description}\n\n{task_lines}"

    def _process_conversation(self, request: BrainRequest) -> BrainResponse:
        """Process the deterministic greeting and message conversation flow."""
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

        response = BrainResponse(
            message=self._compose_response(context),
            request_id=request.request_id,
            intent=context.intent,
            memory_count=0,
        )
        self._memory_manager.add(
            f"User: {request.message}\nHypatia: {response.message}",
            metadata={"request_id": request.request_id, "intent": response.intent},
            tags={"brain", "conversation"},
        )
        self._event_bus.emit(
            "brain.response.ready",
            {"request_id": response.request_id, "intent": response.intent},
            source="brain",
        )
        return response

    @staticmethod
    def _compose_response(context: BrainContext) -> str:
        if context.intent == "greeting":
            return "Hello! I am Hypatia."
        return f"I received your message: {context.request.message}"

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

    @staticmethod
    def _unsupported_response(request: BrainRequest, message: str) -> BrainResponse:
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="unsupported",
            memory_count=0,
        )
