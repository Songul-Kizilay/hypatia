from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from llm.LLMEnvironmentSettings import load_llm_environment_settings
from llm.LLMRuntimeConfig import LLMRuntimeConfig


class LLMEnvironmentSettingsTests(unittest.TestCase):
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
