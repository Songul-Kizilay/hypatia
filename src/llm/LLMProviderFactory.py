"""Composition helpers for the default OpenAI-compatible LLM provider."""

from __future__ import annotations

from llm.LLMProvider import LLMProvider
from llm.OpenAICompatibleProvider import OpenAICompatibleProvider
from llm.UrllibChatCompletionTransport import UrllibChatCompletionTransport


def create_llm_provider(
    base_url: str,
    api_key: str,
    model: str,
    system_prompt: str | None = None,
) -> LLMProvider:
    """Compose an OpenAI-compatible provider with the stdlib transport."""
    return OpenAICompatibleProvider(
        base_url=base_url,
        api_key=api_key,
        model=model,
        transport=UrllibChatCompletionTransport(),
        system_prompt=system_prompt,
    )
