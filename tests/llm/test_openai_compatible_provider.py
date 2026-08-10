from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from llm.LLMProvider import LLMError
from llm.OpenAICompatibleProvider import OpenAICompatibleProvider


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


class OpenAICompatibleProviderTests(unittest.TestCase):
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
