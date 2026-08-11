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
    load_llm_environment_settings,
    load_llm_process_environment_settings,
)
from llm.LLMRuntimeConfig import LLMRuntimeConfig


class LLMEnvironmentSettingsTests(unittest.TestCase):
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
        }

        config, api_key = load_llm_environment_settings(environment)

        self.assertEqual(
            config,
            LLMRuntimeConfig(
                enabled=True,
                base_url="https://api.example.test/v1/chat/completions",
                model="test-model",
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
