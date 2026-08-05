"""Transactional owner of the Hypatia session registry."""

from __future__ import annotations

from datetime import UTC, datetime
from threading import RLock

from core.Exceptions import SessionError
from eventbus.EventBus import EventBus
from session.SessionCreateResult import SessionCreateResult
from session.SessionRecord import SessionRecord
from session.SessionRegistrySnapshot import SessionRegistrySnapshot
from session.SessionStore import SessionStore


class SessionManager:
    """Owns registered sessions, active-session state, and registry persistence."""

    _DEFAULT_SESSION_ID = "default"

    def __init__(
        self,
        event_bus: EventBus | None = None,
        store: SessionStore | None = None,
    ) -> None:
        default_session = self._new_session(self._DEFAULT_SESSION_ID)
        self._sessions: tuple[SessionRecord, ...] = (default_session,)
        self._active_session_id = self._DEFAULT_SESSION_ID
        self._event_bus = event_bus
        self._store = store
        self._lock = RLock()

    def create(self, session_id: str) -> SessionCreateResult:
        """Create a session or report the existing matching session."""
        normalized_session_id = self._normalize_session_id(session_id)

        with self._lock:
            existing = self._find(normalized_session_id)
            if existing is not None:
                return SessionCreateResult(session=existing, created=False)

            session = self._new_session(normalized_session_id)
            candidate_snapshot = SessionRegistrySnapshot(
                active_session_id=self._active_session_id,
                sessions=(*self._sessions, session),
            )
            self._persist(candidate_snapshot)
            self._commit(candidate_snapshot)

        self._emit("session.created", session)
        return SessionCreateResult(session=session, created=True)

    def list(self) -> list[SessionRecord]:
        """Return registered sessions in creation order."""
        with self._lock:
            return list(self._sessions)

    def exists(self, session_id: str) -> bool:
        """Return whether a normalized session ID is registered."""
        normalized_session_id = self._normalize_session_id(session_id)
        with self._lock:
            return self._find(normalized_session_id) is not None

    def set_active(self, session_id: str) -> SessionRecord:
        """Select an existing session as active without changing its position."""
        normalized_session_id = self._normalize_session_id(session_id)

        with self._lock:
            session = self._find(normalized_session_id)
            if session is None:
                raise SessionError(f"Unknown session: {normalized_session_id}")
            if normalized_session_id == self._active_session_id:
                return session

            candidate_snapshot = SessionRegistrySnapshot(
                active_session_id=normalized_session_id,
                sessions=self._sessions,
            )
            self._persist(candidate_snapshot)
            self._commit(candidate_snapshot)

        self._emit("session.activated", session)
        return session

    def get_active(self) -> SessionRecord:
        """Return the registered session currently selected as active."""
        with self._lock:
            session = self._find(self._active_session_id)
            if session is None:
                raise SessionError("The active session is not registered.")
            return session

    def load(self) -> None:
        """Load and atomically replace the registry from the optional store."""
        if self._store is None:
            return

        snapshot = self._store.load()
        if snapshot is None:
            snapshot = self._default_snapshot()
            self._persist(snapshot)

        with self._lock:
            self._commit(snapshot)

    def _default_snapshot(self) -> SessionRegistrySnapshot:
        return SessionRegistrySnapshot(
            active_session_id=self._DEFAULT_SESSION_ID,
            sessions=(self._new_session(self._DEFAULT_SESSION_ID),),
        )

    def _commit(self, snapshot: SessionRegistrySnapshot) -> None:
        self._sessions = tuple(snapshot.sessions)
        self._active_session_id = snapshot.active_session_id

    def _persist(self, snapshot: SessionRegistrySnapshot) -> None:
        if self._store is not None:
            self._store.save(snapshot)

    def _find(self, session_id: str) -> SessionRecord | None:
        return next(
            (session for session in self._sessions if session.session_id == session_id),
            None,
        )

    def _emit(self, name: str, session: SessionRecord) -> None:
        if self._event_bus is None:
            return
        self._event_bus.emit(
            name,
            {
                "session_id": session.session_id,
                "created_at": session.created_at.isoformat(),
            },
            source="session_manager",
        )

    @staticmethod
    def _normalize_session_id(value: object) -> str:
        if not isinstance(value, str):
            raise SessionError("session_id must be a string.")

        normalized_session_id = value.strip()
        if not normalized_session_id:
            raise SessionError("session_id must not be empty.")
        return normalized_session_id

    @staticmethod
    def _new_session(session_id: str) -> SessionRecord:
        return SessionRecord(
            session_id=session_id,
            created_at=datetime.now(UTC),
        )
