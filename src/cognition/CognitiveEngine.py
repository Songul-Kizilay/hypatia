"""Cognitive orchestration entry point."""

from __future__ import annotations

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from core.Exceptions import KnowledgeError, MemoryError
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.MemoryManager import MemoryManager


class CognitiveEngine:
    """Coordinates the first knowledge-backed cognitive request flow."""

    def __init__(
        self,
        knowledge_engine: KnowledgeEngine,
        memory_manager: MemoryManager,
    ) -> None:
        self._knowledge_engine = knowledge_engine
        self._memory_manager = memory_manager

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

        return self._unsupported_response(request, "This intent is not supported yet.")

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
