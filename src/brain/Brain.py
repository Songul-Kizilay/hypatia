"""Entry point for deterministic Brain request processing."""

from __future__ import annotations

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from cognition.CognitiveEngine import CognitiveEngine
from core.Exceptions import BrainError
from eventbus.EventBus import EventBus
from memory.MemoryManager import MemoryManager


class Brain:
    """Normalizes incoming requests and delegates them to cognition."""

    def __init__(
        self,
        cognitive_engine: CognitiveEngine,
        memory_manager: MemoryManager,
        event_bus: EventBus,
    ) -> None:
        self._cognitive_engine = cognitive_engine

    def process(self, request: BrainRequest | str) -> BrainResponse:
        """Normalize a request and delegate processing to cognition."""
        brain_request = self._normalize_request(request)
        return self._cognitive_engine.process(brain_request)

    @staticmethod
    def _normalize_request(request: BrainRequest | str) -> BrainRequest:
        if isinstance(request, BrainRequest):
            if not request.message.strip():
                raise BrainError("Brain request message cannot be empty.")
            return request
        if not isinstance(request, str) or not request.strip():
            raise BrainError("Brain request message cannot be empty.")
        return BrainRequest(message=request.strip())
