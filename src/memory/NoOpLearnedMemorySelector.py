"""Pass-through learned-memory selector with no selection policy."""

from memory.LearnedMemory import LearnedMemory


class NoOpLearnedMemorySelector:
    def select(
        self,
        *,
        source_text: str,
        memories: tuple[LearnedMemory, ...],
    ) -> tuple[LearnedMemory, ...]:
        return memories
