"""Provider boundary for embedding plain text without choosing a model."""

from __future__ import annotations

from typing import Protocol

from memory.Embedding import Embedding

MAX_EMBEDDING_SOURCE_TEXT_CHARACTERS = 1_000_000


def validate_embedding_source_text(source_text: object) -> None:
    """Preserve exact text while rejecting invalid or excessive provider input."""
    if not isinstance(source_text, str):
        raise ValueError("Embedding source text must be a string.")
    if len(source_text) > MAX_EMBEDDING_SOURCE_TEXT_CHARACTERS:
        raise ValueError("Embedding source text is too long.")


class EmbeddingProvider(Protocol):
    """Turn source text into a validated embedding value."""

    def embed(self, source_text: str) -> Embedding:
        """Return one embedding for the exact supplied source text."""
