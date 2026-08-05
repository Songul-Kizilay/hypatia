"""Read-only planning for a possible session deletion."""

from __future__ import annotations

from core.Exceptions import SessionError
from memory.MemoryManager import MemoryManager
from memory.SessionMemoryPolicy import SessionMemoryPolicy
from session.SessionManager import SessionManager


class SessionDeletePreviewService:
    """Validate a deletion target and expose its affected conversation records."""

    _DEFAULT_SESSION_ID = "default"

    def __init__(
        self,
        session_manager: SessionManager,
        memory_manager: MemoryManager,
    ) -> None:
        self._session_manager = session_manager
        self._memory_manager = memory_manager

    def preview(self, session_id: str) -> tuple[str, tuple[str, ...]]:
        """Return the normalized session ID and ordered affected memory IDs."""
        if not self._session_manager.exists(session_id):
            raise SessionError(f"Unknown session: {session_id.strip()}")
        normalized_session_id = session_id.strip()
        if normalized_session_id == self._DEFAULT_SESSION_ID:
            raise SessionError("Default session cannot be deleted.")
        if normalized_session_id == self._session_manager.get_active().session_id:
            raise SessionError("Active session cannot be deleted.")
        memory_ids = tuple(
            record.memory_id
            for record in self._memory_manager.snapshot()
            if SessionMemoryPolicy.matches(record, normalized_session_id)
        )
        return normalized_session_id, memory_ids
