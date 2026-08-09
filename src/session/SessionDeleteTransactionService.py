"""Preparation boundary for a future session-delete transaction."""

from __future__ import annotations

from dataclasses import dataclass

from session.SessionDeleteExecutionResult import SessionDeleteExecutionResult
from session.SessionDeletePlan import SessionDeletePlan
from session.SessionDeletePolicy import SessionDeleteStatus
from session.SessionManager import SessionManager
from session.SessionRecord import SessionRecord
from session.SessionRegistrySnapshot import SessionRegistrySnapshot


@dataclass(frozen=True, slots=True)
class SessionDeleteTransactionContext:
    """Immutable input retained for a future delete execution transaction."""

    session_id: str
    memory_record_ids: tuple[str, ...]


class SessionDeleteTransactionService:
    """Prepare immutable delete transaction data without executing any mutation."""

    def prepare(self, plan: SessionDeletePlan) -> SessionDeleteTransactionContext:
        """Build the future transaction context from an approved deletion plan."""
        if plan.policy_decision.status is not SessionDeleteStatus.ALLOW:
            raise ValueError("Session delete plan must be allowed.")
        if plan.memory_record_ids_to_remove:
            raise ValueError(
                "Allowed session delete plan must not contain memory records."
            )
        return SessionDeleteTransactionContext(
            session_id=plan.session_id,
            memory_record_ids=plan.memory_record_ids_to_remove,
        )

    def build_candidate(
        self,
        context: SessionDeleteTransactionContext,
        snapshot: SessionRegistrySnapshot,
    ) -> SessionRegistrySnapshot:
        """Build a deletion candidate without changing the supplied registry."""
        remaining_sessions = tuple(
            session
            for session in snapshot.sessions
            if session.session_id != context.session_id
        )
        if len(remaining_sessions) == len(snapshot.sessions):
            raise ValueError("Session delete target is not present in snapshot.")
        return SessionRegistrySnapshot(
            active_session_id=snapshot.active_session_id,
            sessions=remaining_sessions,
        )

    def commit(
        self,
        context: SessionDeleteTransactionContext,
        sessions: SessionManager,
    ) -> tuple[SessionDeleteExecutionResult, SessionRecord]:
        """Commit one approved delete without publishing its lifecycle event."""
        if context.memory_record_ids:
            raise ValueError(
                "Session delete transaction must not contain memory records."
            )

        original = sessions.snapshot()
        deleted_session = next(
            (
                session
                for session in original.sessions
                if session.session_id == context.session_id
            ),
            None,
        )
        if deleted_session is None:
            raise ValueError("Session delete target is not present in snapshot.")
        candidate = self.build_candidate(context, original)
        sessions.apply_snapshot_if_current(original, candidate)

        return (
            SessionDeleteExecutionResult(
                session_id=context.session_id,
                memory_records_removed=0,
                committed=True,
            ),
            deleted_session,
        )

    def execute(
        self,
        context: SessionDeleteTransactionContext,
        sessions: SessionManager,
    ) -> SessionDeleteExecutionResult:
        """Commit one approved deletion and publish its lifecycle event."""
        result, deleted_session = self.commit(context, sessions)
        sessions.emit_deleted(deleted_session)
        return result
