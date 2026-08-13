"""Persistence seam for encoded learned memories."""

from memory.LearnedMemory import LearnedMemory
from memory.LearnedMemoryCodec import encode_learned_memory
from memory.MemoryManager import MemoryManager
from memory.MemoryRecord import MemoryRecord


def persist_learned_memory(
    memory_manager: MemoryManager,
    memory: LearnedMemory,
) -> MemoryRecord:
    content, tags, metadata = encode_learned_memory(memory)

    return memory_manager.add(
        content=content,
        tags=tags,
        metadata=metadata,
    )
