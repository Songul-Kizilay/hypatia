"""Local Ollama adapter for the semantic embedding-provider boundary."""

from __future__ import annotations

import json
from math import isfinite
from typing import Protocol, cast

from core.Exceptions import MemoryError
from memory.Embedding import MAX_EMBEDDING_DIMENSION, Embedding
from memory.EmbeddingProvider import validate_embedding_source_text


class OllamaEmbeddingTransport(Protocol):
    """Transport one request with an optional stricter call timeout."""

    def __call__(
        self,
        endpoint: str,
        payload: dict[str, object],
        *,
        timeout_seconds: float | None = None,
    ) -> object: ...


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

    def embed(
        self,
        source_text: str,
        *,
        timeout_seconds: float | None = None,
    ) -> Embedding:
        """Request exactly one embedding for the exact supplied source text."""
        try:
            validate_embedding_source_text(source_text)
        except ValueError as error:
            raise MemoryError("Embedding source text invalid.") from error
        if timeout_seconds is not None and (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            raise MemoryError("Embedding timeout invalid.")
        payload: dict[str, object] = {
            "model": self._model,
            "input": source_text,
        }
        try:
            if timeout_seconds is None:
                response = self._transport(self._endpoint, payload)
            else:
                response = self._transport(
                    self._endpoint,
                    payload,
                    timeout_seconds=float(timeout_seconds),
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
