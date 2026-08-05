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
    memory_record_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        """Keep the preview's read-only memory impact internally consistent."""
        if not isinstance(self.memory_record_ids, tuple):
            raise TypeError("Preview memory record IDs must be a tuple.")
        if len(self.memory_record_ids) != self.memory_record_count:
            raise ValueError("Preview memory record IDs must match the record count.")
        if len(set(self.memory_record_ids)) != len(self.memory_record_ids):
            raise ValueError("Preview memory record IDs must be unique.")
