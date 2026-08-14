from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import cast

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from llm.LLMConversationMessage import LLMConversationMessage
from llm.LLMProvider import LLMError
from llm.OpenAICompatibleProvider import (
    ChatCompletionResponse,
    OpenAICompatibleProvider,
)


class RecordingTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str], dict[str, object]]] = []

    def __call__(
        self,
        base_url: str,
        headers: dict[str, str],
        payload: dict[str, object],
    ) -> dict[str, list[dict[str, dict[str, str]]]]:
        self.calls.append((base_url, headers, payload))
        return {"choices": [{"message": {"content": "Generated answer."}}]}


class FailingTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str], dict[str, object]]] = []

    def __call__(
        self,
        base_url: str,
        headers: dict[str, str],
        payload: dict[str, object],
    ) -> dict[str, list[dict[str, dict[str, str]]]]:
        self.calls.append((base_url, headers, payload))
        raise OSError("Connection refused.")


class MissingChoicesTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str], dict[str, object]]] = []

    def __call__(
        self,
        base_url: str,
        headers: dict[str, str],
        payload: dict[str, object],
    ) -> ChatCompletionResponse:
        self.calls.append((base_url, headers, payload))
        return cast(ChatCompletionResponse, {})


class EmptyChoicesTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str], dict[str, object]]] = []

    def __call__(
        self,
        base_url: str,
        headers: dict[str, str],
        payload: dict[str, object],
    ) -> ChatCompletionResponse:
        self.calls.append((base_url, headers, payload))
        return cast(ChatCompletionResponse, {"choices": []})


class MalformedJsonTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str], dict[str, object]]] = []

    def __call__(
        self, base_url: str, headers: dict[str, str], payload: dict[str, object]
    ) -> ChatCompletionResponse:
        self.calls.append((base_url, headers, payload))
        raise json.JSONDecodeError("Expecting value", "not-json", 0)


class StaticResponseTransport:
    def __init__(self, response: object) -> None:
        self.calls: list[tuple[str, dict[str, str], dict[str, object]]] = []
        self._response = response

    def __call__(
        self,
        base_url: str,
        headers: dict[str, str],
        payload: dict[str, object],
    ) -> object:
        self.calls.append((base_url, headers, payload))
        return self._response


