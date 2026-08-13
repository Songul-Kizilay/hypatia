"""Structural boundary for request-specific learned-memory selection."""

from typing import Protocol

from memory.LearnedMemory import LearnedMemory


class LearnedMemorySelector(Protocol):
    def select(
        self,
        *,
        source_text: str,
        memories: tuple[LearnedMemory, ...],
    ) -> tuple[LearnedMemory, ...]: ...
