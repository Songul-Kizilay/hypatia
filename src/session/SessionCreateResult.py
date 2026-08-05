"""Immutable result returned when creating a session."""

from __future__ import annotations

from dataclasses import dataclass

from session.SessionRecord import SessionRecord


@dataclass(frozen=True, slots=True)
class SessionCreateResult:
    """Reports the session returned by a create request and whether it is new."""

    session: SessionRecord
    created: bool
