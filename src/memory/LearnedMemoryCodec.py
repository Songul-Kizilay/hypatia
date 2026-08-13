"""Deterministic persistence-field encoding for learned memories."""

from typing import cast

from memory.LearnedMemory import LearnedMemory, LearnedMemoryKind
from memory.MemoryRecord import MemoryRecord

_LEARNED_MEMORY_KINDS = frozenset(
    {
        "user_fact",
        "preference",
        "project_fact",
        "goal",
        "self_fact",
    }
)


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


def decode_learned_memory(record: MemoryRecord) -> LearnedMemory | None:
    if "learned" not in record.tags:
        return None

    kind = record.metadata.get("kind")
    key = record.metadata.get("key")
    value = record.metadata.get("value")

    if not isinstance(kind, str) or kind not in _LEARNED_MEMORY_KINDS:
        return None
    if not isinstance(key, str) or not isinstance(value, str):
        return None

    return LearnedMemory(
        kind=cast(LearnedMemoryKind, kind),
        key=key,
        value=value,
    )
