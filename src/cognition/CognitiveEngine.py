"""Cognitive orchestration entry point."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from brain.BrainContext import BrainContext
from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from brain.BrainRouter import BrainRouter
from core.Exceptions import (
    KnowledgeError,
    MemoryError,
    PlannerError,
    SessionDeleteEventError,
    SessionError,
)
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from llm.LLMProvider import LLMProvider
from memory.MemoryManager import MemoryManager
from memory.MemoryRecord import MemoryRecord
from memory.SessionMemoryPolicy import SessionMemoryPolicy
from response.ResponseComposer import ResponseComposer
from session.SessionCreateService import SessionCreateService
from session.SessionDeletePreviewService import SessionDeletePreviewService
from session.SessionDeleteService import SessionDeleteService
from session.SessionManager import SessionManager
from session.SessionRecord import SessionRecord
from session.SessionRenameTransactionService import SessionRenameTransactionService
from session.SessionUseService import SessionUseService

if TYPE_CHECKING:
    from planner.Planner import Planner


class CognitiveEngine:
    """Coordinates the first knowledge-backed cognitive request flow."""

    def __init__(
        self,
        knowledge_engine: KnowledgeEngine,
        memory_manager: MemoryManager,
        planner: Planner,
        event_bus: EventBus,
        response_composer: ResponseComposer,
        session_manager: SessionManager,
        session_rename_service: SessionRenameTransactionService,
        llm_provider: LLMProvider | None = None,
    ) -> None:
        self._knowledge_engine = knowledge_engine
        self._memory_manager = memory_manager
        self._planner = planner
        self._event_bus = event_bus
        self._response_composer = response_composer
        self._session_manager = session_manager
        self._session_create_service = SessionCreateService(session_manager)
        self._session_delete_preview_service = SessionDeletePreviewService(
            session_manager,
            memory_manager,
        )
        self._session_delete_service = SessionDeleteService(
            session_manager,
            memory_manager,
        )
        self._session_use_service = SessionUseService(session_manager)
        self._session_rename_service = session_rename_service
        self._llm_provider = llm_provider
        self._router = BrainRouter()

    def process(self, request: BrainRequest) -> BrainResponse:
        """Process a request using the currently supported cognitive intent."""
        intent = self._router.detect_intent(request)
        if intent == "conversation_search":
            return self._process_conversation_search(request)
        if intent == "session_search":
            return self._process_session_search(request)
        if intent == "session_activity":
            return self._process_session_activity(request)
        if intent == "session_active":
            return self._response_composer.session_active(
                request,
                self._session_manager.get_active(),
            )
        if intent == "session_help":
            return self._response_composer.session_help(request)
        if intent == "session_rename_help":
            return self._response_composer.session_rename_help(request)
        if intent == "session_rename_candidates":
            return self._process_session_rename_candidates(request)
        if intent == "session_rename_target_check":
            return self._process_session_rename_target_check(request)
        if intent == "session_rename":
            return self._process_session_rename(request)
        if intent == "session_rename_preview":
            return self._process_session_rename_preview(request)
        if intent == "session_delete_preview":
            return self._process_session_delete_preview(request)
        if intent == "session_delete":
            return self._process_session_delete(request)

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
                    if record.metadata.get("session_id", "default") == session_id
                ]
            except SessionError as error:
                return self._response_composer.session_failure(request, str(error))
            except MemoryError as error:
                return self._response_composer.recall_failure(request, str(error))
            return self._response_composer.recall_success(request, session_records[:5])

        if intent in {"session_create", "session_list", "session_use"}:
            return self._process_session_command(request, intent)
        if intent == "session_overview":
            return self._process_session_overview(request)
        if intent == "session_details":
            return self._process_session_details(request)
        if intent == "session_recent":
            return self._process_session_recent(request)
        if intent == "recent_conversations":
            return self._process_recent_conversations(request)

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
        except SessionError as error:
            return self._response_composer.session_failure(request, str(error))

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

        if context.intent == "message" and self._llm_provider is not None:
            response = BrainResponse(
                message=self._llm_provider.generate(request.message),
                request_id=request.request_id,
                intent="message",
                memory_count=0,
            )
        else:
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

        if value is None or (isinstance(value, str) and not value.strip()):
            return self._session_manager.get_active().session_id

        if not isinstance(value, str):
            raise SessionError("session_id must be a string.")

        normalized = value.strip()
        if not self._session_manager.exists(normalized):
            raise SessionError(f"Unknown session: {normalized}")
        return normalized

    def _process_session_command(
        self,
        request: BrainRequest,
        intent: str,
    ) -> BrainResponse:
        try:
            if intent == "session_create":
                result = self._session_create_service.create(
                    self._session_command_id(request, "create session")
                )
                if result.created:
                    return self._response_composer.session_created(
                        request,
                        result.session,
                    )
                return self._response_composer.session_exists(request, result.session)
            if intent == "session_list":
                return self._response_composer.sessions_list(
                    request,
                    self._session_manager.list(),
                    self._session_manager.get_active(),
                )
            session = self._session_use_service.use(
                self._session_command_id(request, "use session")
            )
            return self._response_composer.session_activated(request, session)
        except SessionError as error:
            if intent == "session_create":
                return self._response_composer.session_create_failure(
                    request, str(error)
                )
            return self._response_composer.session_failure(request, str(error))

    def _process_session_rename(self, request: BrainRequest) -> BrainResponse:
        """Execute an explicit session rename without conversation side effects."""
        try:
            source_session_id, target_session_id = self._session_rename_parts(request)
            result = self._session_rename_service.rename(
                source_session_id,
                target_session_id,
            )
        except (SessionError, MemoryError, ValueError, RuntimeError) as error:
            return self._response_composer.session_rename_failure(request, str(error))
        return self._response_composer.session_renamed(request, result)

    def _process_session_rename_preview(self, request: BrainRequest) -> BrainResponse:
        """Preview an explicit session rename without any side effects."""
        try:
            source_session_id, target_session_id = self._session_rename_parts(
                request,
                command_prefix="preview rename session",
            )
            preview = self._session_rename_service.preview(
                source_session_id,
                target_session_id,
            )
        except (SessionError, MemoryError, ValueError, RuntimeError) as error:
            return self._response_composer.session_rename_preview_failure(
                request,
                str(error),
            )
        return self._response_composer.session_rename_preview(request, preview)

    def _process_session_delete_preview(self, request: BrainRequest) -> BrainResponse:
        """Preview a deletion without changing either store or emitting events."""
        try:
            (
                session_id,
                memory_ids,
                decision_status,
                decision_reason,
            ) = self._session_delete_preview_service.preview(
                self._session_command_id(request, "preview delete session")
            )
        except (SessionError, MemoryError, ValueError, RuntimeError) as error:
            return self._response_composer.session_delete_preview_failure(
                request,
                str(error),
            )
        return self._response_composer.session_delete_preview(
            request,
            session_id,
            memory_ids,
            decision_status,
            decision_reason,
        )

    def _process_session_delete(self, request: BrainRequest) -> BrainResponse:
        """Execute a delete only when the service confirms its commit."""
        try:
            result = self._session_delete_service.delete(
                self._session_command_id(request, "delete session")
            )
        except SessionDeleteEventError as error:
            if error.result.committed is not True:
                raise ValueError(
                    "Session delete event failure result must be committed."
                ) from error
            return self._response_composer.session_delete_event_failure(
                request,
                error.result,
            )
        except (SessionError, MemoryError, ValueError, RuntimeError) as error:
            return self._response_composer.session_delete_failure(
                request,
                str(error),
            )
        if result.committed is not True:
            raise ValueError("Session delete result must be committed.")
        return self._response_composer.session_deleted(request, result)

    def _process_session_rename_candidates(
        self, request: BrainRequest
    ) -> BrainResponse:
        """List source sessions that are eligible for an explicit rename."""
        sessions = [
            session
            for session in self._session_manager.list()
            if session.session_id != "default"
        ]
        active_session_id = self._session_manager.get_active().session_id
        return self._response_composer.session_rename_candidates(
            request,
            sessions,
            active_session_id,
        )

    def _process_session_rename_target_check(
        self, request: BrainRequest
    ) -> BrainResponse:
        """Check whether an explicit rename target is unused without side effects."""
        try:
            target_session_id = self._session_rename_target_id(request)
        except ValueError as error:
            return self._response_composer.session_rename_target_check_failure(
                request,
                str(error),
            )
        return self._response_composer.session_rename_target_check(
            request,
            target_session_id,
            not self._session_manager.exists(target_session_id),
        )

    def _process_session_overview(self, request: BrainRequest) -> BrainResponse:
        """Return a read-only overview of registered session conversations."""
        try:
            sessions = self._session_manager.list()
            conversation_counts = {session.session_id: 0 for session in sessions}

            for record in self._memory_manager.all():
                for session_id in conversation_counts:
                    if SessionMemoryPolicy.matches(record, session_id):
                        conversation_counts[session_id] += 1
                        break
            active_session_id = self._session_manager.get_active().session_id
        except MemoryError as error:
            return self._response_composer.session_overview_failure(request, str(error))

        return self._response_composer.session_overview(
            request,
            sessions,
            conversation_counts,
            active_session_id,
        )

    def _process_session_details(self, request: BrainRequest) -> BrainResponse:
        """Return a read-only conversation count for one command-selected session."""
        try:
            session_id = self._session_details_id(request)
            if not self._session_manager.exists(session_id):
                raise SessionError(f"Unknown session: {session_id}")
            session = self._session_record(session_id)
            conversation_count = sum(
                1
                for record in self._memory_manager.all()
                if SessionMemoryPolicy.matches(record, session_id)
            )
        except (SessionError, MemoryError, ValueError) as error:
            return self._response_composer.session_details_failure(request, str(error))
        return self._response_composer.session_details(
            request,
            session,
            conversation_count,
            self._session_manager.get_active().session_id == session_id,
        )

    def _process_session_activity(self, request: BrainRequest) -> BrainResponse:
        """Return a read-only first-and-last activity summary for one session."""
        try:
            session_id = self._session_activity_id(request)
            if not self._session_manager.exists(session_id):
                raise SessionError(f"Unknown session: {session_id}")
            session = self._session_record(session_id)
            records = [
                record
                for record in self._memory_manager.all()
                if SessionMemoryPolicy.matches(record, session_id)
            ]
            activity_times = [
                record.created_at for record in records if record.created_at is not None
            ]
            if activity_times:
                first_activity = min(activity_times)
                last_activity = max(activity_times)
            else:
                first_activity = None
                last_activity = None
        except (SessionError, MemoryError, ValueError) as error:
            return self._response_composer.session_activity_failure(request, str(error))
        return self._response_composer.session_activity(
            request,
            session,
            len(records),
            first_activity,
            last_activity,
        )

    def _process_session_recent(self, request: BrainRequest) -> BrainResponse:
        """Return five newest normal conversations for a command-selected session."""
        try:
            session_id = self._session_recent_id(request)
            if not self._session_manager.exists(session_id):
                raise SessionError(f"Unknown session: {session_id}")
            session = self._session_record(session_id)
            records = [
                record
                for record in self._memory_manager.all()
                if SessionMemoryPolicy.matches(record, session_id)
            ]
            recent_records = sorted(
                records,
                key=self._record_created_at,
                reverse=True,
            )[:5]
        except (SessionError, MemoryError, ValueError) as error:
            return self._response_composer.session_recent_failure(request, str(error))
        if not recent_records:
            return self._response_composer.session_recent_empty(request, session)
        return self._response_composer.session_recent(request, recent_records, session)

    def _process_session_search(self, request: BrainRequest) -> BrainResponse:
        """Find matching conversations for a command-selected session."""
        try:
            session_id, query = self._session_search_parts(request)
            if not self._session_manager.exists(session_id):
                raise SessionError(f"Unknown session: {session_id}")
            session = self._session_record(session_id)
            matching_records = [
                record
                for record in self._memory_manager.search(query, limit=None)
                if SessionMemoryPolicy.matches(record, session_id)
            ][:5]
        except (SessionError, MemoryError, ValueError) as error:
            return self._response_composer.session_search_failure(request, str(error))
        if not matching_records:
            return self._response_composer.session_search_empty(
                request,
                session,
                query,
            )
        return self._response_composer.session_search_results(
            request,
            session,
            query,
            matching_records,
        )

    def _process_recent_conversations(self, request: BrainRequest) -> BrainResponse:
        """Return recent normal conversation records for the resolved session."""
        try:
            session_id = self._resolve_session_id(request)
            limit = self._recent_conversation_limit(request)
            session = self._session_record(session_id)
            records = [
                record
                for record in self._memory_manager.all()
                if {"brain", "conversation"}.issubset(record.tags)
                and record.metadata.get("session_id", "default") == session_id
            ]
            recent_records = sorted(
                records,
                key=self._record_created_at,
                reverse=True,
            )[:limit]
        except (SessionError, MemoryError, ValueError) as error:
            return self._response_composer.recent_conversations_failure(
                request,
                str(error),
            )
        if not recent_records:
            return self._response_composer.recent_conversations_empty(request, session)
        return self._response_composer.recent_conversations(
            request,
            recent_records,
            session,
        )

    def _process_conversation_search(self, request: BrainRequest) -> BrainResponse:
        """Find matching normal conversation records in the resolved session."""
        try:
            query = self._conversation_search_query(request)
            session_id = self._resolve_session_id(request)
            records = self._memory_manager.search(query, limit=None)
            matching_records = [
                record
                for record in records
                if {"brain", "conversation"}.issubset(record.tags)
                and record.metadata.get("session_id", "default") == session_id
            ][:5]
            session = self._session_record(session_id)
        except (SessionError, MemoryError, ValueError) as error:
            return self._response_composer.conversation_search_failure(
                request,
                str(error),
            )
        if not matching_records:
            return self._response_composer.conversation_search_empty(request, session)
        return self._response_composer.conversation_search_results(
            request,
            matching_records,
            session,
        )

    @staticmethod
    def _conversation_search_query(request: BrainRequest) -> str:
        """Return the non-empty user-provided conversation search query."""
        query = request.message.strip()[len("search conversations") :].strip()
        if not query:
            raise ValueError("Search query must not be empty.")
        return query

    @staticmethod
    def _session_details_id(request: BrainRequest) -> str:
        """Return the non-empty, command-selected session ID without metadata."""
        session_id = request.message.strip()[len("session details") :].strip()
        if not session_id:
            raise ValueError("Session ID must not be empty.")
        return session_id

    @staticmethod
    def _session_recent_id(request: BrainRequest) -> str:
        """Return the complete non-empty session-recent command suffix."""
        session_id = request.message.strip()[len("session recent") :].strip()
        if not session_id:
            raise ValueError("Session ID must not be empty.")
        return session_id

    @staticmethod
    def _session_activity_id(request: BrainRequest) -> str:
        """Return the complete non-empty session-activity command suffix."""
        session_id = request.message.strip()[len("session activity") :].strip()
        if not session_id:
            raise ValueError("Session ID must not be empty.")
        return session_id

    @staticmethod
    def _session_search_parts(request: BrainRequest) -> tuple[str, str]:
        """Return validated session-search command fields without metadata access."""
        remainder = request.message.strip()[len("session search") :]
        session_part, separator, query_part = remainder.partition(" -- ")
        if not separator:
            if remainder.endswith(" --"):
                session_part = remainder[:-3]
                query_part = ""
            else:
                raise ValueError("Search query separator is required: --")

        session_id = session_part.strip()
        if not session_id:
            raise ValueError("Session ID must not be empty.")

        query = query_part.strip()
        if not query:
            raise ValueError("Search query must not be empty.")
        return session_id, query

    @staticmethod
    def _session_rename_parts(
        request: BrainRequest,
        *,
        command_prefix: str = "rename session",
    ) -> tuple[str, str]:
        """Return validated source and target IDs from an explicit rename command."""
        remainder = request.message.strip()[len(command_prefix) :]
        source_part, separator, target_part = remainder.partition(" -- ")
        if not separator:
            if remainder.endswith(" --"):
                source_part = remainder[:-3]
                target_part = ""
            else:
                raise ValueError("Session rename separator is required: --")

        source_session_id = source_part.strip()
        if not source_session_id:
            raise ValueError("Session source ID must not be empty.")
        target_session_id = target_part.strip()
        if not target_session_id:
            raise ValueError("Session target ID must not be empty.")
        return source_session_id, target_session_id

    @staticmethod
    def _session_rename_target_id(request: BrainRequest) -> str:
        """Return the validated target ID from an explicit availability command."""
        target_session_id = request.message.strip()[
            len("check rename target") :
        ].strip()
        if not target_session_id:
            raise ValueError("Session target ID must not be empty.")
        return target_session_id

    @staticmethod
    def _recent_conversation_limit(request: BrainRequest) -> int:
        """Return the validated optional count from a recent-conversations command."""
        remainder = request.message.strip()[len("recent conversations") :].strip()
        if not remainder:
            return 5

        try:
            limit = int(remainder)
        except ValueError as error:
            raise ValueError("Count must be an integer.") from error

        if not 1 <= limit <= 20:
            raise ValueError("Count must be between 1 and 20.")
        return limit

    def _session_record(self, session_id: str) -> SessionRecord:
        """Return the registry record for an already resolved session ID."""
        return next(
            session
            for session in self._session_manager.list()
            if session.session_id == session_id
        )

    @staticmethod
    def _record_created_at(record: MemoryRecord) -> datetime:
        """Return a deterministic ordering timestamp for a memory record."""
        return record.created_at or datetime.min.replace(tzinfo=UTC)

    @staticmethod
    def _session_command_id(request: BrainRequest, command: str) -> str:
        return request.message.strip()[len(command) :].strip()

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
