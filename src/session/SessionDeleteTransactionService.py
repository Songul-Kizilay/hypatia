"""Preparation boundary for a future session-delete transaction."""

from __future__ import annotations

from dataclasses import dataclass

from session.SessionDeletePlan import SessionDeletePlan
from session.SessionDeletePolicy import SessionDeleteStatus
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
