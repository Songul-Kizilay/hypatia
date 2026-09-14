"""Pure environment mapping loader for optional LLM runtime settings."""

from __future__ import annotations

import os
from collections.abc import Mapping
from math import isfinite

from llm.LLMRuntimeConfig import LLMRuntimeConfig


def load_llm_system_prompt(environment: Mapping[str, str]) -> str | None:
    """Return the configured system prompt without modifying it."""
    return environment.get("HYPATIA_LLM_SYSTEM_PROMPT")


DEFAULT_LLM_HISTORY_MAX_TURNS = 12
UNBOUNDED_LLM_HISTORY = "unbounded"


def load_llm_history_max_turns(environment: Mapping[str, str]) -> int | None:
    """Return the conversation history turn limit, bounded unless overridden.

    An unset value means a bounded default rather than unlimited history. Local
    models commonly run with a small context window, and an unbounded
    transcript pushes the newest user message toward the truncation edge, where
    the model answers the previous question instead of the current one. The
    literal "unbounded" restores the old behaviour for anyone who wants it.
    """
    value = environment.get("HYPATIA_LLM_HISTORY_MAX_TURNS")
    if value is None:
        return DEFAULT_LLM_HISTORY_MAX_TURNS
    if value == UNBOUNDED_LLM_HISTORY:
        return None
    if not value.isascii() or not value.isdecimal():
        raise ValueError("HYPATIA_LLM_HISTORY_MAX_TURNS must be a positive integer.")

    max_turns = int(value)
    if max_turns <= 0:
        raise ValueError("HYPATIA_LLM_HISTORY_MAX_TURNS must be a positive integer.")
    return max_turns


def load_llm_timeout_seconds(environment: Mapping[str, str]) -> float | None:
    """Return the configured positive finite LLM request timeout in seconds."""
    value = environment.get("HYPATIA_LLM_TIMEOUT_SECONDS")
    if value is None:
        return None

    try:
        timeout_seconds = float(value)
    except ValueError as error:
        raise ValueError(
            "HYPATIA_LLM_TIMEOUT_SECONDS must be a positive finite number."
        ) from error

    if not isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError(
            "HYPATIA_LLM_TIMEOUT_SECONDS must be a positive finite number."
        )
    return timeout_seconds


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
        timeout_seconds=load_llm_timeout_seconds(environment),
    )

    return config, environment.get("HYPATIA_LLM_API_KEY")


def load_llm_process_environment_settings() -> tuple[LLMRuntimeConfig, str | None]:
    """Load LLM settings from the current process environment."""
    return load_llm_environment_settings(os.environ)


def load_llm_process_system_prompt() -> str | None:
    """Load the system prompt from the current process environment."""
    return load_llm_system_prompt(os.environ)


def load_llm_process_history_max_turns() -> int | None:
    """Load the conversation history turn limit from the process environment."""
    return load_llm_history_max_turns(os.environ)
