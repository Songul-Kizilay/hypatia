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
        self.assertEqual(
            request.data,
            b'{"model":"embeddinggemma","input":"Exact source"}',
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

    def test_call_timeout_can_only_shorten_the_configured_timeout(self) -> None:
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
                {"model": "embeddinggemma", "input": "first"},
                timeout_seconds=2.5,
            )
            transport(
                "http://localhost:11434/api/embed",
                {"model": "embeddinggemma", "input": "second"},
                timeout_seconds=10,
            )

        self.assertEqual(timeouts, [2.5, 7.5])

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

    def test_exact_utf8_request_bound_and_invalid_payload_skip_network(self) -> None:
        transport = UrllibOllamaEmbeddingTransport()
        payload: dict[str, object] = {"model": "model", "input": "Türkçe"}
        expected_body = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        requests: list[Request] = []

        def fake_open(request: Request, **_: object) -> FakeResponse:
            requests.append(request)
            return FakeResponse()

        with (
            patch(
                "memory.UrllibOllamaEmbeddingTransport.MAX_REQUEST_BYTES",
                len(expected_body),
            ),
            patch(
                "memory.UrllibOllamaEmbeddingTransport._open_without_redirects",
                side_effect=fake_open,
            ),
        ):
            transport("http://localhost:11434/api/embed", payload)

        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].data, expected_body)

        with (
            patch(
                "memory.UrllibOllamaEmbeddingTransport.MAX_REQUEST_BYTES",
                len(expected_body) - 1,
            ),
            patch(
                "memory.UrllibOllamaEmbeddingTransport._open_without_redirects",
                side_effect=AssertionError("Oversized requests must not be sent."),
            ),
        ):
            with self.assertRaisesRegex(OSError, "maximum allowed size"):
                transport("http://localhost:11434/api/embed", payload)

        recursive_payload: dict[str, object] = {}
        recursive_payload["self"] = recursive_payload
        invalid_payloads: tuple[dict[str, object], ...] = (
            recursive_payload,
            {"input": object()},
            {"input": float("nan")},
        )
        with patch(
            "memory.UrllibOllamaEmbeddingTransport._open_without_redirects",
            side_effect=AssertionError("Invalid requests must not be sent."),
        ):
            for invalid_payload in invalid_payloads:
                with self.subTest(payload=invalid_payload):
                    with self.assertRaisesRegex(OSError, "payload is invalid"):
                        transport(
                            "http://localhost:11434/api/embed",
                            invalid_payload,
                        )

    def test_rejects_invalid_timeouts(self) -> None:
        for timeout in (True, 0, -1, float("inf"), "30"):
            with self.subTest(timeout=timeout):
                with self.assertRaisesRegex(ValueError, "positive number"):
                    UrllibOllamaEmbeddingTransport(timeout_seconds=timeout)  # type: ignore[arg-type]

        transport = UrllibOllamaEmbeddingTransport()
        with patch(
            "memory.UrllibOllamaEmbeddingTransport._open_without_redirects",
            side_effect=AssertionError("Invalid timeout must skip network."),
        ):
            for timeout in (True, 0, -1, float("inf"), "30"):
                with self.subTest(call_timeout=timeout):
                    with self.assertRaisesRegex(ValueError, "positive number"):
                        transport(
                            "http://localhost:11434/api/embed",
                            {"model": "embeddinggemma", "input": "source"},
                            timeout_seconds=timeout,  # type: ignore[arg-type]
                        )


if __name__ == "__main__":
    unittest.main()
