"""Read-only session data returned through the Brain response boundary."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SessionSummary:
    """One registered session suitable for a non-persistent presentation list."""

    session_id: str
    active: bool
    conversation_count: int
