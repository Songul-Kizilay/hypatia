"""Thin adapter from a learning candidate to learned-memory persistence."""

from memory.LearnedMemoryCandidate import (
    LearnedMemoryCandidate,
    LearnedMemoryCandidateBatch,
)
from memory.LearnedMemoryCorrection import (
    correct_learned_memory_value_if_changed,
)
from memory.MemoryManager import MemoryManager
from memory.MemoryRecord import MemoryRecord


def persist_learned_memory_candidate(
    memory_manager: MemoryManager,
    candidate: LearnedMemoryCandidate,
) -> MemoryRecord | None:
    return correct_learned_memory_value_if_changed(
        memory_manager,
        kind=candidate.memory.kind,
        key=candidate.memory.key,
        value=candidate.memory.value,
    )


def persist_learned_memory_candidate_batch(
    memory_manager: MemoryManager,
    batch: LearnedMemoryCandidateBatch,
) -> tuple[MemoryRecord | None, ...]:
    return tuple(
        persist_learned_memory_candidate(memory_manager, candidate)
        for candidate in batch.candidates
    )
