from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from llm.LLMProvider import LLMProvider
from llm.LLMProviderFactory import create_llm_provider
from llm.OpenAICompatibleProvider import OpenAICompatibleProvider
from llm.UrllibChatCompletionTransport import UrllibChatCompletionTransport


class LLMProviderFactoryTests(unittest.TestCase):
    def test_factory_composes_the_default_provider_without_generating(self) -> None:
        provider: LLMProvider = create_llm_provider(
            base_url="https://api.example.test/v1/chat/completions",
            api_key="test-api-key",
            model="test-model",
        )

        self.assertIsInstance(provider, OpenAICompatibleProvider)
        self.assertIsInstance(provider._transport, UrllibChatCompletionTransport)
        self.assertEqual(
            provider._base_url, "https://api.example.test/v1/chat/completions"
        )
        self.assertEqual(provider._api_key, "test-api-key")
        self.assertEqual(provider._model, "test-model")
