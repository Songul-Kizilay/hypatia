"""Guarded orchestration for zero-memory session deletion."""

from __future__ import annotations

from core.Exceptions import SessionDeleteEventError, SessionError
from memory.MemoryManager import MemoryManager
from memory.SessionMemoryPolicy import SessionMemoryPolicy
from session.SessionDeleteExecutionResult import SessionDeleteExecutionResult
from session.SessionDeletePlan import SessionDeletePlan
from session.SessionDeletePolicy import SessionDeletePolicy
from session.SessionDeleteTransactionService import SessionDeleteTransactionService
from session.SessionManager import SessionManager


class SessionDeleteService:
    """Compose existing policy, memory guard, and transaction primitives."""

    def __init__(
        self,
        session_manager: SessionManager,
        memory_manager: MemoryManager,
        transaction_service: SessionDeleteTransactionService | None = None,
    ) -> None:
        self._session_manager = session_manager
        self._memory_manager = memory_manager
        self._transaction_service = (
            transaction_service or SessionDeleteTransactionService()
        )

    def delete(self, session_id: str) -> SessionDeleteExecutionResult:
        """Delete one inactive non-default session that has no attached memories."""
        if not self._session_manager.exists(session_id):
            raise SessionError(f"Unknown session: {session_id.strip()}")
        normalized_session_id = session_id.strip()
        expected_memory = self._memory_manager.snapshot()
        matching_memory_ids = tuple(
            record.memory_id
            for record in expected_memory
            if SessionMemoryPolicy.matches(record, normalized_session_id)
        )
        decision = SessionDeletePolicy.evaluate(
            normalized_session_id,
            self._session_manager.get_active().session_id,
            matching_memory_ids,
        )
        plan = SessionDeletePlan.for_decision(
            normalized_session_id,
            matching_memory_ids,
            decision,
        )
        if plan is None:
            raise SessionError(decision.reason)
        context = self._transaction_service.prepare(plan)
        result, deleted_session = self._memory_manager.run_if_snapshot_current(
            expected_memory,
            lambda: self._transaction_service.commit(
                context,
                self._session_manager,
            ),
        )
        try:
            self._session_manager.emit_deleted(deleted_session)
        except Exception as event_error:
            raise SessionDeleteEventError(result, event_error) from event_error
        return result
