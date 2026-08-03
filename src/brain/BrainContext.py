"""Request-scoped Brain processing context."""

from __future__ import annotations

from dataclasses import dataclass, field

from brain.BrainRequest import BrainRequest
from memory.MemoryRecord import MemoryRecord


@dataclass(slots=True)
class BrainContext:
    """Data collected while processing one Brain request."""

    request: BrainRequest
    intent: str = "unknown"
    memories: list[MemoryRecord] = field(default_factory=list)
