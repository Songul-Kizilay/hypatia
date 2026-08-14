from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import cast

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from llm.LLMProviderFactory import create_llm_provider
from llm.OpenAICompatibleProvider import OpenAICompatibleProvider
from llm.UrllibChatCompletionTransport import UrllibChatCompletionTransport


class LLMProviderFactoryTests(unittest.TestCase):
    def test_factory_composes_the_default_provider_without_generating(self) -> None:
        provider = cast(
            OpenAICompatibleProvider,
            create_llm_provider(
                base_url="https://api.example.test/v1/chat/completions",
                api_key="test-api-key",
                model="test-model",
            ),
        )

        self.assertIsInstance(provider, OpenAICompatibleProvider)
        self.assertIsInstance(provider._transport, UrllibChatCompletionTransport)
        self.assertEqual(
            provider._base_url, "https://api.example.test/v1/chat/completions"
        )
        self.assertEqual(provider._api_key, "test-api-key")
        self.assertEqual(provider._model, "test-model")
        self.assertIsNone(provider._system_prompt)
        transport = cast(UrllibChatCompletionTransport, provider._transport)
        self.assertEqual(transport._timeout_seconds, 30.0)

    def test_factory_forwards_an_optional_system_prompt(self) -> None:
        provider = cast(
            OpenAICompatibleProvider,
            create_llm_provider(
                base_url="https://api.example.test/v1/chat/completions",
                api_key="test-api-key",
                model="test-model",
                system_prompt="You are Hypatia.",
            ),
        )

        self.assertIsInstance(provider, OpenAICompatibleProvider)
        self.assertEqual(provider._system_prompt, "You are Hypatia.")

    def test_factory_forwards_an_explicit_timeout_to_the_transport(self) -> None:
        provider = cast(
            OpenAICompatibleProvider,
            create_llm_provider(
                base_url="https://api.example.test/v1/chat/completions",
                api_key="test-api-key",
                model="test-model",
                timeout_seconds=7.5,
            ),
        )

        transport = cast(UrllibChatCompletionTransport, provider._transport)
        self.assertIsInstance(transport, UrllibChatCompletionTransport)
        self.assertEqual(transport._timeout_seconds, 7.5)
