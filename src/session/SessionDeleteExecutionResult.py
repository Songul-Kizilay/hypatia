"""Immutable result contract for a future session-delete execution."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SessionDeleteExecutionResult:
    """Describe a completed future delete execution without performing it."""

    session_id: str
    memory_records_removed: int
    committed: bool
