"""Immutable read-only health summary for the learned-memory store."""

from __future__ import annotations

from dataclasses import dataclass

from memory.LearnedMemory import LearnedMemoryKind

MAX_AUDIT_SAMPLES = 10


@dataclass(frozen=True, slots=True)
class LearnedMemoryIdentitySample:
    """One bounded (kind, key) identity summary without any stored value."""

    kind: LearnedMemoryKind
    key: str
    versions: int


@dataclass(frozen=True, slots=True)
class LearnedMemoryDuplicateCandidate:
    """Two active identities whose stored values are exactly equal.

    This is a candidate for human review only. Equal text is not proof of
    equivalent meaning, and the audit never merges or rewrites either memory.
    """

    first_kind: LearnedMemoryKind
    first_key: str
    second_kind: LearnedMemoryKind
    second_key: str


@dataclass(frozen=True, slots=True)
class LearnedMemoryAuditReport:
    """Deterministic bounded metrics describing learned-memory health."""

    total_learned_records: int
    active_memories: int
    superseded_memories: int
    identities: int
    identities_with_multiple_versions: int
    max_versions_for_one_identity: int
    conflicting_history_identities: int
    duplicate_value_candidates: int
    conflicting_history_samples: tuple[LearnedMemoryIdentitySample, ...]
    duplicate_value_candidate_samples: tuple[LearnedMemoryDuplicateCandidate, ...]
    samples_truncated: bool

    @property
    def superseded_ratio(self) -> float:
        """Return the superseded share of all learned records, or 0.0 when empty."""
        if self.total_learned_records == 0:
            return 0.0
        return self.superseded_memories / self.total_learned_records
