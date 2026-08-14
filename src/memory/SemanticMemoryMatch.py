"""A deterministic semantic-index query result."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SemanticMemoryMatch:
    """One indexed memory ID and its cosine-similarity score."""

    memory_id: str
    score: float
