"""In-process orchestration for a transactional session rename."""

from __future__ import annotations

from threading import RLock

from core.Exceptions import SessionRenameRollbackError
from eventbus.EventBus import EventBus
from memory.MemoryManager import MemoryManager
from session.SessionManager import SessionManager
from session.SessionRenameCandidateBuilder import SessionRenameCandidateBuilder
from session.SessionRenamePlanner import SessionRenamePlanner
from session.SessionRenamePreview import SessionRenamePreview
from session.SessionRenameResult import SessionRenameResult


class SessionRenameTransactionService:
    """Coordinate the existing planner, candidate builder, and manager primitives."""

    def __init__(
        self,
        *,
        session_manager: SessionManager,
        memory_manager: MemoryManager,
        planner: SessionRenamePlanner | None = None,
        candidate_builder: SessionRenameCandidateBuilder | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._session_manager = session_manager
        self._memory_manager = memory_manager
        self._planner = planner or SessionRenamePlanner()
        self._candidate_builder = candidate_builder or SessionRenameCandidateBuilder()
        self._event_bus = event_bus
        self._lock = RLock()

    def rename(
        self,
        source_session_id: str,
        target_session_id: str,
    ) -> SessionRenameResult:
        """Rename a session with rollback only for failed session persistence."""
        with self._lock:
            session_backup = self._session_manager.snapshot()
            memory_backup = self._memory_manager.snapshot()
            plan = self._planner.create_plan(
                registered_session_ids=tuple(
                    session.session_id for session in session_backup.sessions
                ),
                active_session_id=session_backup.active_session_id,
                memory_records=memory_backup,
                source_session_id=source_session_id,
                target_session_id=target_session_id,
            )
            candidate = self._candidate_builder.build(
                plan=plan,
                session_snapshot=session_backup,
                memory_records=memory_backup,
            )

            self._memory_manager.persist_snapshot(candidate.memory_records)
            try:
                self._session_manager.persist_snapshot(candidate.session_snapshot)
            except Exception as session_error:
                try:
                    self._memory_manager.persist_snapshot(memory_backup)
                except Exception as rollback_error:
                    raise SessionRenameRollbackError(
                        session_error,
                        rollback_error,
                    ) from rollback_error
                raise

            self._session_manager.commit_snapshot(candidate.session_snapshot)
            self._memory_manager.commit_snapshot(candidate.memory_records)
            result = SessionRenameResult(
                source_session_id=plan.source_session_id,
                target_session_id=plan.target_session_id,
                memory_record_count=len(plan.memory_record_ids_to_update),
                active_session_changed=(
                    session_backup.active_session_id
                    != candidate.session_snapshot.active_session_id
                ),
            )
            self._emit_renamed(result)
            return result

    def preview(
        self,
        source_session_id: str,
        target_session_id: str,
    ) -> SessionRenamePreview:
        """Return a read-only summary of an otherwise valid rename."""
        with self._lock:
            session_snapshot = self._session_manager.snapshot()
            memory_snapshot = self._memory_manager.snapshot()
            plan = self._planner.create_plan(
                registered_session_ids=tuple(
                    session.session_id for session in session_snapshot.sessions
                ),
                active_session_id=session_snapshot.active_session_id,
                memory_records=memory_snapshot,
                source_session_id=source_session_id,
                target_session_id=target_session_id,
            )
            return SessionRenamePreview(
                source_session_id=plan.source_session_id,
                target_session_id=plan.target_session_id,
                memory_record_count=len(plan.memory_record_ids_to_update),
                active_session_changed=(
                    session_snapshot.active_session_id != plan.updated_active_session_id
                ),
            )

    def _emit_renamed(self, result: SessionRenameResult) -> None:
        if self._event_bus is None:
            return
        self._event_bus.emit(
            "session.renamed",
            {
                "source_session_id": result.source_session_id,
                "target_session_id": result.target_session_id,
                "memory_record_count": result.memory_record_count,
                "active_session_changed": result.active_session_changed,
            },
            source="session_rename_transaction_service",
        )
