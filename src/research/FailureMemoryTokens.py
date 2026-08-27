"""Shared, deliberately conservative tokenization for Failure Memory recall.

Long prose words remain the default signal. Short words are kept only when
they are not closed-list function or medium names, or when their punctuation
already marks them as a technical identifier. This preserves security terms
such as ``XSS``, ``SQL``, ``C++``, and ``C#`` without letting ``the`` or ``web``
manufacture relevance.
"""

from __future__ import annotations

from research.ResearchQueryTerms import (
    COMMON_ACRONYMS,
    STOP_WORDS,
    is_technical_term,
)

_EDGE_PUNCTUATION = ".,;:()[]{}<>\"'?!`*_"
_MIN_TOKEN_LENGTH = 4
_MIN_SHORT_TOKEN_LENGTH = 3


def failure_memory_tokens(value: str) -> frozenset[str]:
    """Return bounded recall tokens while keeping short technical vocabulary."""
    if not isinstance(value, str):
        return frozenset()
    tokens: set[str] = set()
    for word in value.casefold().split():
        token = word.strip(_EDGE_PUNCTUATION)
        if not token:
            continue
        if (
            len(token) >= _MIN_TOKEN_LENGTH
            or is_technical_term(token)
            or (
                len(token) >= _MIN_SHORT_TOKEN_LENGTH
                and token not in STOP_WORDS
                and token not in COMMON_ACRONYMS
            )
        ):
            tokens.add(token)
    return frozenset(tokens)
