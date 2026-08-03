"""Standard response model returned by the Hypatia Brain."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BrainResponse:
    """Deterministic response from the first Brain implementation."""

    message: str
    request_id: str
    intent: str
    memory_count: int
