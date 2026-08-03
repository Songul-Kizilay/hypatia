"""Cognitive orchestration entry point."""

from __future__ import annotations

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from core.Exceptions import KnowledgeError
from knowledge.KnowledgeEngine import KnowledgeEngine


class CognitiveEngine:
    """Coordinates the first knowledge-backed cognitive request flow."""

    def __init__(self, knowledge_engine: KnowledgeEngine) -> None:
        self._knowledge_engine = knowledge_engine

    def process(self, request: BrainRequest) -> BrainResponse:
        """Process a request using the currently supported cognitive intent."""
        if self._is_search_request(request):
            query = self._search_query(request)
            if not query:
                return BrainResponse(
                    message="A search query is required.",
                    request_id=request.request_id,
                    intent="search",
                    memory_count=0,
                    success=False,
                )

            try:
                knowledge_results = self._knowledge_engine.search(query)
            except KnowledgeError as error:
                return BrainResponse(
                    message=f"Knowledge search failed: {error}",
                    request_id=request.request_id,
                    intent="search",
                    memory_count=0,
                    success=False,
                )

            return BrainResponse(
                message=(
                    f"I found {len(knowledge_results)} matching knowledge chunks."
                ),
                request_id=request.request_id,
                intent="search",
                memory_count=0,
                knowledge_results=knowledge_results,
            )

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

    @staticmethod
    def _unsupported_response(request: BrainRequest, message: str) -> BrainResponse:
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="unsupported",
            memory_count=0,
        )
