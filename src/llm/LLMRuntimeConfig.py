"""Configuration contract for optional LLM runtime activation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LLMRuntimeConfig:
    """Non-secret configuration required to describe an LLM runtime."""

    enabled: bool
    base_url: str
    model: str
