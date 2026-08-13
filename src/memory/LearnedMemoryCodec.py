"""Deterministic persistence-field encoding for learned memories."""

from memory.LearnedMemory import LearnedMemory


def encode_learned_memory(
    memory: LearnedMemory,
) -> tuple[str, frozenset[str], dict[str, str]]:
    return (
        memory.value,
        frozenset({"learned", memory.kind}),
        {
            "kind": memory.kind,
            "key": memory.key,
            "value": memory.value,
        },
    )
