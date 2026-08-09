"""Pure memory-policy decisions for future session deletion."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SessionDeleteMemoryAction(Enum):
    """Actions permitted by the current session-delete memory policy."""

    NONE = "none"
    BLOCK = "block"


@dataclass(frozen=True, slots=True)
class SessionDeleteMemoryDecision:
    """Immutable decision for memory records attached to a session."""

    action: SessionDeleteMemoryAction
    memory_record_ids: tuple[str, ...]
    reason: str | None


class SessionDeleteMemoryPolicy:
    """Decide whether attached memories block a future session deletion."""

    @staticmethod
    def evaluate(
        memory_record_ids: tuple[str, ...],
    ) -> SessionDeleteMemoryDecision:
        """Return a deterministic, read-only decision for ordered memory IDs."""
        if not memory_record_ids:
            return SessionDeleteMemoryDecision(
                action=SessionDeleteMemoryAction.NONE,
                memory_record_ids=(),
                reason=None,
            )
        return SessionDeleteMemoryDecision(
            action=SessionDeleteMemoryAction.BLOCK,
            memory_record_ids=memory_record_ids,
            reason="session has attached memories",
        )
