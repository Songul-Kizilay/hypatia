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

    def snapshot(self) -> SessionRegistrySnapshot:
        """Return the current registry and active-session state without side effects."""
        with self._lock:
            return SessionRegistrySnapshot(
                active_session_id=self._active_session_id,
                sessions=self._sessions,
            )

    def persist_snapshot(self, snapshot: SessionRegistrySnapshot) -> None:
        """Persist a complete registry snapshot without changing RAM or events."""
        validated_snapshot = self._validate_snapshot(snapshot)
        with self._lock:
            self._persist(validated_snapshot)

    def commit_snapshot(self, snapshot: SessionRegistrySnapshot) -> None:
        """Replace RAM registry state without persistence or events."""
        validated_snapshot = self._validate_snapshot(snapshot)
        with self._lock:
            self._commit(validated_snapshot)

    def apply_snapshot_if_current(
        self,
        expected_snapshot: SessionRegistrySnapshot,
        candidate_snapshot: SessionRegistrySnapshot,
    ) -> None:
        """Persist and commit a candidate only while the expected registry is current.

        The comparison and state transition share one registry lock.
        """
        expected_snapshot = self._validate_snapshot(expected_snapshot)
        candidate_snapshot = self._validate_snapshot(candidate_snapshot)

        with self._lock:
            current_snapshot = SessionRegistrySnapshot(
                active_session_id=self._active_session_id,
                sessions=self._sessions,
            )
            if current_snapshot != expected_snapshot:
                raise SessionError("Session snapshot changed.")
            self._persist(candidate_snapshot)
            self._commit(candidate_snapshot)

    def emit_deleted(self, session: SessionRecord) -> None:
        """Publish a completed session deletion without changing registry state."""
        self._emit("session.deleted", session)

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

    @classmethod
    def _validate_snapshot(cls, snapshot: object) -> SessionRegistrySnapshot:
        if not isinstance(snapshot, SessionRegistrySnapshot):
            raise SessionError("Session snapshot must be a SessionRegistrySnapshot.")
        if not snapshot.sessions:
            raise SessionError("Session snapshot must contain at least one session.")
        if not all(isinstance(session, SessionRecord) for session in snapshot.sessions):
            raise SessionError("Session snapshot contains an invalid session record.")

        session_ids = tuple(session.session_id for session in snapshot.sessions)
        if not all(
            cls._is_valid_snapshot_session_id(session_id) for session_id in session_ids
        ):
            raise SessionError("Session snapshot contains an invalid session ID.")
        if len(set(session_ids)) != len(session_ids):
            raise SessionError("Session snapshot contains duplicate session IDs.")
        if cls._DEFAULT_SESSION_ID not in session_ids:
            raise SessionError("Session snapshot must contain the default session.")
        if not cls._is_valid_snapshot_session_id(snapshot.active_session_id):
            raise SessionError("Session snapshot has an invalid active session ID.")
        if snapshot.active_session_id not in session_ids:
            raise SessionError("Active session ID must exist in the session registry.")
        if not all(
            cls._is_timezone_aware(session.created_at) for session in snapshot.sessions
        ):
            raise SessionError(
                "Session record created_at must include timezone information."
            )
        return snapshot

    @staticmethod
    def _is_valid_snapshot_session_id(value: object) -> bool:
        return isinstance(value, str) and bool(value) and value == value.strip()

    @staticmethod
    def _is_timezone_aware(value: object) -> bool:
        return (
            isinstance(value, datetime)
            and value.tzinfo is not None
            and value.utcoffset() is not None
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
