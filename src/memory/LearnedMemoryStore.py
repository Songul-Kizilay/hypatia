"""Read-only MemoryManager seam for learned memories."""

from memory.LearnedMemory import LearnedMemory, LearnedMemoryKind
from memory.LearnedMemoryRetrieval import (
    collect_learned_memories,
    resolve_latest_learned_memory,
)
from memory.MemoryManager import MemoryManager


def load_learned_memories(
    memory_manager: MemoryManager,
) -> tuple[LearnedMemory, ...]:
    records = tuple(memory_manager.all())
    return collect_learned_memories(records)


def load_latest_learned_memory(
    memory_manager: MemoryManager,
    *,
    kind: LearnedMemoryKind,
    key: str,
) -> LearnedMemory | None:
    memories = load_learned_memories(memory_manager)
    return resolve_latest_learned_memory(memories, kind=kind, key=key)
