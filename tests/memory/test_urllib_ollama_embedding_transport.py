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

from memory.UrllibOllamaEmbeddingTransport import (
    DEFAULT_TIMEOUT_SECONDS,
    UrllibOllamaEmbeddingTransport,
)


class FakeResponse:
    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return b'{"embeddings": [[0.25, -0.5]]}'


class UrllibOllamaEmbeddingTransportTests(unittest.TestCase):
    def test_posts_single_embedding_payload_without_using_the_network(self) -> None:
        requests: list[Request] = []
        timeouts: list[float] = []

        def fake_urlopen(request: Request, timeout: float) -> FakeResponse:
            requests.append(request)
            timeouts.append(timeout)
            return FakeResponse()

        transport = UrllibOllamaEmbeddingTransport()

        with patch(
            "memory.UrllibOllamaEmbeddingTransport.urlopen",
            side_effect=fake_urlopen,
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

        def fake_urlopen(request: Request, timeout: float) -> FakeResponse:
            timeouts.append(timeout)
            return FakeResponse()

        transport = UrllibOllamaEmbeddingTransport(timeout_seconds=7.5)

        with patch(
            "memory.UrllibOllamaEmbeddingTransport.urlopen",
            side_effect=fake_urlopen,
        ):
            transport(
                "http://localhost:11434/api/embed",
                {"model": "embeddinggemma", "input": "Exact source"},
            )

        self.assertEqual(timeouts, [7.5])

    def test_rejects_invalid_timeouts(self) -> None:
        for timeout in (True, 0, -1, float("inf"), "30"):
            with self.subTest(timeout=timeout):
                with self.assertRaisesRegex(ValueError, "positive number"):
                    UrllibOllamaEmbeddingTransport(timeout_seconds=timeout)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
