"""Configuration contract for optional LLM runtime activation."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class LLMRuntimeConfig:
    """Non-secret configuration required to describe an LLM runtime."""

    enabled: bool
    base_url: str
    model: str
    timeout_seconds: float | None = None

    def __post_init__(self) -> None:
        """Reject invalid non-secret LLM request timeouts."""
        if self.timeout_seconds is None:
            return
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or not isfinite(self.timeout_seconds)
            or self.timeout_seconds <= 0
        ):
            raise ValueError("LLM timeout must be a positive number.")
