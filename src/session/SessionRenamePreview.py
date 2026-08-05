"""Immutable read-only description of a session rename's effects."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SessionRenamePreview:
    """Summarize the state that an otherwise valid rename would affect."""

    source_session_id: str
    target_session_id: str
    memory_record_count: int
    active_session_changed: bool