class OpenAICompatibleProviderTests(unittest.TestCase):
    def test_generate_normalizes_malformed_or_non_string_response_shapes(
        self,
    ) -> None:
        invalid_responses = (
            {"choices": None},
            {"choices": ["invalid"]},
            {"choices": [{"message": None}]},
            {"choices": [{"message": {"content": None}}]},
            {"choices": [{"message": {"content": 123}}]},
        )

        for response in invalid_responses:
            with self.subTest(response=response):
                transport = StaticResponseTransport(response)
                provider = OpenAICompatibleProvider(
                    base_url="https://api.example.test/v1",
                    api_key="test-api-key",
                    model="test-model",
                    transport=transport,
                )

                with self.assertRaises(LLMError) as context:
                    provider.generate("Tell me something.")

                self.assertEqual(str(context.exception), "LLM response invalid.")
                self.assertEqual(len(transport.calls), 1)

    def test_generate_preserves_whitespace_in_string_content(self) -> None:
        transport = StaticResponseTransport(
            {"choices": [{"message": {"content": "  answer  "}}]}
        )
        provider = OpenAICompatibleProvider(
            base_url="https://api.example.test/v1",
            api_key="test-api-key",
            model="test-model",
            transport=transport,
        )

        response = provider.generate("Tell me something.")

        self.assertEqual(response, "  answer  ")
        self.assertEqual(len(transport.calls), 1)

    def test_generate_sends_system_history_and_current_user_in_order(self) -> None:
        transport = RecordingTransport()
        provider = OpenAICompatibleProvider(
            base_url="https://api.example.test/v1",
            api_key="test-api-key",
            model="test-model",
            transport=transport,
            system_prompt="You are Hypatia.",
        )
        history = (
            LLMConversationMessage(role="user", content="My name is Songül."),
            LLMConversationMessage(
                role="assistant",
                content="Nice to meet you.",
            ),
        )

        provider.generate("What is my name?", history=history)

        self.assertEqual(
            transport.calls,
            [
                (
                    "https://api.example.test/v1",
                    {"Authorization": "Bearer test-api-key"},
                    {
                        "model": "test-model",
                        "messages": [
                            {"role": "system", "content": "You are Hypatia."},
                            {"role": "user", "content": "My name is Songül."},
                            {
                                "role": "assistant",
                                "content": "Nice to meet you.",
                            },
                            {"role": "user", "content": "What is my name?"},
                        ],
                    },
                )
            ],
        )

    def test_generate_preserves_turkish_and_english_user_prompts(self) -> None:
        transport = RecordingTransport()
        provider = OpenAICompatibleProvider(
            base_url="https://api.example.test/v1",
            api_key="test-api-key",
            model="test-model",
            transport=transport,
        )
        turkish_prompt = "Merhaba Hypatia, bugün nasılsın?"
        english_prompt = "Hello Hypatia, how are you today?"

        provider.generate(turkish_prompt)
        provider.generate(english_prompt)

        self.assertEqual(
            [call[2]["messages"] for call in transport.calls],
            [
                [{"role": "user", "content": turkish_prompt}],
                [{"role": "user", "content": english_prompt}],
            ],
        )

    def test_generate_sends_a_system_message_before_the_user_message(self) -> None:
        transport = RecordingTransport()
        provider = OpenAICompatibleProvider(
            base_url="https://api.example.test/v1",
            api_key="test-api-key",
            model="test-model",
            transport=transport,
            system_prompt="You are Hypatia.",
        )

        provider.generate("Tell me something.")

        self.assertEqual(
            transport.calls,
            [
                (
                    "https://api.example.test/v1",
                    {"Authorization": "Bearer test-api-key"},
                    {
                        "model": "test-model",
                        "messages": [
                            {"role": "system", "content": "You are Hypatia."},
                            {"role": "user", "content": "Tell me something."},
                        ],
                    },
                )
            ],
        )

    def test_generate_omits_authorization_for_an_intentionally_keyless_provider(
        self,
    ) -> None:
        transport = RecordingTransport()
        provider = OpenAICompatibleProvider(
            base_url="http://localhost:11434/v1/chat/completions",
            api_key=None,
            model="local-model",
            transport=transport,
        )

        provider.generate("Merhaba Hypatia")

        self.assertEqual(
            transport.calls,
            [
                (
                    "http://localhost:11434/v1/chat/completions",
                    {},
                    {
                        "model": "local-model",
                        "messages": [{"role": "user", "content": "Merhaba Hypatia"}],
                    },
                )
            ],
        )

    def test_generate_normalizes_a_json_decode_error(self) -> None:
        transport = MalformedJsonTransport()
        provider = OpenAICompatibleProvider(
            "https://api.example.test/v1", "test-api-key", "test-model", transport
        )
        with self.assertRaises(LLMError) as context:
            provider.generate("Tell me something.")
        self.assertEqual(str(context.exception), "LLM response invalid.")
        self.assertIsInstance(context.exception.__cause__, json.JSONDecodeError)
        self.assertEqual(
            transport.calls,
            [
                (
                    "https://api.example.test/v1",
                    {"Authorization": "Bearer test-api-key"},
                    {
                        "model": "test-model",
                        "messages": [{"role": "user", "content": "Tell me something."}],
                    },
                )
            ],
        )

    def test_generate_normalizes_an_empty_choices_response(self) -> None:
        transport = EmptyChoicesTransport()
        provider = OpenAICompatibleProvider(
            base_url="https://api.example.test/v1",
            api_key="test-api-key",
            model="test-model",
            transport=transport,
        )

        with self.assertRaises(LLMError) as context:
            provider.generate("Tell me something.")

        self.assertEqual(str(context.exception), "LLM response invalid.")
        self.assertIsInstance(context.exception.__cause__, IndexError)
        self.assertEqual(
            transport.calls,
            [
                (
                    "https://api.example.test/v1",
                    {"Authorization": "Bearer test-api-key"},
                    {
                        "model": "test-model",
                        "messages": [{"role": "user", "content": "Tell me something."}],
                    },
                )
            ],
        )

    def test_generate_normalizes_a_missing_choices_response(self) -> None:
        transport = MissingChoicesTransport()
        provider = OpenAICompatibleProvider(
            base_url="https://api.example.test/v1",
            api_key="test-api-key",
            model="test-model",
            transport=transport,
        )

        with self.assertRaises(LLMError) as context:
            provider.generate("Tell me something.")

        self.assertEqual(str(context.exception), "LLM response invalid.")
        self.assertIsInstance(context.exception.__cause__, KeyError)
        self.assertEqual(
            transport.calls,
            [
                (
                    "https://api.example.test/v1",
                    {"Authorization": "Bearer test-api-key"},
                    {
                        "model": "test-model",
                        "messages": [{"role": "user", "content": "Tell me something."}],
                    },
                )
            ],
        )

    def test_generate_normalizes_an_os_error_from_the_transport(self) -> None:
        transport = FailingTransport()
        provider = OpenAICompatibleProvider(
            base_url="https://api.example.test/v1",
            api_key="test-api-key",
            model="test-model",
            transport=transport,
        )

        with self.assertRaises(LLMError) as context:
            provider.generate("Tell me something.")

        self.assertEqual(str(context.exception), "LLM transport failed.")
        self.assertIsInstance(context.exception.__cause__, OSError)
        self.assertEqual(str(context.exception.__cause__), "Connection refused.")
        self.assertEqual(
            transport.calls,
            [
                (
                    "https://api.example.test/v1",
                    {"Authorization": "Bearer test-api-key"},
                    {
                        "model": "test-model",
                        "messages": [{"role": "user", "content": "Tell me something."}],
                    },
                )
            ],
        )

    def test_generate_sends_one_openai_compatible_request_to_the_transport(
        self,
    ) -> None:
        transport = RecordingTransport()
        provider = OpenAICompatibleProvider(
            base_url="https://api.example.test/v1",
            api_key="test-api-key",
            model="test-model",
            transport=transport,
        )

        response = provider.generate("Tell me something.")

        self.assertEqual(response, "Generated answer.")
        self.assertEqual(
            transport.calls,
            [
                (
                    "https://api.example.test/v1",
                    {"Authorization": "Bearer test-api-key"},
                    {
                        "model": "test-model",
                        "messages": [{"role": "user", "content": "Tell me something."}],
                    },
                )
            ],
        )
