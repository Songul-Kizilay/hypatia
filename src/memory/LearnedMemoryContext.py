"""Deterministic LLM-readable representation of learned memories."""

from memory.LearnedMemory import LearnedMemory
from memory.LearnedMemoryStore import load_learned_memories
from memory.MemoryManager import MemoryManager


def build_learned_memory_context(
    memories: tuple[LearnedMemory, ...],
) -> str:
    if not memories:
        return ""

    lines = (
        "Known learned memories:",
        *(f"- {memory.kind} | {memory.key} | {memory.value}" for memory in memories),
    )
    return "\n".join(lines)


def load_learned_memory_context(memory_manager: MemoryManager) -> str:
    memories = load_learned_memories(memory_manager)
    return build_learned_memory_context(memories)
