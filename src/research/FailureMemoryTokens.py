"""Shared, deliberately simple tokenization for Failure Memory recall."""

from __future__ import annotations

_EDGE_PUNCTUATION = ".,;:()[]{}<>\"'?!`*_"
_MIN_TOKEN_LENGTH = 4


def failure_memory_tokens(value: str) -> frozenset[str]:
    """Return bounded lexical tokens with consistent edge punctuation handling."""
    if not isinstance(value, str):
        return frozenset()
    tokens: set[str] = set()
    for word in value.casefold().split():
        token = word.strip(_EDGE_PUNCTUATION)
        if len(token) >= _MIN_TOKEN_LENGTH:
            tokens.add(token)
    return frozenset(tokens)
