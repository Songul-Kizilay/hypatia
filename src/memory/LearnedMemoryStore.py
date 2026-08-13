"""MemoryManager store seams for learned memories."""

from memory.LearnedMemory import LearnedMemory, LearnedMemoryKind
from memory.LearnedMemoryPersistence import persist_learned_memory
from memory.LearnedMemoryRetrieval import (
    collect_learned_memories,
    resolve_latest_learned_memory,
)
from memory.MemoryManager import MemoryManager
from memory.MemoryRecord import MemoryRecord


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


def append_learned_memory(
    memory_manager: MemoryManager,
    memory: LearnedMemory,
) -> MemoryRecord:
    return persist_learned_memory(memory_manager, memory)


def correct_learned_memory(
    memory_manager: MemoryManager,
    memory: LearnedMemory,
) -> MemoryRecord:
    return append_learned_memory(memory_manager, memory)
