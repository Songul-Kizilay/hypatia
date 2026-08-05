"""Public result of an in-process session rename transaction."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SessionRenameResult:
    """Describes the completed rename without retaining runtime references."""

    source_session_id: str
    target_session_id: str
    memory_record_count: int
    active_session_changed: bool
