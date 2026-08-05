"""Immutable description of a future session rename mutation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SessionRenamePlan:
    """Describes every session and memory identifier affected by a rename."""

    source_session_id: str
    target_session_id: str
    updated_session_ids: tuple[str, ...]
    updated_active_session_id: str
    memory_record_ids_to_update: tuple[str, ...]
