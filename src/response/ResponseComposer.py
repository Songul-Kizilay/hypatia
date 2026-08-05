"""Central response composition contract for Hypatia."""

from __future__ import annotations

from datetime import datetime

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from knowledge.Chunk import Chunk
from memory.MemoryRecord import MemoryRecord
from planner.Plan import Plan
from session.SessionRecord import SessionRecord
from session.SessionRenamePreview import SessionRenamePreview
from session.SessionRenameResult import SessionRenameResult


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

    def session_renamed(
        self,
        request: BrainRequest,
        result: SessionRenameResult,
    ) -> BrainResponse:
        """Compose a successful session rename response."""
        return BrainResponse(
            message="\n".join(
                [
                    "Rename complete:",
                    f"Source: {result.source_session_id}",
                    f"Target: {result.target_session_id}",
                    f"Memory records updated: {result.memory_record_count}",
                    "Active session changed: "
                    f"{'yes' if result.active_session_changed else 'no'}",
                    "Status: committed",
                ]
            ),
            request_id=request.request_id,
            intent="session_rename",
            memory_count=result.memory_record_count,
        )

    def session_rename_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose an unsuccessful session rename response."""
        return BrainResponse(
            message=f"Rename failed:\nReason: {message}",
            request_id=request.request_id,
            intent="session_rename",
            memory_count=0,
            success=False,
        )

    def session_rename_preview(
        self,
        request: BrainRequest,
        preview: SessionRenamePreview,
    ) -> BrainResponse:
        """Compose a successful read-only session rename preview."""
        memory_id_lines = (
            [
                "Memory IDs:",
                *(f"- {memory_id}" for memory_id in preview.memory_record_ids),
            ]
            if preview.memory_record_ids
            else []
        )
        return BrainResponse(
            message="\n".join(
                [
                    "Rename preview:",
                    f"Source: {preview.source_session_id}",
                    f"Target: {preview.target_session_id}",
                    f"Affected memories: {preview.memory_record_count}",
                    *memory_id_lines,
                    "Changes: ready",
                ]
            ),
            request_id=request.request_id,
            intent="session_rename_preview",
            memory_count=preview.memory_record_count,
        )

    def session_rename_preview_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose an unsuccessful session rename preview response."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="session_rename_preview",
            memory_count=0,
            success=False,
        )

    def session_rename_help(self, request: BrainRequest) -> BrainResponse:
        """Compose deterministic usage guidance for session rename commands."""
        return BrainResponse(
            message=(
                "Rename session:\n"
                "rename session <source> -- <target>\n"
                "\n"
                "Preview:\n"
                "preview rename session <source> -- <target>\n"
                "\n"
                "Check target:\n"
                "check rename target <target>\n"
                "\n"
                "Example:\n"
                "rename session work -- archive"
            ),
            request_id=request.request_id,
            intent="session_rename_help",
            memory_count=0,
        )

    def session_rename_candidates(
        self,
        request: BrainRequest,
        sessions: list[SessionRecord],
        active_session_id: str,
    ) -> BrainResponse:
        """Compose a deterministic list of sessions eligible for rename."""
        if not sessions:
            message = "No renameable sessions."
        else:
            lines = ["Renameable sessions:"]
            for session in sessions:
                active_suffix = (
                    " (active)" if session.session_id == active_session_id else ""
                )
                lines.append(f"{session.session_id}{active_suffix}")
            message = "\n".join(lines)
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="session_rename_candidates",
            memory_count=0,
        )

    def session_active(
        self,
        request: BrainRequest,
        session: SessionRecord,
    ) -> BrainResponse:
        """Compose the deterministic current active-session status."""
        return BrainResponse(
            message=f"Active session: {session.session_id}",
            request_id=request.request_id,
            intent="session_active",
            memory_count=0,
        )

    def session_help(self, request: BrainRequest) -> BrainResponse:
        """Compose deterministic usage guidance for supported session commands."""
        return BrainResponse(
            message=(
                "Session commands:\n"
                "create session <session_id>\n"
                "list sessions\n"
                "use session <session_id>\n"
                "active session\n"
                "session overview\n"
                "session details <session_id>\n"
                "session recent <session_id>\n"
                "session activity <session_id>\n"
                "session search <session_id> <query>\n"
                "list renameable sessions\n"
                "check rename target <target>\n"
                "preview rename session <source> -- <target>\n"
                "rename session <source> -- <target>\n"
                "help rename session"
            ),
            request_id=request.request_id,
            intent="session_help",
            memory_count=0,
        )

    def session_rename_target_check(
        self,
        request: BrainRequest,
        target_session_id: str,
        available: bool,
    ) -> BrainResponse:
        """Compose the deterministic read-only rename-target availability status."""
        status = "available" if available else "unavailable"
        return BrainResponse(
            message=f"Session rename target {status}: {target_session_id}",
            request_id=request.request_id,
            intent="session_rename_target_check",
            memory_count=0,
        )

    def session_rename_target_check_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose a controlled rename-target availability validation failure."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="session_rename_target_check",
            memory_count=0,
            success=False,
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
            message=(
                "Session created:\n" f"ID: {session.session_id}\n" "Status: ready"
            ),
            request_id=request.request_id,
            intent="session_create",
            memory_count=0,
        )

    def session_create_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose an unsuccessful session-creation response."""
        return BrainResponse(
            message=f"Session creation failed:\nReason: {message}",
            request_id=request.request_id,
            intent="session_create",
            memory_count=0,
            success=False,
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

    def session_overview(
        self,
        request: BrainRequest,
        sessions: list[SessionRecord],
        conversation_counts: dict[str, int],
        active_session_id: str,
    ) -> BrainResponse:
        """Compose an ordered overview of registered session conversations."""
        session_lines = "\n".join(
            self._session_overview_line(
                index,
                session,
                conversation_counts.get(session.session_id, 0),
                active_session_id,
            )
            for index, session in enumerate(sessions, start=1)
        )
        memory_count = sum(
            conversation_counts.get(session.session_id, 0) for session in sessions
        )
        return BrainResponse(
            message=f"Sessions:\n{session_lines}",
            request_id=request.request_id,
            intent="session_overview",
            memory_count=memory_count,
        )

    def session_details(
        self,
        request: BrainRequest,
        session: SessionRecord,
        conversation_count: int,
        is_active: bool,
    ) -> BrainResponse:
        """Compose a read-only detail response for one registered session."""
        status = "active" if is_active else "inactive"
        conversation_label = (
            "conversation" if conversation_count == 1 else "conversations"
        )
        return BrainResponse(
            message=(
                f"Session: {session.session_id}\n"
                f"Status: {status}\n"
                f"Conversations: {conversation_count} {conversation_label}\n"
                f"Created: {session.created_at.isoformat()}"
            ),
            request_id=request.request_id,
            intent="session_details",
            memory_count=conversation_count,
        )

    def session_details_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose an unsuccessful session-details response."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="session_details",
            memory_count=0,
            success=False,
        )

    def session_activity(
        self,
        request: BrainRequest,
        session: SessionRecord,
        conversation_count: int,
        first_activity: datetime | None,
        last_activity: datetime | None,
    ) -> BrainResponse:
        """Compose a read-only conversation activity summary for one session."""
        first_value = first_activity.isoformat() if first_activity else "none"
        last_value = last_activity.isoformat() if last_activity else "none"
        return BrainResponse(
            message=(
                f"Session: {session.session_id}\n"
                f"Conversations: {conversation_count}\n"
                f"First activity: {first_value}\n"
                f"Last activity: {last_value}"
            ),
            request_id=request.request_id,
            intent="session_activity",
            memory_count=conversation_count,
        )

    def session_activity_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose an unsuccessful session-activity response."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="session_activity",
            memory_count=0,
            success=False,
        )

    def session_recent(
        self,
        request: BrainRequest,
        records: list[MemoryRecord],
        session: SessionRecord,
    ) -> BrainResponse:
        """Compose a recent-conversations response for a command-selected session."""
        items = "\n".join(
            f"{index}. {record.content}"
            for index, record in enumerate(records, start=1)
        )
        return BrainResponse(
            message=f"Recent conversations in {session.session_id}:\n{items}",
            request_id=request.request_id,
            intent="session_recent",
            memory_count=len(records),
        )

    def session_recent_empty(
        self,
        request: BrainRequest,
        session: SessionRecord,
    ) -> BrainResponse:
        """Compose a successful empty session-recent response."""
        return BrainResponse(
            message=f"No conversations found in session: {session.session_id}",
            request_id=request.request_id,
            intent="session_recent",
            memory_count=0,
        )

    def session_recent_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose an unsuccessful session-recent response."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="session_recent",
            memory_count=0,
            success=False,
        )

    def session_search_results(
        self,
        request: BrainRequest,
        session: SessionRecord,
        query: str,
        records: list[MemoryRecord],
    ) -> BrainResponse:
        """Compose a search response for a command-selected session."""
        items = "\n".join(
            f"{index}. {record.content}"
            for index, record in enumerate(records, start=1)
        )
        return BrainResponse(
            message=(
                f'Conversation matches in {session.session_id} for "{query}":\n{items}'
            ),
            request_id=request.request_id,
            intent="session_search",
            memory_count=len(records),
        )

    def session_search_empty(
        self,
        request: BrainRequest,
        session: SessionRecord,
        query: str,
    ) -> BrainResponse:
        """Compose a successful empty command-selected session search response."""
        return BrainResponse(
            message=(
                "No matching conversations found in session "
                f"{session.session_id} for: {query}"
            ),
            request_id=request.request_id,
            intent="session_search",
            memory_count=0,
        )

    def session_search_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose an unsuccessful command-selected session search response."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="session_search",
            memory_count=0,
            success=False,
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

    @staticmethod
    def _session_overview_line(
        index: int,
        session: SessionRecord,
        count: int,
        active_session_id: str,
    ) -> str:
        """Format one session overview line without changing registry order."""
        conversation_label = "conversation" if count == 1 else "conversations"
        active_marker = " [active]" if session.session_id == active_session_id else ""
        return (
            f"{index}. {session.session_id} — {count} "
            f"{conversation_label}{active_marker}"
        )
