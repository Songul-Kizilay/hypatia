"""Command-level delegation for active-session selection."""

from __future__ import annotations

from session.SessionManager import SessionManager
from session.SessionRecord import SessionRecord


class SessionUseService:
    """Delegate explicit session-use commands to the registry transaction owner."""

    def __init__(self, session_manager: SessionManager) -> None:
        self._session_manager = session_manager

    def use(self, session_id: str) -> SessionRecord:
        """Activate an existing session through the manager-owned transaction."""
        return self._session_manager.set_active(session_id)
