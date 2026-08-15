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

from memory.UrllibOllamaEmbeddingTransport import (
    DEFAULT_TIMEOUT_SECONDS,
    MAX_RESPONSE_BYTES,
    UrllibOllamaEmbeddingTransport,
    _NoRedirectHandler,
)


class FakeResponse:
    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        return b'{"embeddings": [[0.25, -0.5]]}'


class OversizedFakeResponse(FakeResponse):
    def read(self, size: int = -1) -> bytes:
        return b"x" * (MAX_RESPONSE_BYTES + 1)


class UrllibOllamaEmbeddingTransportTests(unittest.TestCase):
    def test_posts_single_embedding_payload_without_using_the_network(self) -> None:
        requests: list[Request] = []
        timeouts: list[float] = []

        def fake_open(request: Request, *, timeout: float) -> FakeResponse:
            requests.append(request)
            timeouts.append(timeout)
            return FakeResponse()

        transport = UrllibOllamaEmbeddingTransport()

        with patch(
            "memory.UrllibOllamaEmbeddingTransport._open_without_redirects",
            side_effect=fake_open,
        ):
            response = transport(
                "http://localhost:11434/api/embed",
                {"model": "embeddinggemma", "input": "Exact source"},
            )

        self.assertEqual(response, {"embeddings": [[0.25, -0.5]]})
        self.assertEqual(timeouts, [DEFAULT_TIMEOUT_SECONDS])
        self.assertEqual(len(requests), 1)
        request = requests[0]
        self.assertEqual(request.full_url, "http://localhost:11434/api/embed")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Content-type"), "application/json")
        assert isinstance(request.data, bytes)
        self.assertEqual(
            json.loads(request.data.decode("utf-8")),
            {"model": "embeddinggemma", "input": "Exact source"},
        )

    def test_uses_a_valid_explicit_timeout(self) -> None:
        timeouts: list[float] = []

        def fake_open(request: Request, *, timeout: float) -> FakeResponse:
            timeouts.append(timeout)
            return FakeResponse()

        transport = UrllibOllamaEmbeddingTransport(timeout_seconds=7.5)

        with patch(
            "memory.UrllibOllamaEmbeddingTransport._open_without_redirects",
            side_effect=fake_open,
        ):
            transport(
                "http://localhost:11434/api/embed",
                {"model": "embeddinggemma", "input": "Exact source"},
            )

        self.assertEqual(timeouts, [7.5])

    def test_redirect_handler_never_follows_a_local_embedding_redirect(self) -> None:
        request = Request(
            "http://localhost:11434/api/embed",
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

    def test_rejects_an_oversized_embedding_response_before_json_parsing(self) -> None:
        transport = UrllibOllamaEmbeddingTransport()

        with patch(
            "memory.UrllibOllamaEmbeddingTransport._open_without_redirects",
            return_value=OversizedFakeResponse(),
        ):
            with self.assertRaisesRegex(
                OSError,
                "Embedding response exceeds the maximum allowed size.",
            ):
                transport(
                    "http://localhost:11434/api/embed",
                    {"model": "embeddinggemma", "input": "Exact source"},
                )

    def test_rejects_invalid_timeouts(self) -> None:
        for timeout in (True, 0, -1, float("inf"), "30"):
            with self.subTest(timeout=timeout):
                with self.assertRaisesRegex(ValueError, "positive number"):
                    UrllibOllamaEmbeddingTransport(timeout_seconds=timeout)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
