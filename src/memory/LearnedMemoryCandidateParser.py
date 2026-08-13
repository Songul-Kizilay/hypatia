"""Pure parsing boundary for learned-memory candidate payloads."""

import json

from memory.LearnedMemoryCandidate import LearnedMemoryCandidateBatch

_INVALID_PAYLOAD_MESSAGE = "Learned memory candidate payload invalid."


def parse_learned_memory_candidate_batch(
    *,
    source_text: str,
    payload: str,
) -> LearnedMemoryCandidateBatch:
    try:
        decoded = json.loads(payload)
    except (json.JSONDecodeError, TypeError) as error:
        raise ValueError(_INVALID_PAYLOAD_MESSAGE) from error

    if decoded != {"candidates": []}:
        raise ValueError(_INVALID_PAYLOAD_MESSAGE)

    return LearnedMemoryCandidateBatch(
        source_text=source_text,
        candidates=(),
    )
