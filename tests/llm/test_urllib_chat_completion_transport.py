from __future__ import annotations

import json
import sys
import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from llm.UrllibChatCompletionTransport import (
    DEFAULT_TIMEOUT_SECONDS,
    UrllibChatCompletionTransport,
    _NoRedirectHandler,
)


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
        timeouts: list[float] = []

        def fake_open(request: Request, *, timeout: float) -> FakeResponse:
            requests.append(request)
            timeouts.append(timeout)
            return FakeResponse()

        transport = UrllibChatCompletionTransport()

        with patch(
            "llm.UrllibChatCompletionTransport._open_without_redirects",
            side_effect=fake_open,
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
        self.assertEqual(timeouts, [DEFAULT_TIMEOUT_SECONDS])
        request = requests[0]
        self.assertEqual(
            request.full_url, "https://api.example.test/v1/chat/completions"
        )
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-api-key")
        assert isinstance(request.data, bytes)
        self.assertEqual(
            json.loads(request.data.decode("utf-8")),
            {
                "model": "test-model",
                "messages": [{"role": "user", "content": "Tell me something."}],
            },
        )

    def test_redirect_handler_never_follows_an_authenticated_redirect(self) -> None:
        request = Request(
            "https://api.example.test/v1/chat/completions",
            headers={"Authorization": "Bearer test-api-key"},
            method="POST",
        )

        redirected_request = _NoRedirectHandler().redirect_request(
            request,
            object(),
            302,
            "Found",
            Message(),
            "https://other.example.test/collect",
        )

        self.assertIsNone(redirected_request)
