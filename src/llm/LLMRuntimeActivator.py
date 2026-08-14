"""Opt-in activation boundary for the optional LLM runtime."""

from __future__ import annotations

from llm.LLMEndpointPolicy import is_loopback_llm_endpoint, validate_llm_endpoint
from llm.LLMProvider import LLMProvider
from llm.LLMProviderFactory import create_llm_provider
from llm.LLMRuntimeConfig import LLMRuntimeConfig


def activate_llm(
    config: LLMRuntimeConfig,
    api_key: str | None,
    system_prompt: str | None = None,
) -> LLMProvider | None:
    """Create the configured provider only when LLM runtime is enabled."""
    if config.enabled is False:
        return None

    endpoint = validate_llm_endpoint(config.base_url)
    if api_key is not None and not api_key.strip():
        api_key = None
    if api_key is None and not is_loopback_llm_endpoint(endpoint):
        raise ValueError("LLM API key is required for a non-local LLM endpoint.")

    return create_llm_provider(
        base_url=endpoint,
        api_key=api_key,
        model=config.model,
        system_prompt=system_prompt,
    )
