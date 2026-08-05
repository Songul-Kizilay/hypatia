"""Immutable persistence snapshot for the session registry."""

from __future__ import annotations

from dataclasses import dataclass

from session.SessionRecord import SessionRecord


@dataclass(frozen=True, slots=True)
class SessionRegistrySnapshot:
    """Captures the active session and ordered registered sessions."""

    active_session_id: str
    sessions: tuple[SessionRecord, ...]
