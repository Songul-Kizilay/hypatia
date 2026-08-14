"""Stable learned-memory ranking by deterministic keyword relevance score."""

from memory.KeywordLearnedMemoryRelevance import (
    score_keyword_learned_memory_relevance,
)
from memory.LearnedMemory import LearnedMemory


class RankedKeywordLearnedMemorySelector:
    def __init__(self, limit: int | None = None) -> None:
        if limit is not None and limit < 0:
            raise ValueError(
                "Ranked keyword learned memory selector limit must be non-negative."
            )
        self._limit = limit

    def select(
        self,
        *,
        source_text: str,
        memories: tuple[LearnedMemory, ...],
    ) -> tuple[LearnedMemory, ...]:
        scored_memories = tuple(
            (
                score_keyword_learned_memory_relevance(
                    source_text=source_text,
                    memory=memory,
                ),
                memory,
            )
            for memory in memories
        )
        relevant_memories = (
            scored_memory for scored_memory in scored_memories if scored_memory[0] > 0
        )
        ranked_memories = tuple(
            memory
            for _, memory in sorted(
                relevant_memories,
                key=lambda scored_memory: scored_memory[0],
                reverse=True,
            )
        )
        if self._limit is None:
            return ranked_memories
        return ranked_memories[: self._limit]
