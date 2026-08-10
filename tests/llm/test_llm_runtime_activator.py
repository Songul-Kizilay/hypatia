from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from llm.LLMProvider import LLMProvider
from llm.LLMRuntimeActivator import activate_llm
from llm.LLMRuntimeConfig import LLMRuntimeConfig


class LLMRuntimeActivatorTests(unittest.TestCase):
    def test_disabled_config_returns_none_without_creating_a_provider(self) -> None:
        config = LLMRuntimeConfig(
            enabled=False,
            base_url="https://api.example.test/v1/chat/completions",
            model="test-model",
        )

        with patch("llm.LLMRuntimeActivator.create_llm_provider") as provider_factory:
            provider = activate_llm(config, "test-api-key")

        self.assertIsNone(provider)
        provider_factory.assert_not_called()

    def test_enabled_config_creates_and_returns_the_configured_provider(self) -> None:
        config = LLMRuntimeConfig(
            enabled=True,
            base_url="https://api.example.test/v1/chat/completions",
            model="test-model",
        )
        sentinel_provider = Mock(spec=LLMProvider)

        with patch(
            "llm.LLMRuntimeActivator.create_llm_provider",
            return_value=sentinel_provider,
        ) as provider_factory:
            provider = activate_llm(config, "test-api-key")

        self.assertIs(provider, sentinel_provider)
        provider_factory.assert_called_once_with(
            base_url="https://api.example.test/v1/chat/completions",
            api_key="test-api-key",
            model="test-model",
        )
        sentinel_provider.generate.assert_not_called()
