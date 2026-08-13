"""Thin service for append-only learned-memory corrections."""

from memory.LearnedMemory import LearnedMemory, LearnedMemoryKind
from memory.LearnedMemoryStore import correct_learned_memory
from memory.MemoryManager import MemoryManager
from memory.MemoryRecord import MemoryRecord


def correct_learned_memory_value(
    memory_manager: MemoryManager,
    *,
    kind: LearnedMemoryKind,
    key: str,
    value: str,
) -> MemoryRecord:
    memory = LearnedMemory(kind=kind, key=key, value=value)
    return correct_learned_memory(memory_manager, memory)
