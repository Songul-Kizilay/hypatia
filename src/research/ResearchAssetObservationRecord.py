"""One immutable, append-only asset observation fact.

An observation only says: this attested source recorded this canonical
hostname or address, with this note, at this time. It never says the asset is
currently reachable, currently resolves the same way, or is in scope for
anything — `ResearchAsset`/`assets_for_program` derive identity from these
facts, and `ResearchTargetScope.resolve_hostname`/`resolve_addresses` (always
called fresh, never cached here) are the only source of a scope answer.

`canonical_value` must already be canonical for its `kind` when this record
is constructed: unchanged under `ResearchTargetScope.canonical_dns_hostname`
for `HOSTNAME`, unchanged under `str(ipaddress.ip_address(value))` for
`IP_ADDRESS`. This fails closed rather than silently normalizing, so a
canonicalization decision is always made once, explicitly, by the caller that
already holds raw operator input — never repeated or second-guessed here.

`source_operation_digest` and `provenance` are fail-closed 1:1 bound:
`source_operation_digest` is `None` exactly when `provenance` is
`OPERATOR_AUTHORED` (a human cannot forge automated provenance by supplying a
digest), and a valid `is_kali_operation_digest` value exactly when
`provenance` is `KALI_OPERATION_RESULT` (an automated result cannot
masquerade as operator-authored by omitting it).
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from datetime import datetime

from core.Exceptions import ResearchError
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchAssetProvenanceKind import ResearchAssetProvenanceKind
from research.ResearchKaliOperationPreview import is_kali_operation_digest
from research.ResearchSensitiveInputPolicy import ResearchSensitiveInputPolicy
from research.ResearchTargetScope import canonical_dns_hostname

MAX_ASSET_OBSERVATION_ID_CHARACTERS = 200
MAX_ASSET_PROGRAM_ID_CHARACTERS = 200
MAX_ASSET_CANONICAL_VALUE_CHARACTERS = 253
MAX_ASSET_OBSERVATION_NOTE_CHARACTERS = 2_000

_SENSITIVE_INPUT_POLICY = ResearchSensitiveInputPolicy()


def _refuse_sensitive_input(value: str, label: str) -> None:
    sensitive_class = _SENSITIVE_INPUT_POLICY.classify(value)
    if sensitive_class.refused:
        raise ResearchError(f"{label} was refused as {sensitive_class.operator_label}.")


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


def require_bound_provenance_digest(
    provenance: ResearchAssetProvenanceKind,
    source_operation_digest: str | None,
    label: str,
) -> None:
    """Fail closed unless `source_operation_digest` matches `provenance` 1:1.

    Shared by `ResearchAssetObservationRecord` and `ResearchAssetRelationRecord`
    so the forgery-rejection rule can never silently diverge between the two
    record types.
    """
    if not isinstance(provenance, ResearchAssetProvenanceKind):
        raise ResearchError(f"{label} provenance is invalid.")
    if provenance is ResearchAssetProvenanceKind.OPERATOR_AUTHORED:
        if source_operation_digest is not None:
            raise ResearchError(
                f"{label} cannot carry an operation digest for operator-authored"
                " provenance."
            )
    elif provenance is ResearchAssetProvenanceKind.KALI_OPERATION_RESULT:
        if not is_kali_operation_digest(source_operation_digest):
            raise ResearchError(
                f"{label} requires a valid Kali operation digest for automated"
                " provenance."
            )
    else:
        raise ResearchError(f"{label} provenance is invalid.")


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
    source_operation_digest: str | None = None

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
        require_bound_provenance_digest(
            self.provenance, self.source_operation_digest, "Asset observation"
        )
        if (
            not isinstance(self.canonical_value, str)
            or not self.canonical_value
            or len(self.canonical_value) > MAX_ASSET_CANONICAL_VALUE_CHARACTERS
        ):
            raise ResearchError("Asset observation canonical value is invalid.")
        self._require_already_canonical(self.kind, self.canonical_value)
        if not isinstance(self.note, str):
            raise ResearchError("Asset observation note is invalid.")
        note = self.note.strip()
        if len(note) > MAX_ASSET_OBSERVATION_NOTE_CHARACTERS:
            raise ResearchError("Asset observation note is too long.")
        _refuse_sensitive_input(note, "Asset observation note")
        if (
            not isinstance(self.recorded_at, datetime)
            or self.recorded_at.utcoffset() is None
        ):
            raise ResearchError(
                "Asset observation recorded time must be timezone-aware."
            )
        object.__setattr__(self, "observation_id", observation_id)
        object.__setattr__(self, "program_id", program_id)
        object.__setattr__(self, "note", note)

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
