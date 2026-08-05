"""Read-only rules for identifying session conversation records."""

from __future__ import annotations

from memory.MemoryRecord import MemoryRecord


class SessionMemoryPolicy:
    """Defines the shared session ownership rules for conversation records."""

    @staticmethod
    def is_conversation(record: MemoryRecord) -> bool:
        """Return whether *record* is a normal brain conversation."""
        return {"brain", "conversation"}.issubset(record.tags)

    @staticmethod
    def belongs_to_session(record: MemoryRecord, session_id: str) -> bool:
        """Return whether *record* belongs to *session_id* under legacy rules."""
        record_session_id = record.metadata.get("session_id", "default")
        return isinstance(record_session_id, str) and record_session_id == session_id

    @classmethod
    def matches(cls, record: MemoryRecord, session_id: str) -> bool:
        """Return whether *record* is a conversation in *session_id*."""
        return cls.is_conversation(record) and cls.belongs_to_session(
            record, session_id
        )
