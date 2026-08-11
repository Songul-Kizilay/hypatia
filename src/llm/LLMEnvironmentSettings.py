"""Pure environment mapping loader for optional LLM runtime settings."""

from __future__ import annotations

import os
from collections.abc import Mapping

from llm.LLMRuntimeConfig import LLMRuntimeConfig


def load_llm_system_prompt(environment: Mapping[str, str]) -> str | None:
    """Return the configured system prompt without modifying it."""
    return environment.get("HYPATIA_LLM_SYSTEM_PROMPT")


def load_llm_environment_settings(
    environment: Mapping[str, str],
) -> tuple[LLMRuntimeConfig, str | None]:
    """Build non-secret LLM configuration and return its secret separately."""
    if environment.get("HYPATIA_LLM_ENABLED") != "true":
        return LLMRuntimeConfig(enabled=False, base_url="", model=""), None

    config = LLMRuntimeConfig(
        enabled=environment["HYPATIA_LLM_ENABLED"] == "true",
        base_url=environment.get("HYPATIA_LLM_BASE_URL", ""),
        model=environment.get("HYPATIA_LLM_MODEL", ""),
    )

    return config, environment.get("HYPATIA_LLM_API_KEY")


def load_llm_process_environment_settings() -> tuple[LLMRuntimeConfig, str | None]:
    """Load LLM settings from the current process environment."""
    return load_llm_environment_settings(os.environ)


def load_llm_process_system_prompt() -> str | None:
    """Load the system prompt from the current process environment."""
    return load_llm_system_prompt(os.environ)
