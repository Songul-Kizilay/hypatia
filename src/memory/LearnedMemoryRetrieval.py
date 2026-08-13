"""Pure collection helpers for learned-memory records."""

from memory.LearnedMemory import LearnedMemory
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
