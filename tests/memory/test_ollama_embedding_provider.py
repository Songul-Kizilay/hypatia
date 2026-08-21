from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import MemoryError
from memory.Embedding import Embedding
from memory.OllamaEmbeddingProvider import OllamaEmbeddingProvider


class OllamaEmbeddingProviderTests(unittest.TestCase):
    def test_sends_exact_source_and_returns_validated_embedding(self) -> None:
        calls: list[tuple[str, dict[str, object]]] = []

        def transport(endpoint: str, payload: dict[str, object]) -> object:
            calls.append((endpoint, payload))
            return {"embeddings": [[1, -2.5]]}

        provider = OllamaEmbeddingProvider(
            endpoint="http://localhost:11434/api/embed",
            model="embeddinggemma",
            transport=transport,
        )

        embedding = provider.embed("  Exact source  ")

        self.assertEqual(embedding, Embedding((1.0, -2.5)))
        self.assertEqual(
            calls,
            [
                (
                    "http://localhost:11434/api/embed",
                    {"model": "embeddinggemma", "input": "  Exact source  "},
                )
            ],
        )

    def test_rejects_missing_empty_multiple_or_invalid_embeddings(self) -> None:
        responses: tuple[object, ...] = (
            {},
            {"embeddings": []},
            {"embeddings": [[1], [2]]},
            {"embeddings": ["not-a-vector"]},
            {"embeddings": [[float("inf")]]},
        )

        for response in responses:
            with self.subTest(response=response):
                provider = OllamaEmbeddingProvider(
                    endpoint="http://localhost:11434/api/embed",
                    model="embeddinggemma",
                    transport=lambda *_, response=response: response,
                )
                with self.assertRaisesRegex(MemoryError, "response invalid"):
                    provider.embed("source")

    def test_wraps_transport_and_json_errors_as_memory_errors(self) -> None:
        for error in (OSError("offline"), json.JSONDecodeError("bad", "{", 0)):
            with self.subTest(error=type(error).__name__):
                provider = OllamaEmbeddingProvider(
                    endpoint="http://localhost:11434/api/embed",
                    model="embeddinggemma",
                    transport=lambda *_, error=error: (_ for _ in ()).throw(error),
                )
                expected = (
                    "transport failed"
                    if isinstance(error, OSError)
                    else "response invalid"
                )
                with self.assertRaisesRegex(MemoryError, expected):
                    provider.embed("source")

    def test_rejects_oversized_provider_vector_before_embedding_construction(
        self,
    ) -> None:
        provider = OllamaEmbeddingProvider(
            endpoint="http://localhost:11434/api/embed",
            model="embeddinggemma",
            transport=lambda *_: {"embeddings": [[1, 0, 0]]},
        )

        with (
            patch("memory.OllamaEmbeddingProvider.MAX_EMBEDDING_DIMENSION", 2),
            patch(
                "memory.OllamaEmbeddingProvider.Embedding",
                side_effect=AssertionError(
                    "Oversized provider output must not construct an Embedding."
                ),
            ),
        ):
            with self.assertRaisesRegex(MemoryError, "response invalid"):
                provider.embed("source")

    def test_source_text_bound_preserves_exact_input_and_skips_transport(self) -> None:
        calls: list[dict[str, object]] = []

        def transport(_: str, payload: dict[str, object]) -> object:
            calls.append(payload)
            return {"embeddings": [[1, 0]]}

        provider = OllamaEmbeddingProvider(
            endpoint="http://localhost:11434/api/embed",
            model="embeddinggemma",
            transport=transport,
        )

        with patch(
            "memory.EmbeddingProvider.MAX_EMBEDDING_SOURCE_TEXT_CHARACTERS",
            5,
        ):
            self.assertEqual(provider.embed("  abc"), Embedding((1, 0)))
            with self.assertRaisesRegex(MemoryError, "source text invalid"):
                provider.embed("abcdef")
            with self.assertRaisesRegex(MemoryError, "source text invalid"):
                provider.embed(123)  # type: ignore[arg-type]

        self.assertEqual(
            calls,
            [{"model": "embeddinggemma", "input": "  abc"}],
        )


if __name__ == "__main__":
    unittest.main()
