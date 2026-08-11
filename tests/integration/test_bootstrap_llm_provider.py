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
from llm.HypatiaSystemPrompt import HYPATIA_DEFAULT_SYSTEM_PROMPT
from llm.LLMProvider import LLMProvider
from llm.LLMRuntimeConfig import LLMRuntimeConfig
from llm.OpenAICompatibleProvider import OpenAICompatibleProvider


class FakeLLMProvider(LLMProvider):
    def __init__(self) -> None:
        self.generate_calls = 0

    def generate(self, prompt: str) -> str:
        self.generate_calls += 1
        return "unused"


class BootstrapLLMProviderTests(unittest.TestCase):
    def test_process_environment_factory_activates_and_passes_provider_to_cognition(
        self,
    ) -> None:
        sentinel_config = LLMRuntimeConfig(
            enabled=True,
            base_url="https://api.example.test/v1/chat/completions",
            model="test-model",
        )
        sentinel_provider = Mock(spec=LLMProvider)

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            memory_path = temporary_path / "memory.json"
            session_path = temporary_path / "sessions.json"

            with (
                patch(
                    "core.Bootstrap.load_llm_process_environment_settings",
                    return_value=(sentinel_config, "test-api-key"),
                ) as settings_loader,
                patch(
                    "core.Bootstrap.load_llm_process_system_prompt",
                    return_value="  Custom prompt.  ",
                ) as system_prompt_loader,
                patch(
                    "core.Bootstrap.activate_llm",
                    return_value=sentinel_provider,
                ) as activate_llm,
            ):
                bootstrap = Bootstrap.from_process_environment(
                    memory_path,
                    session_path,
                )
                bootstrap.initialize()

            cognitive_engine = bootstrap.container.resolve(CognitiveEngine)

        settings_loader.assert_called_once_with()
        system_prompt_loader.assert_called_once_with()
        activate_llm.assert_called_once_with(
            sentinel_config,
            "test-api-key",
            system_prompt="  Custom prompt.  ",
        )
        self.assertIs(cognitive_engine._llm_provider, sentinel_provider)
        sentinel_provider.generate.assert_not_called()

    def test_process_environment_factory_uses_default_system_prompt_when_absent(
        self,
    ) -> None:
        sentinel_config = LLMRuntimeConfig(
            enabled=True,
            base_url="https://api.example.test/v1/chat/completions",
            model="test-model",
        )
        sentinel_provider = Mock(spec=LLMProvider)

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)

            with (
                patch(
                    "core.Bootstrap.load_llm_process_environment_settings",
                    return_value=(sentinel_config, "test-api-key"),
                ) as settings_loader,
                patch(
                    "core.Bootstrap.load_llm_process_system_prompt",
                    return_value=None,
                ) as system_prompt_loader,
                patch(
                    "core.Bootstrap.activate_llm",
                    return_value=sentinel_provider,
                ) as activate_llm,
            ):
                bootstrap = Bootstrap.from_process_environment(
                    temporary_path / "memory.json",
                    temporary_path / "sessions.json",
                )
                bootstrap.initialize()

        settings_loader.assert_called_once_with()
        system_prompt_loader.assert_called_once_with()
        self.assertEqual(
            bootstrap._llm_system_prompt,
            HYPATIA_DEFAULT_SYSTEM_PROMPT,
        )
        activate_llm.assert_called_once_with(
            sentinel_config,
            "test-api-key",
            system_prompt=HYPATIA_DEFAULT_SYSTEM_PROMPT,
        )

    def test_default_system_prompt_reaches_the_composed_provider(self) -> None:
        sentinel_config = LLMRuntimeConfig(
            enabled=True,
            base_url="https://api.example.test/v1/chat/completions",
            model="test-model",
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)

            with (
                patch(
                    "core.Bootstrap.load_llm_process_environment_settings",
                    return_value=(sentinel_config, "test-api-key"),
                ),
                patch(
                    "core.Bootstrap.load_llm_process_system_prompt",
                    return_value=None,
                ),
            ):
                bootstrap = Bootstrap.from_process_environment(
                    temporary_path / "memory.json",
                    temporary_path / "sessions.json",
                )
                bootstrap.initialize()

            cognitive_engine = bootstrap.container.resolve(CognitiveEngine)

        provider = cognitive_engine._llm_provider
        self.assertIsInstance(provider, OpenAICompatibleProvider)
        self.assertEqual(
            provider._system_prompt,
            HYPATIA_DEFAULT_SYSTEM_PROMPT,
        )

    def test_process_environment_factory_preserves_loaded_settings(self) -> None:
        sentinel_config = LLMRuntimeConfig(
            enabled=True,
            base_url="https://api.example.test/v1/chat/completions",
            model="test-model",
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            memory_path = temporary_path / "memory.json"
            session_path = temporary_path / "sessions.json"

            with (
                patch(
                    "core.Bootstrap.load_llm_process_environment_settings",
                    return_value=(sentinel_config, "test-api-key"),
                ) as settings_loader,
                patch(
                    "core.Bootstrap.load_llm_process_system_prompt",
                    return_value="You are Hypatia.",
                ) as system_prompt_loader,
                patch("core.Bootstrap.activate_llm") as activate_llm,
            ):
                bootstrap = Bootstrap.from_process_environment(
                    memory_path,
                    session_path,
                )

        settings_loader.assert_called_once_with()
        system_prompt_loader.assert_called_once_with()
        self.assertIs(bootstrap._llm_config, sentinel_config)
        self.assertEqual(bootstrap._llm_api_key, "test-api-key")
        self.assertEqual(bootstrap._llm_system_prompt, "You are Hypatia.")
        self.assertIs(bootstrap._memory_path, memory_path)
        self.assertIs(bootstrap._session_path, session_path)
        activate_llm.assert_not_called()

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

        activate_llm.assert_called_once_with(
            config,
            "test-api-key",
            system_prompt=None,
        )
        self.assertIs(cognitive_engine._llm_provider, sentinel_provider)
        sentinel_provider.generate.assert_not_called()

    def test_enabled_config_forwards_system_prompt_unchanged(self) -> None:
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
                llm_system_prompt="You are Hypatia.",
            )

            with patch(
                "core.Bootstrap.activate_llm",
                return_value=sentinel_provider,
            ) as activate_llm:
                bootstrap.initialize()

            cognitive_engine = bootstrap.container.resolve(CognitiveEngine)

        activate_llm.assert_called_once_with(
            config,
            "test-api-key",
            system_prompt="You are Hypatia.",
        )
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

    def test_enabled_config_with_a_whitespace_only_base_url_fails_before_activation(
        self,
    ) -> None:
        config = LLMRuntimeConfig(
            enabled=True,
            base_url="   ",
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

    def test_enabled_config_with_an_empty_model_fails_before_activation(
        self,
    ) -> None:
        config = LLMRuntimeConfig(
            enabled=True,
            base_url="https://api.example.test/v1/chat/completions",
            model="",
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
                    "^LLM model is required when LLM is enabled\\.$",
                ):
                    bootstrap.initialize()

        activate_llm.assert_not_called()

    def test_enabled_config_with_a_whitespace_only_model_fails_before_activation(
        self,
    ) -> None:
        config = LLMRuntimeConfig(
            enabled=True,
            base_url="https://api.example.test/v1/chat/completions",
            model="   ",
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
                    "^LLM model is required when LLM is enabled\\.$",
                ):
                    bootstrap.initialize()

        activate_llm.assert_not_called()
