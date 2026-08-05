"""Pure decision policy for a future session-deletion transaction."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SessionDeleteStatus(Enum):
    """Possible outcomes for a known session deletion request."""

    ALLOW = "ALLOW"
    DENY = "DENY"
    PENDING_MEMORY_POLICY = "PENDING_MEMORY_POLICY"


@dataclass(frozen=True)
class SessionDeleteDecision:
    """Immutable policy result with no transaction or persistence behavior."""

    status: SessionDeleteStatus
    reason: str


class SessionDeletePolicy:
    """Evaluate known session deletion eligibility without external dependencies."""

    _DEFAULT_SESSION_ID = "default"

    @classmethod
    def evaluate(
        cls,
        session_id: str,
        active_session_id: str,
        matching_memory_ids: tuple[str, ...],
    ) -> SessionDeleteDecision:
        """Return the deterministic decision for one known session."""
        if session_id == cls._DEFAULT_SESSION_ID:
            return SessionDeleteDecision(
                status=SessionDeleteStatus.DENY,
                reason="default session cannot be deleted",
            )
        if session_id == active_session_id:
            return SessionDeleteDecision(
                status=SessionDeleteStatus.DENY,
                reason="active session cannot be deleted",
            )
        if matching_memory_ids:
            return SessionDeleteDecision(
                status=SessionDeleteStatus.PENDING_MEMORY_POLICY,
                reason="session has attached memories",
            )
        return SessionDeleteDecision(
            status=SessionDeleteStatus.ALLOW,
            reason="",
        )
