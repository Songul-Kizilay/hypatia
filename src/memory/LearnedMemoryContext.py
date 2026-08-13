"""Deterministic LLM-readable representation of learned memories."""

from memory.LearnedMemory import LearnedMemory


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
