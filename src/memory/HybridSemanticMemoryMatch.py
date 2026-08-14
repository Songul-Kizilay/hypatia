"""One deterministic hybrid ranking result for a memory ID."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HybridSemanticMemoryMatch:
    """A memory ID and its rank-fusion score."""

    memory_id: str
    score: float
