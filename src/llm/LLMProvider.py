"""Provider-independent contract for language-model generation."""

from __future__ import annotations

from typing import Protocol


class LLMError(Exception):
    """Raised when LLM generation cannot complete."""


class LLMProvider(Protocol):
    """Generate a text response for a prompt."""

    def generate(self, prompt: str) -> str:
        """Return a generated response for the supplied prompt."""
