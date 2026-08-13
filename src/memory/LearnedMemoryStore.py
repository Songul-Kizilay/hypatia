"""Read-only MemoryManager seam for learned memories."""

from memory.LearnedMemory import LearnedMemory
from memory.LearnedMemoryRetrieval import collect_learned_memories
from memory.MemoryManager import MemoryManager


def load_learned_memories(
    memory_manager: MemoryManager,
) -> tuple[LearnedMemory, ...]:
    records = tuple(memory_manager.all())
    return collect_learned_memories(records)
