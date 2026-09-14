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
from llm.UrllibChatCompletionTransport import (
    DEFAULT_TIMEOUT_SECONDS,
)


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
            system_prompt=None,
            timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
        )
        sentinel_provider.generate.assert_not_called()

    def test_enabled_config_forwards_system_prompt_unchanged(self) -> None:
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
            provider = activate_llm(
                config,
                "test-api-key",
                system_prompt="You are Hypatia.",
            )

        self.assertIs(provider, sentinel_provider)
        provider_factory.assert_called_once_with(
            base_url="https://api.example.test/v1/chat/completions",
            api_key="test-api-key",
            model="test-model",
            system_prompt="You are Hypatia.",
            timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
        )
        sentinel_provider.generate.assert_not_called()

    def test_enabled_loopback_config_allows_no_api_key_and_slow_generation(
        self,
    ) -> None:
        config = LLMRuntimeConfig(
            enabled=True,
            base_url="http://localhost:11434/v1/chat/completions",
            model="local-model",
        )
        sentinel_provider = Mock(spec=LLMProvider)

        with patch(
            "llm.LLMRuntimeActivator.create_llm_provider",
            return_value=sentinel_provider,
        ) as provider_factory:
            provider = activate_llm(config, None)

        self.assertIs(provider, sentinel_provider)
        provider_factory.assert_called_once_with(
            base_url="http://localhost:11434/v1/chat/completions",
            api_key=None,
            model="local-model",
            system_prompt=None,
            timeout_seconds=300.0,
        )

    def test_enabled_config_uses_an_explicit_timeout_over_the_endpoint_default(
        self,
    ) -> None:
        config = LLMRuntimeConfig(
            enabled=True,
            base_url="http://localhost:11434/v1/chat/completions",
            model="local-model",
            timeout_seconds=7.5,
        )
        sentinel_provider = Mock(spec=LLMProvider)

        with patch(
            "llm.LLMRuntimeActivator.create_llm_provider",
            return_value=sentinel_provider,
        ) as provider_factory:
            provider = activate_llm(config, None)

        self.assertIs(provider, sentinel_provider)
        provider_factory.assert_called_once_with(
            base_url="http://localhost:11434/v1/chat/completions",
            api_key=None,
            model="local-model",
            system_prompt=None,
            timeout_seconds=7.5,
        )

    def test_enabled_remote_config_rejects_a_missing_api_key(self) -> None:
        config = LLMRuntimeConfig(
            enabled=True,
            base_url="https://api.example.test/v1/chat/completions",
            model="test-model",
        )

        with (
            patch("llm.LLMRuntimeActivator.create_llm_provider") as provider_factory,
            self.assertRaisesRegex(
                ValueError,
                "^LLM API key is required for a non-local LLM endpoint\\.$",
            ),
        ):
            activate_llm(config, None)

        provider_factory.assert_not_called()

    def test_enabled_config_rejects_a_non_loopback_http_endpoint(self) -> None:
        config = LLMRuntimeConfig(
            enabled=True,
            base_url="http://api.example.test/v1/chat/completions",
            model="test-model",
        )

        with (
            patch("llm.LLMRuntimeActivator.create_llm_provider") as provider_factory,
            self.assertRaises(ValueError) as raised,
        ):
            activate_llm(config, "test-api-key")

        self.assertEqual(
            str(raised.exception),
            "LLM base URL must use HTTPS unless it targets localhost, "
            "127.0.0.1, or ::1.",
        )
        provider_factory.assert_not_called()
