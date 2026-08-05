"""Central response composition contract for Hypatia."""

from __future__ import annotations

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from knowledge.Chunk import Chunk
from memory.MemoryRecord import MemoryRecord
from planner.Plan import Plan
from session.SessionRecord import SessionRecord


class ResponseComposer:
    """Creates user-facing response models without orchestration logic."""

    def greeting(self, request: BrainRequest) -> BrainResponse:
        """Compose the deterministic greeting response."""
        return BrainResponse(
            message="Hello! I am Hypatia.",
            request_id=request.request_id,
            intent="greeting",
            memory_count=0,
        )

    def message(self, request: BrainRequest) -> BrainResponse:
        """Compose the deterministic generic message response."""
        return BrainResponse(
            message=f"I received your message: {request.message}",
            request_id=request.request_id,
            intent="message",
            memory_count=0,
        )

    def search_success(
        self,
        request: BrainRequest,
        results: list[Chunk],
    ) -> BrainResponse:
        """Compose a successful knowledge search response."""
        return BrainResponse(
            message=f"I found {len(results)} matching knowledge chunks.",
            request_id=request.request_id,
            intent="search",
            memory_count=0,
            knowledge_results=results,
        )

    def search_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose an unsuccessful knowledge search response."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="search",
            memory_count=0,
            success=False,
        )

    def plan_success(
        self,
        request: BrainRequest,
        plan: Plan,
    ) -> BrainResponse:
        """Compose a successful ordered plan response."""
        task_lines = "\n".join(f"{task.order}. {task.title}" for task in plan.tasks)
        return BrainResponse(
            message=f"Plan created for: {plan.goal.description}\n\n{task_lines}",
            request_id=request.request_id,
            intent="plan",
            memory_count=0,
        )

    def plan_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose an unsuccessful planning response."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="plan",
            memory_count=0,
            success=False,
        )

    def recall_success(
        self,
        request: BrainRequest,
        records: list[MemoryRecord],
    ) -> BrainResponse:
        """Compose a successful explicit conversation recall response."""
        if not records:
            return BrainResponse(
                message="No matching conversation records found.",
                request_id=request.request_id,
                intent="recall",
                memory_count=0,
            )

        items = "\n\n".join(
            f"{index}. {record.content}"
            for index, record in enumerate(records, start=1)
        )
        return BrainResponse(
            message=f"Matching conversation records:\n\n{items}",
            request_id=request.request_id,
            intent="recall",
            memory_count=len(records),
        )

    def recall_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose an unsuccessful explicit conversation recall response."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="recall",
            memory_count=0,
            success=False,
        )

    def recent_conversations(
        self,
        request: BrainRequest,
        records: list[MemoryRecord],
        session: SessionRecord,
    ) -> BrainResponse:
        """Compose an ordered list of recent conversation records."""
        items = "\n".join(
            f"{index}. {record.content}"
            for index, record in enumerate(records, start=1)
        )
        return BrainResponse(
            message=f"Recent conversations in {session.session_id}:\n{items}",
            request_id=request.request_id,
            intent="recent_conversations",
            memory_count=len(records),
        )

    def recent_conversations_empty(
        self,
        request: BrainRequest,
        session: SessionRecord,
    ) -> BrainResponse:
        """Compose a successful empty recent-conversations response."""
        return BrainResponse(
            message=f"No conversations found in session: {session.session_id}",
            request_id=request.request_id,
            intent="recent_conversations",
            memory_count=0,
        )

    def recent_conversations_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose an unsuccessful recent-conversations response."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="recent_conversations",
            memory_count=0,
            success=False,
        )

    def conversation_search_results(
        self,
        request: BrainRequest,
        records: list[MemoryRecord],
        session: SessionRecord,
    ) -> BrainResponse:
        """Compose an ordered presentation of conversation search results."""
        items = "\n".join(
            f"{index}. {record.content}"
            for index, record in enumerate(records, start=1)
        )
        return BrainResponse(
            message=f"Conversation matches in {session.session_id}:\n{items}",
            request_id=request.request_id,
            intent="conversation_search",
            memory_count=len(records),
        )

    def conversation_search_empty(
        self,
        request: BrainRequest,
        session: SessionRecord,
    ) -> BrainResponse:
        """Compose a successful empty conversation-search response."""
        return BrainResponse(
            message=f"No matching conversations found in session: {session.session_id}",
            request_id=request.request_id,
            intent="conversation_search",
            memory_count=0,
        )

    def conversation_search_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose an unsuccessful conversation-search response."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="conversation_search",
            memory_count=0,
            success=False,
        )

    def session_created(
        self,
        request: BrainRequest,
        session: SessionRecord,
    ) -> BrainResponse:
        """Compose a successful session creation response."""
        return BrainResponse(
            message=f"Session created: {session.session_id}",
            request_id=request.request_id,
            intent="session_create",
            memory_count=0,
        )

    def session_exists(
        self,
        request: BrainRequest,
        session: SessionRecord,
    ) -> BrainResponse:
        """Compose a successful duplicate-session response."""
        return BrainResponse(
            message=f"Session already exists: {session.session_id}",
            request_id=request.request_id,
            intent="session_create",
            memory_count=0,
        )

    def sessions_list(
        self,
        request: BrainRequest,
        sessions: list[SessionRecord],
        active_session: SessionRecord,
    ) -> BrainResponse:
        """Compose an ordered registry listing with one active-session marker."""
        session_lines = "\n".join(
            (
                f"{index}. {session.session_id} (active)"
                if session.session_id == active_session.session_id
                else f"{index}. {session.session_id}"
            )
            for index, session in enumerate(sessions, start=1)
        )
        return BrainResponse(
            message=f"Sessions:\n{session_lines}",
            request_id=request.request_id,
            intent="session_list",
            memory_count=0,
        )

    def session_activated(
        self,
        request: BrainRequest,
        session: SessionRecord,
    ) -> BrainResponse:
        """Compose a successful active-session selection response."""
        return BrainResponse(
            message=f"Active session: {session.session_id}",
            request_id=request.request_id,
            intent="session_use",
            memory_count=0,
        )

    def session_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose an unsuccessful session command response."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="session",
            memory_count=0,
            success=False,
        )
