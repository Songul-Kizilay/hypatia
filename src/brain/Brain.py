"""Entry point for deterministic Brain request processing."""

from __future__ import annotations

from brain.BrainContext import BrainContext
from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from brain.BrainRouter import BrainRouter
from cognition.CognitiveEngine import CognitiveEngine
from core.Exceptions import BrainError
from eventbus.EventBus import EventBus
from memory.MemoryManager import MemoryManager


class Brain:
    """Routes knowledge searches and preserves existing local Brain behavior."""

    def __init__(
        self,
        cognitive_engine: CognitiveEngine,
        memory_manager: MemoryManager,
        event_bus: EventBus,
    ) -> None:
        self._cognitive_engine = cognitive_engine
        self._memory_manager = memory_manager
        self._event_bus = event_bus
        self._router = BrainRouter()

    def process(self, request: BrainRequest | str) -> BrainResponse:
        """Route a request to cognition or the existing deterministic Brain flow."""
        brain_request = self._normalize_request(request)
        normalized_message = brain_request.message.strip()
        if (
            brain_request.metadata.get("intent") == "search"
            or normalized_message.casefold() == "search"
            or normalized_message.casefold().startswith("search ")
        ):
            return self._cognitive_engine.process(brain_request)

        return self._process_local_request(brain_request)

    def _process_local_request(self, request: BrainRequest) -> BrainResponse:
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
    def _normalize_request(request: BrainRequest | str) -> BrainRequest:
        if isinstance(request, BrainRequest):
            if not request.message.strip():
                raise BrainError("Brain request message cannot be empty.")
            return request
        if not isinstance(request, str) or not request.strip():
            raise BrainError("Brain request message cannot be empty.")
        return BrainRequest(message=request.strip())

    @staticmethod
    def _compose_response(context: BrainContext) -> str:
        if context.intent == "greeting":
            return "Hello! I am Hypatia."
        return f"I received your message: {context.request.message}"
