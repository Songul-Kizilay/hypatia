"""Immutable description of a future session deletion mutation."""

from __future__ import annotations

from dataclasses import dataclass

from session.SessionDeletePolicy import SessionDeleteDecision, SessionDeleteStatus


@dataclass(frozen=True, slots=True)
class SessionDeletePlan:
    """Describe one policy-approved session deletion without executing it."""

    session_id: str
    memory_record_ids_to_remove: tuple[str, ...]
    policy_decision: SessionDeleteDecision

    @classmethod
    def for_decision(
        cls,
        session_id: str,
        memory_record_ids: tuple[str, ...],
        decision: SessionDeleteDecision,
    ) -> SessionDeletePlan | None:
        """Return an executable future plan only for an allowed decision."""
        if decision.status is not SessionDeleteStatus.ALLOW:
            return None
        return cls(
            session_id=session_id,
            memory_record_ids_to_remove=memory_record_ids,
            policy_decision=decision,
        )
