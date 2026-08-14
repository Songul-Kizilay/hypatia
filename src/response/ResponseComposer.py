"""Central response composition contract for Hypatia."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from knowledge.Chunk import Chunk
from knowledge.KnowledgeCitation import KnowledgeCitation
from knowledge.KnowledgeGraph import KnowledgeGraphView
from memory.MemoryRecord import MemoryRecord
from planner.Plan import Plan
from session.SessionDeleteExecutionResult import SessionDeleteExecutionResult
from session.SessionDeletePolicy import SessionDeleteStatus
from session.SessionRecord import SessionRecord
from session.SessionRenamePreview import SessionRenamePreview
from session.SessionRenameResult import SessionRenameResult


class ResponseComposer:
    """Creates user-facing response models without orchestration logic."""

    _KNOWLEDGE_CONTEXT_MAX_CHARS_PER_RESULT = 600

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

    def session_delete_preview(
        self,
        request: BrainRequest,
        session_id: str,
        memory_ids: tuple[str, ...],
        decision_status: SessionDeleteStatus,
        decision_reason: str,
    ) -> BrainResponse:
        """Compose a deterministic, read-only delete preview."""
        lines = [
            "Delete preview:",
            f"Session: {session_id}",
        ]
        lines.append(f"Decision: {decision_status.value}")
        if decision_status is SessionDeleteStatus.ALLOW:
            lines.extend(
                [
                    f"Affected memories: {len(memory_ids)}",
                    "Changes: ready",
                ]
            )
        else:
            lines.append(f"Reason: {decision_reason}")
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="session_delete_preview",
            memory_count=len(memory_ids),
        )

    def session_delete_preview_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose a failed, side-effect-free delete preview."""
        return BrainResponse(
            message=f"Delete preview failed:\nReason: {message}",
            request_id=request.request_id,
            intent="session_delete_preview",
            memory_count=0,
            success=False,
        )

    def session_deleted(
        self,
        request: BrainRequest,
        result: SessionDeleteExecutionResult,
    ) -> BrainResponse:
        """Compose a successful response for a committed session deletion."""
        return BrainResponse(
            message="\n".join(
                [
                    "Session deleted:",
                    f"ID: {result.session_id}",
                    f"Memory records removed: {result.memory_records_removed}",
                    "Status: committed",
                ]
            ),
            request_id=request.request_id,
            intent="session_delete",
            memory_count=result.memory_records_removed,
        )

    def session_delete_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose a failed pre-commit session deletion response."""
        return BrainResponse(
            message=f"Delete failed:\nReason: {message}",
            request_id=request.request_id,
            intent="session_delete",
            memory_count=0,
            success=False,
        )

    def session_delete_event_failure(
        self,
        request: BrainRequest,
        result: SessionDeleteExecutionResult,
    ) -> BrainResponse:
        """Compose a committed deletion with an event-publication warning."""
        return BrainResponse(
            message="\n".join(
                [
                    "Session deleted:",
                    f"ID: {result.session_id}",
                    f"Memory records removed: {result.memory_records_removed}",
                    "Status: committed",
                    "Warning: lifecycle event publication failed",
                ]
            ),
            request_id=request.request_id,
            intent="session_delete",
            memory_count=result.memory_records_removed,
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
            knowledge_citations=[
                KnowledgeCitation.from_chunk(result) for result in results
            ],
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

    def knowledge_context_success(
        self,
        request: BrainRequest,
        results: list[Chunk],
    ) -> BrainResponse:
        """Compose an explicit, citation-visible bounded local context response."""
        citations = [KnowledgeCitation.from_chunk(result) for result in results]
        if not results:
            message = "Knowledge context: no matching local knowledge found."
        else:
            items = "\n\n".join(
                self._knowledge_context_item(index, result, citation)
                for index, (result, citation) in enumerate(
                    zip(results, citations, strict=True),
                    start=1,
                )
            )
            message = f"Knowledge context:\n\n{items}"
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="knowledge_context",
            memory_count=0,
            knowledge_results=results,
            knowledge_citations=citations,
        )

    def knowledge_context_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose a failed explicit local knowledge-context response."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="knowledge_context",
            memory_count=0,
            success=False,
        )

    def knowledge_graph_success(
        self,
        request: BrainRequest,
        results: list[Chunk],
        graph_view: KnowledgeGraphView,
    ) -> BrainResponse:
        """Compose an explicit, citation-visible local structural graph view."""
        citations = [KnowledgeCitation.from_chunk(result) for result in results]
        nodes_by_id = {node.node_id: node for node in graph_view.nodes}
        if not results:
            message = "Knowledge graph: no matching local knowledge found."
        else:
            edges = "\n".join(
                "- "
                f"{nodes_by_id[edge.source_node_id].label} "
                f"--{edge.relation.value}--> "
                f"{nodes_by_id[edge.target_node_id].label}"
                for edge in graph_view.edges
            )
            message = f"Knowledge graph:\n{edges}"
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="knowledge_graph",
            memory_count=0,
            knowledge_results=results,
            knowledge_citations=citations,
        )

    def knowledge_graph_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose a failed explicit local structural-graph request."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="knowledge_graph",
            memory_count=0,
            success=False,
        )

    def ask_knowledge_success(
        self,
        request: BrainRequest,
        answer: str,
        results: list[Chunk],
        citations: list[KnowledgeCitation],
    ) -> BrainResponse:
        """Compose an explicit local RAG answer with its visible source records."""
        return BrainResponse(
            message=answer,
            request_id=request.request_id,
            intent="ask_knowledge",
            memory_count=0,
            knowledge_results=results,
            knowledge_citations=citations,
        )

    def ask_knowledge_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose an unsuccessful explicit local RAG answer request."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="ask_knowledge",
            memory_count=0,
            success=False,
        )

    def _knowledge_context_item(
        self,
        index: int,
        result: Chunk,
        citation: KnowledgeCitation,
    ) -> str:
        source = citation.source or "local source unavailable"
        content = result.content
        if len(content) > self._KNOWLEDGE_CONTEXT_MAX_CHARS_PER_RESULT:
            content = (
                content[: self._KNOWLEDGE_CONTEXT_MAX_CHARS_PER_RESULT].rstrip() + "..."
            )
        return (
            f"{index}. {citation.document_title} | {source} | "
            f"paragraph {citation.chunk_index + 1}\n{content}"
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

    def semantic_recall_success(
        self,
        request: BrainRequest,
        records: Sequence[tuple[MemoryRecord, float | None]],
        *,
        retrieval: str,
    ) -> BrainResponse:
        """Compose explicit semantic recall with a visible retrieval mode."""
        if not records:
            return BrainResponse(
                message=(
                    f"Semantic recall ({retrieval}): "
                    "no matching conversation records found."
                ),
                request_id=request.request_id,
                intent="semantic_recall",
                memory_count=0,
            )

        items = "\n\n".join(
            self._semantic_recall_item(
                index,
                record,
                score,
                score_label="rank score" if retrieval == "hybrid" else "similarity",
            )
            for index, (record, score) in enumerate(records, start=1)
        )
        return BrainResponse(
            message=f"Semantic recall ({retrieval}):\n\n{items}",
            request_id=request.request_id,
            intent="semantic_recall",
            memory_count=len(records),
        )

    def semantic_recall_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose an unsuccessful semantic recall response."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="semantic_recall",
            memory_count=0,
            success=False,
        )

    @staticmethod
    def _semantic_recall_item(
        index: int,
        record: MemoryRecord,
        score: float | None,
        *,
        score_label: str,
    ) -> str:
        if score is None:
            return f"{index}. {record.content}"
        return f"{index}. [{score_label}: {score:.3f}] {record.content}"

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

    def session_overview_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose an unsuccessful session-overview response."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="session_overview",
            memory_count=0,
            success=False,
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
