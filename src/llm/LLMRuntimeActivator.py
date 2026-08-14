"""Opt-in activation boundary for the optional LLM runtime."""

from __future__ import annotations

from llm.LLMEndpointPolicy import is_loopback_llm_endpoint, validate_llm_endpoint
from llm.LLMProvider import LLMProvider
from llm.LLMProviderFactory import create_llm_provider
from llm.LLMRuntimeConfig import LLMRuntimeConfig
from llm.UrllibChatCompletionTransport import (
    DEFAULT_TIMEOUT_SECONDS,
    LOCAL_DEFAULT_TIMEOUT_SECONDS,
)


def activate_llm(
    config: LLMRuntimeConfig,
    api_key: str | None,
    system_prompt: str | None = None,
) -> LLMProvider | None:
    """Create the configured provider only when LLM runtime is enabled."""
    if config.enabled is False:
        return None

    endpoint = validate_llm_endpoint(config.base_url)
    is_loopback = is_loopback_llm_endpoint(endpoint)
    if api_key is not None and not api_key.strip():
        api_key = None
    if api_key is None and not is_loopback:
        raise ValueError("LLM API key is required for a non-local LLM endpoint.")
    timeout_seconds = config.timeout_seconds
    if timeout_seconds is None:
        timeout_seconds = (
            LOCAL_DEFAULT_TIMEOUT_SECONDS if is_loopback else DEFAULT_TIMEOUT_SECONDS
        )

    return create_llm_provider(
        base_url=endpoint,
        api_key=api_key,
        model=config.model,
        system_prompt=system_prompt,
        timeout_seconds=timeout_seconds,
    )
