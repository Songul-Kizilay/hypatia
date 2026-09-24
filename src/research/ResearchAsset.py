"""Pure, bounded asset identity derived from recorded observations only.

Modeled directly on `ResearchSourceTemporalHistory.py`'s type-plus-builder
shape: a canonical identity kept structurally separate from a tuple of
dated, independently-recorded observations, derived fresh from already-
persisted data on every read. `ResearchAsset` is never itself persisted —
there is no "find an existing asset and mutate it" persistence logic
anywhere; `assets_for_program` recomputes identical output from the same
observation list on every call.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.Exceptions import ResearchError
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchAssetObservationRecord import ResearchAssetObservationRecord


@dataclass(frozen=True, slots=True)
class ResearchAsset:
    """One canonical asset identity and every observation recorded of it."""

    program_id: str
    kind: ResearchAssetKind
    canonical_value: str
    observations: tuple[ResearchAssetObservationRecord, ...]

    def __post_init__(self) -> None:
        # `ResearchAssetKind` is a `StrEnum`, so the identity comparison below
        # would treat the plain string "hostname" as equal to the member. The
        # explicit check keeps a derived asset from carrying a kind no
        # resolver dispatch recognises.
        if not isinstance(self.kind, ResearchAssetKind):
            raise ResearchError("Research asset kind is invalid.")
        if not isinstance(self.program_id, str) or not self.program_id.strip():
            raise ResearchError("Research asset program ID is invalid.")
        canonical_value = self.canonical_value
        if not isinstance(canonical_value, str) or not canonical_value.strip():
            raise ResearchError("Research asset canonical value is invalid.")
        if not isinstance(self.observations, tuple) or not self.observations:
            raise ResearchError("Research asset requires at least one observation.")
        if any(
            not isinstance(observation, ResearchAssetObservationRecord)
            for observation in self.observations
        ):
            raise ResearchError("Research asset observations are invalid.")
        if any(
            (
                observation.program_id,
                observation.kind,
                observation.canonical_value,
            )
            != (self.program_id, self.kind, self.canonical_value)
            for observation in self.observations
        ):
            raise ResearchError(
                "Research asset observations do not all share this asset's identity."
            )

    @property
    def first_seen(self) -> datetime:
        """Return the earliest of this asset's recorded observation times."""
        return min(observation.recorded_at for observation in self.observations)

    @property
    def last_seen(self) -> datetime:
        """Return the latest of this asset's recorded observation times."""
        return max(observation.recorded_at for observation in self.observations)


def assets_for_program(
    program_id: str,
    observations: tuple[ResearchAssetObservationRecord, ...],
) -> tuple[ResearchAsset, ...]:
    """Derive one program's assets fresh from its flat recorded observation list.

    Groups by `(program_id, kind, canonical_value)`, preserving each group's
    observations in their given order. Deterministic: assets are returned
    sorted by `(kind, canonical_value)`, so restart/reload and repeated calls
    over identical input always produce byte-identical output.
    """
    if not isinstance(program_id, str) or not program_id.strip():
        raise ResearchError("Research asset program ID cannot be empty.")
    normalized_program_id = program_id.strip()
    if not isinstance(observations, tuple):
        raise ResearchError("Research asset observations must be an immutable tuple.")
    if any(
        not isinstance(observation, ResearchAssetObservationRecord)
        for observation in observations
    ):
        raise ResearchError("Research asset observations are invalid.")
    grouped: dict[
        tuple[ResearchAssetKind, str], list[ResearchAssetObservationRecord]
    ] = {}
    for observation in observations:
        if observation.program_id != normalized_program_id:
            continue
        key = (observation.kind, observation.canonical_value)
        grouped.setdefault(key, []).append(observation)
    return tuple(
        ResearchAsset(
            program_id=normalized_program_id,
            kind=kind,
            canonical_value=canonical_value,
            observations=tuple(grouped[(kind, canonical_value)]),
        )
        for kind, canonical_value in sorted(grouped, key=lambda key: (key[0], key[1]))
    )
