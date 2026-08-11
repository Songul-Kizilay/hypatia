"""Provider-independent contract for language-model generation."""

from __future__ import annotations

from typing import Protocol

from llm.LLMConversationMessage import LLMConversationMessage


class LLMError(Exception):
    """Raised when LLM generation cannot complete."""


class LLMProvider(Protocol):
    """Generate a text response for a prompt."""

    def generate(
        self,
        prompt: str,
        history: tuple[LLMConversationMessage, ...] = (),
    ) -> str:
        """Return a response for the prompt and optional conversation history."""
