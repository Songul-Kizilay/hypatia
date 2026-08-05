"""Pure planning for a future session rename operation."""

from __future__ import annotations

from collections.abc import Sequence

from core.Exceptions import SessionError
from memory.MemoryRecord import MemoryRecord
from session.SessionRenamePlan import SessionRenamePlan


class SessionRenamePlanner:
    """Calculate a rename without mutating runtime state or persistence."""

    _DEFAULT_SESSION_ID = "default"

    def create_plan(
        self,
        *,
        registered_session_ids: Sequence[str],
        active_session_id: str,
        memory_records: Sequence[MemoryRecord],
        source_session_id: str,
        target_session_id: str,
    ) -> SessionRenamePlan:
        """Return the deterministic changes required to rename a session."""
        source = self._require_string(source_session_id, "source").strip()
        target = self._require_string(target_session_id, "target").strip()

        if not source:
            raise SessionError("Session source ID cannot be empty.")
        if not target:
            raise SessionError("Session target ID cannot be empty.")

        if source not in registered_session_ids:
            raise SessionError(f"Unknown session: {source}")
        if source == self._DEFAULT_SESSION_ID:
            raise SessionError("Default session cannot be renamed.")
        if source == target:
            raise SessionError("Session source and target must be different.")
        if target in registered_session_ids:
            raise SessionError(f"Session already exists: {target}")

        return SessionRenamePlan(
            source_session_id=source,
            target_session_id=target,
            updated_session_ids=tuple(
                target if session_id == source else session_id
                for session_id in registered_session_ids
            ),
            updated_active_session_id=(
                target if active_session_id == source else active_session_id
            ),
            memory_record_ids_to_update=tuple(
                record.memory_id
                for record in memory_records
                if self._has_exact_source_session(record, source)
            ),
        )

    @staticmethod
    def _require_string(value: object, role: str) -> str:
        if not isinstance(value, str):
            raise SessionError(f"Session {role} ID must be a string.")
        return value

    @staticmethod
    def _has_exact_source_session(record: MemoryRecord, source_session_id: str) -> bool:
        record_session_id = record.metadata.get("session_id")
        return (
            isinstance(record_session_id, str)
            and record_session_id == source_session_id
        )
