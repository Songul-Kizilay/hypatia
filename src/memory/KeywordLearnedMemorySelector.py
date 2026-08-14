"""Deterministic key-or-value-token learned-memory relevance selection."""

import re

from memory.LearnedMemory import LearnedMemory

_ALPHANUMERIC_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)


def _tokens(text: str) -> frozenset[str]:
    return frozenset(token.casefold() for token in _ALPHANUMERIC_TOKEN.findall(text))


class KeywordLearnedMemorySelector:
    def select(
        self,
        *,
        source_text: str,
        memories: tuple[LearnedMemory, ...],
    ) -> tuple[LearnedMemory, ...]:
        source_tokens = _tokens(source_text)
        return tuple(
            memory
            for memory in memories
            if source_tokens.intersection(_tokens(memory.key) | _tokens(memory.value))
        )
