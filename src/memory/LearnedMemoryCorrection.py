"""Thin service for append-only learned-memory corrections."""

from memory.LearnedMemory import LearnedMemory, LearnedMemoryKind
from memory.LearnedMemoryStore import (
    correct_learned_memory,
    load_latest_learned_memory,
)
from memory.MemoryManager import MemoryManager
from memory.MemoryRecord import MemoryRecord


def should_correct_learned_memory(
    current: LearnedMemory | None,
    *,
    kind: LearnedMemoryKind,
    key: str,
    value: str,
) -> bool:
    if current is None:
        return True
    return (current.kind, current.key, current.value) != (kind, key, value)


def correct_learned_memory_value(
    memory_manager: MemoryManager,
    *,
    kind: LearnedMemoryKind,
    key: str,
    value: str,
) -> MemoryRecord:
    memory = LearnedMemory(kind=kind, key=key, value=value)
    return correct_learned_memory(memory_manager, memory)


def correct_learned_memory_value_if_changed(
    memory_manager: MemoryManager,
    *,
    kind: LearnedMemoryKind,
    key: str,
    value: str,
) -> MemoryRecord | None:
    current = load_latest_learned_memory(
        memory_manager,
        kind=kind,
        key=key,
    )
    if not should_correct_learned_memory(
        current,
        kind=kind,
        key=key,
        value=value,
    ):
        return None
    return correct_learned_memory_value(
        memory_manager,
        kind=kind,
        key=key,
        value=value,
    )
