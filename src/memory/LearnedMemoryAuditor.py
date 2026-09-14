"""Pure read-only auditing of learned-memory records.

The auditor never writes, deletes, merges, normalizes, or reorders stored data.
It reports candidates for human review and deliberately makes no equivalence,
correctness, or deletion decision of its own.
"""

from __future__ import annotations

from memory.LearnedMemory import LearnedMemory, LearnedMemoryKind
from memory.LearnedMemoryAuditReport import (
    MAX_AUDIT_SAMPLES,
    LearnedMemoryAuditReport,
    LearnedMemoryDuplicateCandidate,
    LearnedMemoryIdentitySample,
)
from memory.LearnedMemoryRetrieval import (
    collect_learned_memories,
    select_latest_learned_memories,
)
from memory.MemoryRecord import MemoryRecord

_Identity = tuple[LearnedMemoryKind, str]


def audit_learned_memory_records(
    records: tuple[MemoryRecord, ...],
) -> LearnedMemoryAuditReport:
    """Return deterministic bounded metrics for the supplied records."""
    memories = collect_learned_memories(records)
    return audit_learned_memories(memories)


def audit_learned_memories(
    memories: tuple[LearnedMemory, ...],
) -> LearnedMemoryAuditReport:
    """Return deterministic bounded metrics without mutating any input."""
    active_memories = select_latest_learned_memories(memories)

    versions_by_identity: dict[_Identity, int] = {}
    distinct_values_by_identity: dict[_Identity, set[str]] = {}
    for memory in memories:
        identity: _Identity = (memory.kind, memory.key)
        versions_by_identity[identity] = versions_by_identity.get(identity, 0) + 1
        distinct_values_by_identity.setdefault(identity, set()).add(memory.value)

    conflicting_identities = tuple(
        sorted(
            (
                identity
                for identity, values in distinct_values_by_identity.items()
                if len(values) > 1
            )
        )
    )
    duplicate_candidates = _duplicate_value_candidates(active_memories)

    conflicting_samples = tuple(
        LearnedMemoryIdentitySample(
            kind=kind,
            key=key,
            versions=versions_by_identity[(kind, key)],
        )
        for kind, key in conflicting_identities[:MAX_AUDIT_SAMPLES]
    )
    duplicate_samples = duplicate_candidates[:MAX_AUDIT_SAMPLES]

    return LearnedMemoryAuditReport(
        total_learned_records=len(memories),
        active_memories=len(active_memories),
        superseded_memories=len(memories) - len(active_memories),
        identities=len(versions_by_identity),
        identities_with_multiple_versions=sum(
            1 for count in versions_by_identity.values() if count > 1
        ),
        max_versions_for_one_identity=(
            max(versions_by_identity.values()) if versions_by_identity else 0
        ),
        conflicting_history_identities=len(conflicting_identities),
        duplicate_value_candidates=len(duplicate_candidates),
        conflicting_history_samples=conflicting_samples,
        duplicate_value_candidate_samples=duplicate_samples,
        samples_truncated=(
            len(conflicting_identities) > MAX_AUDIT_SAMPLES
            or len(duplicate_candidates) > MAX_AUDIT_SAMPLES
        ),
    )


def _duplicate_value_candidates(
    active_memories: tuple[LearnedMemory, ...],
) -> tuple[LearnedMemoryDuplicateCandidate, ...]:
    """Pair active identities whose stored values are exactly equal.

    Exact value equality is the only signal used. The pairing is a review
    candidate, never an assertion that two memories mean the same thing.
    """
    by_value: dict[str, list[LearnedMemory]] = {}
    for memory in active_memories:
        by_value.setdefault(memory.value, []).append(memory)

    candidates: list[LearnedMemoryDuplicateCandidate] = []
    for value in sorted(by_value):
        group = sorted(by_value[value], key=lambda memory: (memory.kind, memory.key))
        if len(group) < 2:
            continue
        for first_index in range(len(group)):
            for second_index in range(first_index + 1, len(group)):
                first = group[first_index]
                second = group[second_index]
                candidates.append(
                    LearnedMemoryDuplicateCandidate(
                        first_kind=first.kind,
                        first_key=first.key,
                        second_kind=second.kind,
                        second_key=second.key,
                    )
                )
    return tuple(candidates)
