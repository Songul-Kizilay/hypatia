"""First deterministic orchestration layer for the Hypatia Brain."""

from __future__ import annotations

from brain.BrainContext import BrainContext
from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from brain.BrainRouter import BrainRouter
from core.DependencyContainer import DependencyContainer
from eventbus.EventBus import EventBus
from memory.MemoryManager import MemoryManager


class Brain:
    """Coordinates the initial request, memory, event, and response flow."""

    def __init__(self, container: DependencyContainer) -> None:
        self._memory_manager = container.resolve(MemoryManager)
        self._event_bus = container.resolve(EventBus)
        self._router = BrainRouter()

    def process(self, message: str) -> BrainResponse:
        """Process a user message without involving an LLM or planner."""
        request = BrainRequest(message=message.strip())
        if not request.message:
            raise ValueError("Brain request message cannot be empty.")

        context = BrainContext(request=request)
        self._event_bus.emit(
            "brain.request.received",
            {"request_id": request.request_id, "message": request.message},
            source="brain",
        )

        context.memories = self._memory_manager.search(request.message, limit=5)
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
            memory_count=len(context.memories),
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
