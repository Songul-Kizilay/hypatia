"""Read-only planning for a possible session deletion."""

from __future__ import annotations

from core.Exceptions import SessionError
from memory.MemoryManager import MemoryManager
from memory.SessionMemoryPolicy import SessionMemoryPolicy
from session.SessionDeletePolicy import SessionDeletePolicy, SessionDeleteStatus
from session.SessionManager import SessionManager


class SessionDeletePreviewService:
    """Validate a deletion target and expose its affected conversation records."""

    def __init__(
        self,
        session_manager: SessionManager,
        memory_manager: MemoryManager,
    ) -> None:
        self._session_manager = session_manager
        self._memory_manager = memory_manager

    def preview(
        self,
        session_id: str,
    ) -> tuple[str, tuple[str, ...], SessionDeleteStatus, str]:
        """Return the read-only deletion preview and its policy decision."""
        if not self._session_manager.exists(session_id):
            raise SessionError(f"Unknown session: {session_id.strip()}")
        normalized_session_id = session_id.strip()
        memory_ids = tuple(
            record.memory_id
            for record in self._memory_manager.snapshot()
            if SessionMemoryPolicy.matches(record, normalized_session_id)
        )
        decision = SessionDeletePolicy.evaluate(
            normalized_session_id,
            self._session_manager.get_active().session_id,
            memory_ids,
        )
        return normalized_session_id, memory_ids, decision.status, decision.reason
