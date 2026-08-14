"""Pure deterministic keyword learned-memory relevance scoring."""

import re

from memory.LearnedMemory import LearnedMemory

_ALPHANUMERIC_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)


def _tokens(text: str) -> frozenset[str]:
    return frozenset(token.casefold() for token in _ALPHANUMERIC_TOKEN.findall(text))


def score_keyword_learned_memory_relevance(
    *,
    source_text: str,
    memory: LearnedMemory,
) -> int:
    source_tokens = _tokens(source_text)
    memory_tokens = _tokens(memory.key) | _tokens(memory.value)
    return len(source_tokens & memory_tokens)
