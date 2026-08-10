"""Pure environment mapping loader for optional LLM runtime settings."""

from __future__ import annotations

import os
from collections.abc import Mapping

from llm.LLMRuntimeConfig import LLMRuntimeConfig


def load_llm_environment_settings(
    environment: Mapping[str, str],
) -> tuple[LLMRuntimeConfig, str | None]:
    """Build non-secret LLM configuration and return its secret separately."""
    config = LLMRuntimeConfig(
        enabled=environment["HYPATIA_LLM_ENABLED"] == "true",
        base_url=environment["HYPATIA_LLM_BASE_URL"],
        model=environment["HYPATIA_LLM_MODEL"],
    )

    return config, environment.get("HYPATIA_LLM_API_KEY")


def load_llm_process_environment_settings() -> tuple[LLMRuntimeConfig, str | None]:
    """Load LLM settings from the current process environment."""
    return load_llm_environment_settings(os.environ)
