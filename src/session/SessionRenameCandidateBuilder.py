"""Pure construction of session rename candidates."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from core.Exceptions import SessionError
from memory.MemoryRecord import MemoryRecord
from session.SessionRecord import SessionRecord
from session.SessionRegistrySnapshot import SessionRegistrySnapshot
from session.SessionRenameCandidate import SessionRenameCandidate
from session.SessionRenamePlan import SessionRenamePlan


class SessionRenameCandidateBuilder:
    """Build a validated rename candidate without touching runtime state."""

    def build(
        self,
        *,
        plan: SessionRenamePlan,
        session_snapshot: SessionRegistrySnapshot,
        memory_records: Sequence[MemoryRecord],
    ) -> SessionRenameCandidate:
        """Return a candidate whose contents agree exactly with *plan*."""
        source_sessions = tuple(
            session
            for session in session_snapshot.sessions
            if session.session_id == plan.source_session_id
        )
        if len(source_sessions) > 1:
            raise SessionError(
                "Session rename snapshot contains duplicate source session: "
                f"{plan.source_session_id}"
            )
        if not source_sessions:
            raise SessionError(
                "Session rename plan source is missing from the session snapshot: "
                f"{plan.source_session_id}"
            )

        updated_sessions = tuple(
            (
                SessionRecord(plan.target_session_id, session.created_at)
                if session.session_id == plan.source_session_id
                else session
            )
            for session in session_snapshot.sessions
        )
        if (
            tuple(session.session_id for session in updated_sessions)
            != plan.updated_session_ids
        ):
            raise SessionError(
                "Session rename plan session order does not match the session snapshot."
            )

        expected_active_session_id = (
            plan.target_session_id
            if session_snapshot.active_session_id == plan.source_session_id
            else session_snapshot.active_session_id
        )
        updated_session_ids = {session.session_id for session in updated_sessions}
        if (
            plan.updated_active_session_id != expected_active_session_id
            or plan.updated_active_session_id not in updated_session_ids
        ):
            raise SessionError(
                "Session rename plan active session does not match "
                "the session snapshot."
            )

        self._validate_memory_ids(plan, memory_records)
        records_to_update = set(plan.memory_record_ids_to_update)
        updated_records = tuple(
            (
                self._renamed_record(record, plan.target_session_id)
                if record.memory_id in records_to_update
                else record
            )
            for record in memory_records
        )

        return SessionRenameCandidate(
            plan=plan,
            session_snapshot=SessionRegistrySnapshot(
                active_session_id=plan.updated_active_session_id,
                sessions=updated_sessions,
            ),
            memory_records=updated_records,
        )

    @staticmethod
    def _validate_memory_ids(
        plan: SessionRenamePlan,
        memory_records: Sequence[MemoryRecord],
    ) -> None:
        planned_ids: set[str] = set()
        for memory_id in plan.memory_record_ids_to_update:
            if memory_id in planned_ids:
                raise SessionError(
                    "Session rename plan contains duplicate memory record ID: "
                    f"{memory_id}"
                )
            planned_ids.add(memory_id)

        snapshot_ids: set[str] = set()
        for record in memory_records:
            if record.memory_id in snapshot_ids:
                raise SessionError(
                    "Session rename snapshot contains duplicate memory record ID: "
                    f"{record.memory_id}"
                )
            snapshot_ids.add(record.memory_id)

        for memory_id in plan.memory_record_ids_to_update:
            if memory_id not in snapshot_ids:
                raise SessionError(
                    "Session rename plan references unknown memory record: "
                    f"{memory_id}"
                )

    @staticmethod
    def _renamed_record(record: MemoryRecord, target_session_id: str) -> MemoryRecord:
        metadata = dict(record.metadata)
        metadata["session_id"] = target_session_id
        return replace(record, metadata=metadata)
