"""Stable learned-memory ranking by deterministic keyword relevance score."""

from memory.KeywordLearnedMemoryRelevance import (
    score_keyword_learned_memory_relevance,
)
from memory.LearnedMemory import LearnedMemory


class RankedKeywordLearnedMemorySelector:
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
        return tuple(
            memory
            for _, memory in sorted(
                relevant_memories,
                key=lambda scored_memory: scored_memory[0],
                reverse=True,
            )
        )
