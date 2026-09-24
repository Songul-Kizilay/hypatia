"""One immutable, append-only relationship between two assets.

References both sides by `(kind, canonical_value)`, not a synthetic asset ID —
matching the derived-projection identity model `ResearchAsset` uses (assets
are never persisted directly, so there is no durable asset ID to reference).
A relation carries no scope semantics of its own: recording `RESOLVES_TO`
between two assets never widens, implies, or substitutes for either asset's
scope resolution, which is always a fresh call into
`ResearchTargetScope.resolve_hostname`/`resolve_addresses`.

Every relation now carries an explicit `provenance` — a relation is no longer
implicitly operator-authored by omission. `source_operation_digest` is bound
1:1 to `provenance` by the same fail-closed rule
`ResearchAssetObservationRecord` enforces (see
`require_bound_provenance_digest`): `None` exactly for `OPERATOR_AUTHORED`, a
valid Kali operation digest exactly for `KALI_OPERATION_RESULT`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.Exceptions import ResearchError
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchAssetObservationRecord import (
    MAX_ASSET_CANONICAL_VALUE_CHARACTERS,
    canonicalize_asset_value,
    require_bound_provenance_digest,
)
from research.ResearchAssetProvenanceKind import ResearchAssetProvenanceKind
from research.ResearchAssetRelationKind import ResearchAssetRelationKind

MAX_ASSET_RELATION_ID_CHARACTERS = 200
MAX_ASSET_RELATION_PROGRAM_ID_CHARACTERS = 200
MAX_ASSET_RELATION_NOTE_CHARACTERS = 2_000


@dataclass(frozen=True, slots=True)
class ResearchAssetRelationRecord:
    """One recorded fact: this operator relates one asset to another."""

    relation_id: str
    program_id: str
    source_kind: ResearchAssetKind
    source_value: str
    related_kind: ResearchAssetKind
    related_value: str
    kind: ResearchAssetRelationKind
    provenance: ResearchAssetProvenanceKind
    note: str
    recorded_at: datetime
    source_operation_digest: str | None = None

    def __post_init__(self) -> None:
        relation_id = self._bounded_id(
            self.relation_id,
            "Asset relation ID",
            MAX_ASSET_RELATION_ID_CHARACTERS,
        )
        program_id = self._bounded_id(
            self.program_id,
            "Asset relation program ID",
            MAX_ASSET_RELATION_PROGRAM_ID_CHARACTERS,
        )
        if not isinstance(self.kind, ResearchAssetRelationKind):
            raise ResearchError("Asset relation kind is invalid.")
        require_bound_provenance_digest(
            self.provenance, self.source_operation_digest, "Asset relation"
        )
        source_value = self._require_canonical_value(
            self.source_kind, self.source_value, "source"
        )
        related_value = self._require_canonical_value(
            self.related_kind, self.related_value, "related"
        )
        if (self.source_kind, source_value) == (self.related_kind, related_value):
            raise ResearchError("Asset relation cannot relate an asset to itself.")
        if self.kind is ResearchAssetRelationKind.RESOLVES_TO and (
            self.source_kind is not ResearchAssetKind.HOSTNAME
            or self.related_kind is not ResearchAssetKind.IP_ADDRESS
        ):
            raise ResearchError(
                "A resolves-to relation must point from a hostname to an IP address."
            )
        if not isinstance(self.note, str):
            raise ResearchError("Asset relation note is invalid.")
        if len(self.note.strip()) > MAX_ASSET_RELATION_NOTE_CHARACTERS:
            raise ResearchError("Asset relation note is too long.")
        if (
            not isinstance(self.recorded_at, datetime)
            or self.recorded_at.utcoffset() is None
        ):
            raise ResearchError("Asset relation recorded time must be timezone-aware.")
        object.__setattr__(self, "relation_id", relation_id)
        object.__setattr__(self, "program_id", program_id)
        object.__setattr__(self, "source_value", source_value)
        object.__setattr__(self, "related_value", related_value)
        object.__setattr__(self, "note", self.note.strip())

    @staticmethod
    def _require_canonical_value(
        kind: ResearchAssetKind, value: str, label: str
    ) -> str:
        if (
            not isinstance(value, str)
            or not value
            or len(value) > MAX_ASSET_CANONICAL_VALUE_CHARACTERS
        ):
            raise ResearchError(f"Asset relation {label} value is invalid.")
        try:
            expected = canonicalize_asset_value(kind, value)
        except ResearchError as error:
            raise ResearchError(
                f"Asset relation {label} value is not canonical."
            ) from error
        if expected != value:
            raise ResearchError(f"Asset relation {label} value is not canonical.")
        return value

    @staticmethod
    def _bounded_id(value: str, label: str, maximum: int) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ResearchError(f"{label} cannot be empty.")
        normalized = value.strip()
        if len(normalized) > maximum:
            raise ResearchError(f"{label} is too long.")
        return normalized
