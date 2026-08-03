"""Standard response model returned by the Hypatia Brain."""

from __future__ import annotations

from dataclasses import dataclass, field

from knowledge.Chunk import Chunk


@dataclass(frozen=True, slots=True)
class BrainResponse:
    """Deterministic response from the first Brain implementation."""

    message: str
    request_id: str
    intent: str
    memory_count: int
    success: bool = True
    knowledge_results: list[Chunk] = field(default_factory=list)
