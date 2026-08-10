from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from cognition.CognitiveEngine import CognitiveEngine
from core.Bootstrap import Bootstrap
from llm.LLMProvider import LLMProvider
from llm.LLMRuntimeConfig import LLMRuntimeConfig


class FakeLLMProvider(LLMProvider):
    def __init__(self) -> None:
        self.generate_calls = 0

    def generate(self, prompt: str) -> str:
        self.generate_calls += 1
        return "unused"


class BootstrapLLMProviderTests(unittest.TestCase):
    def test_bootstrap_passes_the_supplied_provider_to_cognitive_engine(self) -> None:
        provider = FakeLLMProvider()

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            bootstrap = Bootstrap(
                memory_path=temporary_path / "memory.json",
                session_path=temporary_path / "sessions.json",
                llm_provider=provider,
            )
            bootstrap.initialize()

            cognitive_engine = bootstrap.container.resolve(CognitiveEngine)

        self.assertIs(cognitive_engine._llm_provider, provider)
        self.assertEqual(provider.generate_calls, 0)

    def test_disabled_config_keeps_the_cognitive_engine_provider_free(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            bootstrap = Bootstrap(
                memory_path=temporary_path / "memory.json",
                session_path=temporary_path / "sessions.json",
                llm_config=LLMRuntimeConfig(
                    enabled=False,
                    base_url="https://api.example.test/v1/chat/completions",
                    model="test-model",
                ),
            )

            with patch("llm.LLMRuntimeActivator.activate_llm") as activate_llm:
                bootstrap.initialize()

            cognitive_engine = bootstrap.container.resolve(CognitiveEngine)

        self.assertIsNone(cognitive_engine._llm_provider)
        activate_llm.assert_not_called()

    def test_enabled_config_activates_and_passes_the_provider_to_cognition(
        self,
    ) -> None:
        config = LLMRuntimeConfig(
            enabled=True,
            base_url="https://api.example.test/v1/chat/completions",
            model="test-model",
        )
        sentinel_provider = Mock(spec=LLMProvider)

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            bootstrap = Bootstrap(
                memory_path=temporary_path / "memory.json",
                session_path=temporary_path / "sessions.json",
                llm_config=config,
                llm_api_key="test-api-key",
            )

            with patch(
                "core.Bootstrap.activate_llm",
                return_value=sentinel_provider,
            ) as activate_llm:
                bootstrap.initialize()

            cognitive_engine = bootstrap.container.resolve(CognitiveEngine)

        activate_llm.assert_called_once_with(config, "test-api-key")
        self.assertIs(cognitive_engine._llm_provider, sentinel_provider)
        sentinel_provider.generate.assert_not_called()

    def test_enabled_config_without_an_api_key_fails_before_activation(self) -> None:
        config = LLMRuntimeConfig(
            enabled=True,
            base_url="https://api.example.test/v1/chat/completions",
            model="test-model",
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            bootstrap = Bootstrap(
                memory_path=temporary_path / "memory.json",
                session_path=temporary_path / "sessions.json",
                llm_config=config,
            )

            with patch("core.Bootstrap.activate_llm") as activate_llm:
                with self.assertRaisesRegex(
                    RuntimeError,
                    "^LLM API key is required when LLM is enabled\\.$",
                ):
                    bootstrap.initialize()

        activate_llm.assert_not_called()

    def test_enabled_config_with_an_empty_api_key_fails_before_activation(self) -> None:
        config = LLMRuntimeConfig(
            enabled=True,
            base_url="https://api.example.test/v1/chat/completions",
            model="test-model",
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            bootstrap = Bootstrap(
                memory_path=temporary_path / "memory.json",
                session_path=temporary_path / "sessions.json",
                llm_config=config,
                llm_api_key="",
            )

            with patch("core.Bootstrap.activate_llm") as activate_llm:
                with self.assertRaisesRegex(
                    RuntimeError,
                    "^LLM API key is required when LLM is enabled\\.$",
                ):
                    bootstrap.initialize()

        activate_llm.assert_not_called()

    def test_enabled_config_with_a_whitespace_only_api_key_fails_before_activation(
        self,
    ) -> None:
        config = LLMRuntimeConfig(
            enabled=True,
            base_url="https://api.example.test/v1/chat/completions",
            model="test-model",
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            bootstrap = Bootstrap(
                memory_path=temporary_path / "memory.json",
                session_path=temporary_path / "sessions.json",
                llm_config=config,
                llm_api_key="   ",
            )

            with patch("core.Bootstrap.activate_llm") as activate_llm:
                with self.assertRaisesRegex(
                    RuntimeError,
                    "^LLM API key is required when LLM is enabled\\.$",
                ):
                    bootstrap.initialize()

        activate_llm.assert_not_called()

    def test_enabled_config_with_an_empty_base_url_fails_before_activation(
        self,
    ) -> None:
        config = LLMRuntimeConfig(
            enabled=True,
            base_url="",
            model="test-model",
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            bootstrap = Bootstrap(
                memory_path=temporary_path / "memory.json",
                session_path=temporary_path / "sessions.json",
                llm_config=config,
                llm_api_key="test-api-key",
            )

            with patch("core.Bootstrap.activate_llm") as activate_llm:
                with self.assertRaisesRegex(
                    RuntimeError,
                    "^LLM base URL is required when LLM is enabled\\.$",
                ):
                    bootstrap.initialize()

        activate_llm.assert_not_called()
