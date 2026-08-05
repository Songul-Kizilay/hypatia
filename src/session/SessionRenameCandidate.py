"""Immutable, in-process candidates for a planned session rename."""

from __future__ import annotations

from dataclasses import dataclass

from memory.MemoryRecord import MemoryRecord
from session.SessionRegistrySnapshot import SessionRegistrySnapshot
from session.SessionRenamePlan import SessionRenamePlan


@dataclass(frozen=True, slots=True)
class SessionRenameCandidate:
    """Contains the proposed registry and memory state for a rename plan."""

    plan: SessionRenamePlan
    session_snapshot: SessionRegistrySnapshot
    memory_records: tuple[MemoryRecord, ...]
