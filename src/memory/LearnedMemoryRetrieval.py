"""Pure collection helpers for learned-memory records."""

from memory.LearnedMemory import LearnedMemory, LearnedMemoryKind
from memory.LearnedMemoryCodec import decode_learned_memory
from memory.MemoryRecord import MemoryRecord


def collect_learned_memories(
    records: tuple[MemoryRecord, ...],
) -> tuple[LearnedMemory, ...]:
    memories: list[LearnedMemory] = []

    for record in records:
        memory = decode_learned_memory(record)
        if memory is not None:
            memories.append(memory)

    return tuple(memories)


def find_learned_memories(
    memories: tuple[LearnedMemory, ...],
    *,
    kind: LearnedMemoryKind,
    key: str,
) -> tuple[LearnedMemory, ...]:
    return tuple(
        memory for memory in memories if memory.kind == kind and memory.key == key
    )


def select_latest_learned_memories(
    memories: tuple[LearnedMemory, ...],
) -> tuple[LearnedMemory, ...]:
    seen: set[tuple[LearnedMemoryKind, str]] = set()
    retained_reversed: list[LearnedMemory] = []

    for memory in reversed(memories):
        identity = (memory.kind, memory.key)
        if identity not in seen:
            seen.add(identity)
            retained_reversed.append(memory)

    return tuple(reversed(retained_reversed))


def resolve_latest_learned_memory(
    memories: tuple[LearnedMemory, ...],
    *,
    kind: LearnedMemoryKind,
    key: str,
) -> LearnedMemory | None:
    matches = find_learned_memories(memories, kind=kind, key=key)
    return matches[-1] if matches else None
