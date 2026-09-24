"""One immutable, append-only, operator-authored asset observation fact.

An observation only says: this operator recorded this canonical hostname or
address, with this note, at this time. It never says the asset is currently
reachable, currently resolves the same way, or is in scope for anything —
`ResearchAsset`/`assets_for_program` derive identity from these facts, and
`ResearchTargetScope.resolve_hostname`/`resolve_addresses` (always called
fresh, never cached here) are the only source of a scope answer.

`canonical_value` must already be canonical for its `kind` when this record
is constructed: unchanged under `ResearchTargetScope.canonical_dns_hostname`
for `HOSTNAME`, unchanged under `str(ipaddress.ip_address(value))` for
`IP_ADDRESS`. This fails closed rather than silently normalizing, so a
canonicalization decision is always made once, explicitly, by the caller that
already holds raw operator input — never repeated or second-guessed here.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from datetime import datetime

from core.Exceptions import ResearchError
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchAssetProvenanceKind import ResearchAssetProvenanceKind
from research.ResearchTargetScope import canonical_dns_hostname

MAX_ASSET_OBSERVATION_ID_CHARACTERS = 200
MAX_ASSET_PROGRAM_ID_CHARACTERS = 200
MAX_ASSET_CANONICAL_VALUE_CHARACTERS = 253
MAX_ASSET_OBSERVATION_NOTE_CHARACTERS = 2_000


def canonicalize_asset_value(kind: ResearchAssetKind, value: str) -> str:
    """Derive the single canonical form for `value` under `kind`.

    The one place raw, possibly-uncanonical operator input is allowed to
    become canonical. Every record type instead fails closed if a value it
    is given is not already exactly this function's output — this function
    is what a caller runs first.
    """
    if not isinstance(kind, ResearchAssetKind):
        raise ResearchError("Asset kind is invalid.")
    if not isinstance(value, str) or not value.strip():
        raise ResearchError("Asset value cannot be empty.")
    stripped = value.strip()
    if kind is ResearchAssetKind.HOSTNAME:
        return canonical_dns_hostname(stripped)
    try:
        parsed = ipaddress.ip_address(stripped)
    except ValueError as error:
        raise ResearchError("Asset address is invalid.") from error
    if getattr(parsed, "scope_id", None) is not None:
        # A scoped link-local address (`fe80::1%eth0`) parses and round-trips
        # here, but `ResearchTargetScope` refuses every address containing
        # "%" before matching. Accepting it would make an identity the scope
        # layer structurally cannot read, and because records are append-only
        # that would wedge the program's whole inventory read path with no
        # recovery. Identity refuses exactly what scope matching refuses.
        raise ResearchError("Asset address is invalid.")
    return str(parsed)


@dataclass(frozen=True, slots=True)
class ResearchAssetObservationRecord:
    """One recorded fact: this canonical asset was observed by an operator."""

    observation_id: str
    program_id: str
    kind: ResearchAssetKind
    canonical_value: str
    provenance: ResearchAssetProvenanceKind
    note: str
    recorded_at: datetime

    def __post_init__(self) -> None:
        observation_id = self._bounded_id(
            self.observation_id,
            "Asset observation ID",
            MAX_ASSET_OBSERVATION_ID_CHARACTERS,
        )
        program_id = self._bounded_id(
            self.program_id,
            "Asset observation program ID",
            MAX_ASSET_PROGRAM_ID_CHARACTERS,
        )
        if not isinstance(self.kind, ResearchAssetKind):
            raise ResearchError("Asset observation kind is invalid.")
        if not isinstance(self.provenance, ResearchAssetProvenanceKind):
            raise ResearchError("Asset observation provenance is invalid.")
        if (
            not isinstance(self.canonical_value, str)
            or not self.canonical_value
            or len(self.canonical_value) > MAX_ASSET_CANONICAL_VALUE_CHARACTERS
        ):
            raise ResearchError("Asset observation canonical value is invalid.")
        self._require_already_canonical(self.kind, self.canonical_value)
        if not isinstance(self.note, str):
            raise ResearchError("Asset observation note is invalid.")
        if len(self.note.strip()) > MAX_ASSET_OBSERVATION_NOTE_CHARACTERS:
            raise ResearchError("Asset observation note is too long.")
        if (
            not isinstance(self.recorded_at, datetime)
            or self.recorded_at.utcoffset() is None
        ):
            raise ResearchError(
                "Asset observation recorded time must be timezone-aware."
            )
        object.__setattr__(self, "observation_id", observation_id)
        object.__setattr__(self, "program_id", program_id)
        object.__setattr__(self, "note", self.note.strip())

    @staticmethod
    def _require_already_canonical(kind: ResearchAssetKind, value: str) -> None:
        """Fail closed unless `value` is already the kind-appropriate canonical form."""
        try:
            expected = canonicalize_asset_value(kind, value)
        except ResearchError as error:
            raise ResearchError(
                "Asset observation canonical value is not canonical."
            ) from error
        if expected != value:
            raise ResearchError("Asset observation canonical value is not canonical.")

    @staticmethod
    def _bounded_id(value: str, label: str, maximum: int) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ResearchError(f"{label} cannot be empty.")
        normalized = value.strip()
        if len(normalized) > maximum:
            raise ResearchError(f"{label} is too long.")
        return normalized
