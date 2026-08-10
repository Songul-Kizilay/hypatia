from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from llm.UrllibChatCompletionTransport import UrllibChatCompletionTransport


class FakeResponse:
    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return b'{"choices": [{"message": {"content": "Generated answer."}}]}'


class UrllibChatCompletionTransportTests(unittest.TestCase):
    def test_transport_posts_a_json_request_without_using_the_network(self) -> None:
        requests: list[Request] = []

        def fake_urlopen(request: Request) -> FakeResponse:
            requests.append(request)
            return FakeResponse()

        transport = UrllibChatCompletionTransport()

        with patch(
            "llm.UrllibChatCompletionTransport.urlopen",
            side_effect=fake_urlopen,
        ):
            response = transport(
                "https://api.example.test/v1/chat/completions",
                {"Authorization": "Bearer test-api-key"},
                {
                    "model": "test-model",
                    "messages": [{"role": "user", "content": "Tell me something."}],
                },
            )

        self.assertEqual(
            response,
            {"choices": [{"message": {"content": "Generated answer."}}]},
        )
        self.assertEqual(len(requests), 1)
        request = requests[0]
        self.assertEqual(
            request.full_url, "https://api.example.test/v1/chat/completions"
        )
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-api-key")
        self.assertEqual(
            json.loads(request.data.decode("utf-8")),
            {
                "model": "test-model",
                "messages": [{"role": "user", "content": "Tell me something."}],
            },
        )
