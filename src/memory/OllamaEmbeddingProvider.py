"""Local Ollama adapter for the semantic embedding-provider boundary."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import cast

from core.Exceptions import MemoryError
from memory.Embedding import MAX_EMBEDDING_DIMENSION, Embedding

OllamaEmbeddingTransport = Callable[[str, dict[str, object]], object]


class OllamaEmbeddingProvider:
    """Generate one embedding through an explicitly configured Ollama endpoint."""

    def __init__(
        self,
        endpoint: str,
        model: str,
        transport: OllamaEmbeddingTransport,
    ) -> None:
        self._endpoint = endpoint
        self._model = model
        self._transport = transport

    def embed(self, source_text: str) -> Embedding:
        """Request exactly one embedding for the exact supplied source text."""
        try:
            response = self._transport(
                self._endpoint,
                {"model": self._model, "input": source_text},
            )
        except OSError as error:
            raise MemoryError("Embedding transport failed.") from error
        except json.JSONDecodeError as error:
            raise MemoryError("Embedding response invalid.") from error
        return _extract_single_embedding(response)


def _extract_single_embedding(response: object) -> Embedding:
    try:
        embeddings = cast(dict[str, object], response)["embeddings"]
        raw_embedding = cast(list[object], embeddings)[0]
    except (KeyError, IndexError, TypeError) as error:
        raise MemoryError("Embedding response invalid.") from error
    if not isinstance(embeddings, list) or len(embeddings) != 1:
        raise MemoryError("Embedding response invalid.")
    if not isinstance(raw_embedding, list):
        raise MemoryError("Embedding response invalid.")
    if len(raw_embedding) > MAX_EMBEDDING_DIMENSION:
        raise MemoryError("Embedding response invalid.")

    try:
        return Embedding(cast(tuple[float, ...], tuple(raw_embedding)))
    except ValueError as error:
        raise MemoryError("Embedding response invalid.") from error
