"""Shared, deliberately conservative tokenization for Failure Memory recall.

Closed-list function words and medium names are excluded at every length.
Other words are kept from three characters, or when their punctuation already
marks them as a technical identifier. This preserves security terms
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
_MIN_SHORT_TOKEN_LENGTH = 3


def failure_memory_tokens(value: str) -> frozenset[str]:
    """Return bounded recall tokens while keeping short technical vocabulary."""
    if not isinstance(value, str):
        return frozenset()
    tokens: set[str] = set()
    for word in value.casefold().split():
        token = word.strip(_EDGE_PUNCTUATION)
        if not token or token in STOP_WORDS or token in COMMON_ACRONYMS:
            continue
        if len(token) >= _MIN_SHORT_TOKEN_LENGTH or is_technical_term(token):
            tokens.add(token)
    return frozenset(tokens)
