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


def resolve_latest_learned_memory(
    memories: tuple[LearnedMemory, ...],
    *,
    kind: LearnedMemoryKind,
    key: str,
) -> LearnedMemory | None:
    matches = find_learned_memories(memories, kind=kind, key=key)
    return matches[-1] if matches else None
