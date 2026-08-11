"""Opt-in activation boundary for the optional LLM runtime."""

from __future__ import annotations

from llm.LLMProvider import LLMProvider
from llm.LLMProviderFactory import create_llm_provider
from llm.LLMRuntimeConfig import LLMRuntimeConfig


def activate_llm(
    config: LLMRuntimeConfig,
    api_key: str,
    system_prompt: str | None = None,
) -> LLMProvider | None:
    """Create the configured provider only when LLM runtime is enabled."""
    if config.enabled is False:
        return None

    return create_llm_provider(
        base_url=config.base_url,
        api_key=api_key,
        model=config.model,
        system_prompt=system_prompt,
    )
