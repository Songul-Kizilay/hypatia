"""Preview and confirmed-write results for ingesting one DNS lookup run.

Kept in `research/`, not alongside the application service that builds them,
matching `ResearchAssetInventoryEntry.py`'s existing separation: so
`brain.BrainResponse` can reference these types without a cognition-layer
import cycle.

`ResearchAssetDnsIngestionPreview` is side-effect-free — it never claims a
write happened, mirroring `ResearchKaliOperationEvidenceCandidate`'s
`evidence_recorded`/`claim_created`/... discipline. `ResearchAssetDnsIngestionResult`
is only ever constructed from records a durable write has already produced;
it exists to give the operator one bounded view of what was created/already
known/rejected, never to authorize anything further.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchAssetObservationRecord import ResearchAssetObservationRecord
from research.ResearchAssetProvenanceKind import ResearchAssetProvenanceKind
from research.ResearchAssetRelationKind import ResearchAssetRelationKind
from research.ResearchAssetRelationRecord import ResearchAssetRelationRecord
from research.ResearchDnsLookupResultParser import ResearchDnsLookupRejectedRow
from research.ResearchKaliOperationPreview import (
    ResearchDnsRecordType,
    is_kali_operation_digest,
)

MAX_DNS_INGESTION_PROGRAM_ID_CHARACTERS = 200


@dataclass(frozen=True, slots=True)
class ResearchAssetDnsIngestionAssetPreview:
    """One asset a DNS ingestion would observe, and whether it already exists."""

    kind: ResearchAssetKind
    canonical_value: str
    already_known: bool

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ResearchAssetKind):
            raise ResearchError("DNS ingestion asset preview kind is invalid.")
        if not isinstance(self.canonical_value, str) or not self.canonical_value:
            raise ResearchError(
                "DNS ingestion asset preview canonical value cannot be empty."
            )
        if not isinstance(self.already_known, bool):
            raise ResearchError(
                "DNS ingestion asset preview known flag must be boolean."
            )


@dataclass(frozen=True, slots=True)
class ResearchAssetDnsIngestionAddressPreview:
    """One resolved address candidate, paired with its would-be relation state."""

    asset: ResearchAssetDnsIngestionAssetPreview
    resolves_to_relation_already_known: bool

    def __post_init__(self) -> None:
        if not isinstance(self.asset, ResearchAssetDnsIngestionAssetPreview):
            raise ResearchError("DNS ingestion address preview asset is invalid.")
        if self.asset.kind is not ResearchAssetKind.IP_ADDRESS:
            raise ResearchError(
                "DNS ingestion address preview must hold an IP address asset."
            )
        if not isinstance(self.resolves_to_relation_already_known, bool):
            raise ResearchError(
                "DNS ingestion address preview relation flag must be boolean."
            )


@dataclass(frozen=True, slots=True)
class ResearchAssetDnsIngestionPreview:
    """A complete, side-effect-free preview of ingesting one DNS lookup run.

    `observations_recorded`/`relations_recorded` are hard-pinned `False`,
    mirroring `ResearchKaliOperationEvidenceCandidate`: this type gives the
    operator a bounded view without ever claiming a durable write happened.
    """

    program_id: str
    operation_digest: str
    hostname_asset: ResearchAssetDnsIngestionAssetPreview
    record_type: ResearchDnsRecordType
    address_assets: tuple[ResearchAssetDnsIngestionAddressPreview, ...]
    rejected_rows: tuple[ResearchDnsLookupRejectedRow, ...]
    observations_recorded: bool = False
    relations_recorded: bool = False

    def __post_init__(self) -> None:
        if (
            not isinstance(self.program_id, str)
            or not self.program_id.strip()
            or len(self.program_id) > MAX_DNS_INGESTION_PROGRAM_ID_CHARACTERS
        ):
            raise ResearchError("DNS ingestion preview program ID is invalid.")
        if not is_kali_operation_digest(self.operation_digest):
            raise ResearchError("DNS ingestion preview operation digest is invalid.")
        if (
            not isinstance(self.hostname_asset, ResearchAssetDnsIngestionAssetPreview)
            or self.hostname_asset.kind is not ResearchAssetKind.HOSTNAME
        ):
            raise ResearchError("DNS ingestion preview hostname asset is invalid.")
        if not isinstance(self.record_type, ResearchDnsRecordType):
            raise ResearchError("DNS ingestion preview record type is invalid.")
        if not isinstance(self.address_assets, tuple) or any(
            not isinstance(entry, ResearchAssetDnsIngestionAddressPreview)
            for entry in self.address_assets
        ):
            raise ResearchError("DNS ingestion preview address assets are invalid.")
        if not isinstance(self.rejected_rows, tuple) or any(
            not isinstance(row, ResearchDnsLookupRejectedRow)
            for row in self.rejected_rows
        ):
            raise ResearchError("DNS ingestion preview rejected rows are invalid.")
        if self.observations_recorded is not False or self.relations_recorded is not (
            False
        ):
            raise ResearchError("DNS ingestion preview must not claim writes.")


@dataclass(frozen=True, slots=True)
class ResearchAssetDnsIngestionResult:
    """What one confirmed DNS ingestion actually recorded.

    Every observation/relation here is validated to already carry
    `provenance=KALI_OPERATION_RESULT` and `source_operation_digest ==
    operation_digest` — this type can only describe a write that already
    happened through the same fail-closed record types, never fabricate one.
    """

    program_id: str
    operation_digest: str
    hostname_observation: ResearchAssetObservationRecord
    address_observations: tuple[ResearchAssetObservationRecord, ...]
    relations: tuple[ResearchAssetRelationRecord, ...]
    rejected_rows: tuple[ResearchDnsLookupRejectedRow, ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.program_id, str)
            or not self.program_id.strip()
            or len(self.program_id) > MAX_DNS_INGESTION_PROGRAM_ID_CHARACTERS
        ):
            raise ResearchError("DNS ingestion result program ID is invalid.")
        if not is_kali_operation_digest(self.operation_digest):
            raise ResearchError("DNS ingestion result operation digest is invalid.")
        self._require_ingested_observation(
            self.hostname_observation, ResearchAssetKind.HOSTNAME
        )
        if not isinstance(self.address_observations, tuple):
            raise ResearchError("DNS ingestion result address observations invalid.")
        for observation in self.address_observations:
            self._require_ingested_observation(
                observation, ResearchAssetKind.IP_ADDRESS
            )
        if not isinstance(self.relations, tuple):
            raise ResearchError("DNS ingestion result relations are invalid.")
        address_values = {
            observation.canonical_value for observation in self.address_observations
        }
        if len(self.relations) != len(self.address_observations):
            raise ResearchError(
                "DNS ingestion result must have one relation per accepted address."
            )
        for relation in self.relations:
            self._require_ingested_relation(relation, address_values)
        if not isinstance(self.rejected_rows, tuple) or any(
            not isinstance(row, ResearchDnsLookupRejectedRow)
            for row in self.rejected_rows
        ):
            raise ResearchError("DNS ingestion result rejected rows are invalid.")

    def _require_ingested_observation(
        self, observation: object, kind: ResearchAssetKind
    ) -> None:
        if not isinstance(observation, ResearchAssetObservationRecord):
            raise ResearchError("DNS ingestion result observation is invalid.")
        if observation.program_id != self.program_id:
            raise ResearchError(
                "DNS ingestion result observation belongs to a different program."
            )
        if observation.kind is not kind:
            raise ResearchError("DNS ingestion result observation kind is wrong.")
        if (
            observation.provenance
            is not ResearchAssetProvenanceKind.KALI_OPERATION_RESULT
            or observation.source_operation_digest != self.operation_digest
        ):
            raise ResearchError(
                "DNS ingestion result observation is not bound to this operation."
            )

    def _require_ingested_relation(
        self, relation: object, address_values: set[str]
    ) -> None:
        if not isinstance(relation, ResearchAssetRelationRecord):
            raise ResearchError("DNS ingestion result relation is invalid.")
        if relation.program_id != self.program_id:
            raise ResearchError(
                "DNS ingestion result relation belongs to a different program."
            )
        if relation.kind is not ResearchAssetRelationKind.RESOLVES_TO:
            raise ResearchError("DNS ingestion result relation kind is wrong.")
        if (
            relation.source_kind is not ResearchAssetKind.HOSTNAME
            or relation.source_value != self.hostname_observation.canonical_value
        ):
            raise ResearchError(
                "DNS ingestion result relation does not source the queried hostname."
            )
        if (
            relation.related_kind is not ResearchAssetKind.IP_ADDRESS
            or relation.related_value not in address_values
        ):
            raise ResearchError(
                "DNS ingestion result relation does not target an ingested address."
            )
        if (
            relation.provenance is not ResearchAssetProvenanceKind.KALI_OPERATION_RESULT
            or relation.source_operation_digest != self.operation_digest
        ):
            raise ResearchError(
                "DNS ingestion result relation is not bound to this operation."
            )
