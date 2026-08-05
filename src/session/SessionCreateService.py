"""Command-level validation for transactional session creation."""

from __future__ import annotations

from core.Exceptions import SessionError
from session.SessionCreateResult import SessionCreateResult
from session.SessionManager import SessionManager


class SessionCreateService:
    """Validate explicit create commands before delegating to the registry owner."""

    _DEFAULT_SESSION_ID = "default"

    def __init__(self, session_manager: SessionManager) -> None:
        self._session_manager = session_manager

    def create(self, session_id: str) -> SessionCreateResult:
        """Create one new session through the manager-owned transaction boundary."""
        self._session_manager.exists(session_id)
        normalized_session_id = session_id.strip()

        if normalized_session_id == self._DEFAULT_SESSION_ID:
            raise SessionError("reserved default session id.")
        return self._session_manager.create(normalized_session_id)
