"""Pure parsing boundary for learned-memory candidate payloads."""

import json
from typing import cast

from memory.LearnedMemory import LearnedMemory, LearnedMemoryKind
from memory.LearnedMemoryCandidate import (
    LearnedMemoryCandidate,
    LearnedMemoryCandidateBatch,
)

_INVALID_PAYLOAD_MESSAGE = "Learned memory candidate payload invalid."
_ALLOWED_KINDS = {
    "user_fact",
    "preference",
    "project_fact",
    "goal",
    "self_fact",
}


def parse_learned_memory_candidate_batch(
    *,
    source_text: str,
    payload: str,
) -> LearnedMemoryCandidateBatch:
    try:
        decoded = json.loads(payload)
    except (json.JSONDecodeError, TypeError) as error:
        raise ValueError(_INVALID_PAYLOAD_MESSAGE) from error

    if not isinstance(decoded, dict) or set(decoded) != {"candidates"}:
        raise ValueError(_INVALID_PAYLOAD_MESSAGE)

    candidates = decoded["candidates"]
    if not isinstance(candidates, list) or len(candidates) > 1:
        raise ValueError(_INVALID_PAYLOAD_MESSAGE)

    if not candidates:
        return LearnedMemoryCandidateBatch(
            source_text=source_text,
            candidates=(),
        )

    candidate = candidates[0]
    if not isinstance(candidate, dict) or set(candidate) != {
        "kind",
        "key",
        "value",
    }:
        raise ValueError(_INVALID_PAYLOAD_MESSAGE)

    kind = candidate["kind"]
    key = candidate["key"]
    value = candidate["value"]
    if (
        not isinstance(kind, str)
        or kind not in _ALLOWED_KINDS
        or not isinstance(key, str)
        or not isinstance(value, str)
    ):
        raise ValueError(_INVALID_PAYLOAD_MESSAGE)

    return LearnedMemoryCandidateBatch(
        source_text=source_text,
        candidates=(
            LearnedMemoryCandidate(
                memory=LearnedMemory(
                    kind=cast(LearnedMemoryKind, kind),
                    key=key,
                    value=value,
                ),
                source_text=source_text,
            ),
        ),
    )
