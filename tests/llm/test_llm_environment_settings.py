from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from llm.LLMEnvironmentSettings import (
    DEFAULT_LLM_HISTORY_MAX_TURNS,
    UNBOUNDED_LLM_HISTORY,
    load_llm_environment_settings,
    load_llm_history_max_turns,
    load_llm_process_environment_settings,
    load_llm_process_history_max_turns,
    load_llm_process_system_prompt,
    load_llm_system_prompt,
    load_llm_timeout_seconds,
)
from llm.LLMRuntimeConfig import LLMRuntimeConfig


class LLMEnvironmentSettingsTests(unittest.TestCase):
    def test_history_max_turns_loader_maps_optional_positive_integer(self) -> None:
        environment = {"HYPATIA_LLM_HISTORY_MAX_TURNS": "8"}

        self.assertEqual(load_llm_history_max_turns(environment), 8)
        self.assertEqual(environment, {"HYPATIA_LLM_HISTORY_MAX_TURNS": "8"})

    def test_history_is_bounded_by_default(self) -> None:
        """An unset limit must not mean an unbounded transcript.

        A small local context window truncates the oldest-first ordering the
        server receives, so an unbounded history pushes the newest user message
        toward the edge and the model answers the previous question.
        """
        self.assertEqual(
            load_llm_history_max_turns({}),
            DEFAULT_LLM_HISTORY_MAX_TURNS,
        )

    def test_unbounded_history_remains_available_explicitly(self) -> None:
        self.assertIsNone(
            load_llm_history_max_turns(
                {"HYPATIA_LLM_HISTORY_MAX_TURNS": UNBOUNDED_LLM_HISTORY}
            )
        )

    def test_history_max_turns_loader_rejects_invalid_values(self) -> None:
        expected_message = "HYPATIA_LLM_HISTORY_MAX_TURNS must be a positive integer."

        for value in ("", " ", "0", "-1", "abc", " 8 "):
            with self.subTest(value=value):
                with self.assertRaises(ValueError) as raised:
                    load_llm_history_max_turns({"HYPATIA_LLM_HISTORY_MAX_TURNS": value})
                self.assertEqual(str(raised.exception), expected_message)

    def test_timeout_loader_maps_optional_positive_finite_number(self) -> None:
        environment = {"HYPATIA_LLM_TIMEOUT_SECONDS": "7.5"}

        self.assertIsNone(load_llm_timeout_seconds({}))
        self.assertEqual(load_llm_timeout_seconds(environment), 7.5)
        self.assertEqual(environment, {"HYPATIA_LLM_TIMEOUT_SECONDS": "7.5"})

    def test_timeout_loader_rejects_invalid_values(self) -> None:
        expected_message = (
            "HYPATIA_LLM_TIMEOUT_SECONDS must be a positive finite number."
        )

        for value in ("", " ", "0", "-1", "nan", "inf", "abc"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError) as raised:
                    load_llm_timeout_seconds({"HYPATIA_LLM_TIMEOUT_SECONDS": value})
                self.assertEqual(str(raised.exception), expected_message)

    def test_system_prompt_loader_preserves_value_and_mapping(self) -> None:
        environment = {
            "HYPATIA_LLM_SYSTEM_PROMPT": "  You are Hypatia.  ",
        }

        result = load_llm_system_prompt(environment)

        self.assertEqual(result, "  You are Hypatia.  ")
        self.assertEqual(
            environment,
            {"HYPATIA_LLM_SYSTEM_PROMPT": "  You are Hypatia.  "},
        )
        self.assertIsNone(load_llm_system_prompt({}))

    def test_loader_maps_missing_model_to_empty_when_enabled(self) -> None:
        environment = {
            "HYPATIA_LLM_ENABLED": "true",
            "HYPATIA_LLM_BASE_URL": "https://api.example.test/v1/chat/completions",
            "HYPATIA_LLM_API_KEY": "test-api-key",
        }

        config, api_key = load_llm_environment_settings(environment)

        self.assertEqual(
            config,
            LLMRuntimeConfig(
                enabled=True,
                base_url="https://api.example.test/v1/chat/completions",
                model="",
            ),
        )
        self.assertEqual(api_key, "test-api-key")
        self.assertEqual(
            environment,
            {
                "HYPATIA_LLM_ENABLED": "true",
                "HYPATIA_LLM_BASE_URL": "https://api.example.test/v1/chat/completions",
                "HYPATIA_LLM_API_KEY": "test-api-key",
            },
        )

    def test_loader_maps_missing_base_url_to_empty_when_enabled(self) -> None:
        environment = {
            "HYPATIA_LLM_ENABLED": "true",
            "HYPATIA_LLM_MODEL": "test-model",
            "HYPATIA_LLM_API_KEY": "test-api-key",
        }

        config, api_key = load_llm_environment_settings(environment)

        self.assertEqual(
            config,
            LLMRuntimeConfig(enabled=True, base_url="", model="test-model"),
        )
        self.assertEqual(api_key, "test-api-key")
        self.assertEqual(
            environment,
            {
                "HYPATIA_LLM_ENABLED": "true",
                "HYPATIA_LLM_MODEL": "test-model",
                "HYPATIA_LLM_API_KEY": "test-api-key",
            },
        )

    def test_loader_defaults_to_disabled_when_enable_flag_is_false(self) -> None:
        environment = {"HYPATIA_LLM_ENABLED": "false"}

        config, api_key = load_llm_environment_settings(environment)

        self.assertEqual(
            config,
            LLMRuntimeConfig(enabled=False, base_url="", model=""),
        )
        self.assertIsNone(api_key)
        self.assertEqual(environment, {"HYPATIA_LLM_ENABLED": "false"})

    def test_loader_defaults_to_disabled_when_enable_flag_is_absent(self) -> None:
        environment: dict[str, str] = {}

        config, api_key = load_llm_environment_settings(environment)

        self.assertEqual(
            config,
            LLMRuntimeConfig(enabled=False, base_url="", model=""),
        )
        self.assertIsNone(api_key)
        self.assertEqual(environment, {})

    def test_loader_preserves_values_and_keeps_api_key_separate(self) -> None:
        environment = {
            "HYPATIA_LLM_ENABLED": "true",
            "HYPATIA_LLM_BASE_URL": "https://api.example.test/v1/chat/completions",
            "HYPATIA_LLM_MODEL": "test-model",
            "HYPATIA_LLM_API_KEY": "test-api-key",
            "HYPATIA_LLM_TIMEOUT_SECONDS": "7.5",
        }

        config, api_key = load_llm_environment_settings(environment)

        self.assertEqual(
            config,
            LLMRuntimeConfig(
                enabled=True,
                base_url="https://api.example.test/v1/chat/completions",
                model="test-model",
                timeout_seconds=7.5,
            ),
        )
        self.assertEqual(api_key, "test-api-key")
        self.assertNotIn("api_key", config.__dataclass_fields__)
        self.assertEqual(
            environment,
            {
                "HYPATIA_LLM_ENABLED": "true",
                "HYPATIA_LLM_BASE_URL": "https://api.example.test/v1/chat/completions",
                "HYPATIA_LLM_MODEL": "test-model",
                "HYPATIA_LLM_API_KEY": "test-api-key",
                "HYPATIA_LLM_TIMEOUT_SECONDS": "7.5",
            },
        )

    def test_process_environment_loader_delegates_to_the_pure_loader(self) -> None:
        sentinel_config = LLMRuntimeConfig(
            enabled=True,
            base_url="https://api.example.test/v1/chat/completions",
            model="test-model",
        )
        sentinel_result = (sentinel_config, "test-api-key")

        with patch(
            "llm.LLMEnvironmentSettings.load_llm_environment_settings",
            return_value=sentinel_result,
        ) as pure_loader:
            result = load_llm_process_environment_settings()

        self.assertIs(result, sentinel_result)
        pure_loader.assert_called_once_with(os.environ)

    def test_process_system_prompt_loader_delegates_to_the_pure_loader(self) -> None:
        with patch(
            "llm.LLMEnvironmentSettings.load_llm_system_prompt",
            return_value="sentinel-system-prompt",
        ) as pure_loader:
            result = load_llm_process_system_prompt()

        self.assertEqual(result, "sentinel-system-prompt")
        pure_loader.assert_called_once_with(os.environ)

    def test_process_history_max_turns_loader_delegates_to_the_pure_loader(
        self,
    ) -> None:
        with patch(
            "llm.LLMEnvironmentSettings.load_llm_history_max_turns",
            return_value=8,
        ) as pure_loader:
            result = load_llm_process_history_max_turns()

        self.assertEqual(result, 8)
        pure_loader.assert_called_once_with(os.environ)
