"""Provider boundary for embedding plain text without choosing a model."""

from __future__ import annotations

from typing import Protocol

from memory.Embedding import Embedding


class EmbeddingProvider(Protocol):
    """Turn source text into a validated embedding value."""

    def embed(self, source_text: str) -> Embedding:
        """Return one embedding for the exact supplied source text."""
