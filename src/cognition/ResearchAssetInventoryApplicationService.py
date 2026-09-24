"""Brain-facing boundary for the Bug Bounty asset inventory.

Records operator-authored observations/relations
(`ResearchAssetProvenanceKind.OPERATOR_AUTHORED`) and, since the DNS lookup
ingestion slice, structured facts parsed from one already-completed,
authorization-gated `ResearchKaliOperationRun`
(`ResearchAssetProvenanceKind.KALI_OPERATION_RESULT`). This service itself
performs no DNS lookup, no fetch, no process, and no model call — ingestion
only ever reads facts a Kali runner already produced and an operator already
authorized and ran; it never triggers a new one. Scope resolution is always a
fresh call into the unchanged `ResearchTargetScope.resolve_hostname`/
`resolve_addresses` against a caller-supplied *currently active*
`ResearchProgramScopeRevision` — never cached, never persisted, and never
substituted for a live check. Asset existence, a recorded observation, or a
`RESOLVES_TO` relation is never by itself sufficient grounds for any
authorization or execution decision.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from core.Exceptions import ResearchError
from research.JsonFileResearchAssetInventoryStore import (
    ResearchAssetInventoryDocument,
)
from research.ResearchAsset import ResearchAsset, assets_for_program
from research.ResearchAssetDnsIngestion import (
    ResearchAssetDnsIngestionAddressPreview,
    ResearchAssetDnsIngestionAssetPreview,
    ResearchAssetDnsIngestionPreview,
    ResearchAssetDnsIngestionResult,
)
from research.ResearchAssetInventoryEntry import (
    ResearchAssetInventoryEntry,
    ResearchAssetScopeResolutionView,
)
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchAssetObservationRecord import (
    ResearchAssetObservationRecord,
    canonicalize_asset_value,
)
from research.ResearchAssetProvenanceKind import ResearchAssetProvenanceKind
from research.ResearchAssetRelationKind import ResearchAssetRelationKind
from research.ResearchAssetRelationRecord import ResearchAssetRelationRecord
from research.ResearchDnsLookupResultParser import parse_dns_lookup_result
from research.ResearchKaliOperationExecution import ResearchKaliOperationRun
from research.ResearchProgramScopeRevision import ResearchProgramScopeRevision
from response.ResponseComposer import ResponseComposer

RESEARCH_ASSET_OBSERVATION_RECORD_INTENT = "research_asset_observation_record"
RESEARCH_ASSET_RELATION_RECORD_INTENT = "research_asset_relation_record"
RESEARCH_ASSET_INVENTORY_PREVIEW_INTENT = "research_asset_inventory_preview"
RESEARCH_ASSET_DNS_INGESTION_PREVIEW_INTENT = "research_asset_dns_ingestion_preview"
RESEARCH_ASSET_DNS_INGESTION_RECORD_INTENT = "research_asset_dns_ingestion_record"


class ResearchAssetInventoryStore(Protocol):
    def load(self) -> ResearchAssetInventoryDocument: ...

    def save(self, document: ResearchAssetInventoryDocument) -> None: ...


class ActiveProgramScopeRevisionReader(Protocol):
    """Read-only view of the program-scope revision history.

    Deliberately narrower than `ResearchProgramScopeRevisionStore`, which also
    exposes `save`. This service has no authority of its own and must never be
    able to write the authority history it reads, so it asks for exactly the
    one method it uses. Structural typing keeps the real store compatible.
    """

    def load(self) -> list[ResearchProgramScopeRevision]: ...


class ResearchAssetInventoryApplicationService:
    """Record operator-authored asset observations/relations; derive read models."""

    def __init__(
        self,
        store: ResearchAssetInventoryStore,
        response_composer: ResponseComposer,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
        program_scope_revision_store: ActiveProgramScopeRevisionReader | None = None,
    ) -> None:
        self._store = store
        self._response_composer = response_composer
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or (lambda: str(uuid4()))
        self._program_scope_revision_store = program_scope_revision_store

    # -- durable writes ----------------------------------------------------

    def record_observation(
        self,
        program_id: str,
        kind: ResearchAssetKind,
        value: str,
        note: str = "",
        provenance: ResearchAssetProvenanceKind = (
            ResearchAssetProvenanceKind.OPERATOR_AUTHORED
        ),
        source_operation_digest: str | None = None,
    ) -> ResearchAssetObservationRecord:
        """Canonicalize raw operator input once, then append one observation.

        This is the one place raw, possibly-uncanonical operator input
        becomes canonical; every record type downstream fails closed if it is
        ever given something that is not already canonical.
        """
        canonical_value = canonicalize_asset_value(kind, value)
        observation = ResearchAssetObservationRecord(
            observation_id=self._new_id(),
            program_id=program_id,
            kind=kind,
            canonical_value=canonical_value,
            provenance=provenance,
            note=note,
            recorded_at=self._now(),
            source_operation_digest=source_operation_digest,
        )
        document = self._load()
        if any(
            existing.observation_id == observation.observation_id
            for existing in document.observations
        ):
            raise ResearchError("Asset observation identity already exists.")
        self._save(
            ResearchAssetInventoryDocument(
                observations=(*document.observations, observation),
                relations=document.relations,
            )
        )
        return observation

    def record_relation(
        self,
        program_id: str,
        source_kind: ResearchAssetKind,
        source_value: str,
        related_kind: ResearchAssetKind,
        related_value: str,
        kind: ResearchAssetRelationKind,
        note: str = "",
        provenance: ResearchAssetProvenanceKind = (
            ResearchAssetProvenanceKind.OPERATOR_AUTHORED
        ),
        source_operation_digest: str | None = None,
    ) -> ResearchAssetRelationRecord:
        """Append one relation between two assets already observed in this program.

        `source_value`/`related_value` must already be exactly canonical —
        this method never normalizes them, matching the "record must already
        be canonical" discipline the record type itself enforces.
        """
        relation = ResearchAssetRelationRecord(
            relation_id=self._new_id(),
            program_id=program_id,
            source_kind=source_kind,
            source_value=source_value,
            related_kind=related_kind,
            related_value=related_value,
            kind=kind,
            provenance=provenance,
            note=note,
            recorded_at=self._now(),
            source_operation_digest=source_operation_digest,
        )
        document = self._load()
        if not self._has_observation(
            document.observations,
            relation.program_id,
            relation.source_kind,
            relation.source_value,
        ):
            raise ResearchError(
                "Asset relation source has no recorded observation in this program."
            )
        if not self._has_observation(
            document.observations,
            relation.program_id,
            relation.related_kind,
            relation.related_value,
        ):
            raise ResearchError(
                "Asset relation target has no recorded observation in this program."
            )
        if any(
            existing.relation_id == relation.relation_id
            for existing in document.relations
        ):
            raise ResearchError("Asset relation identity already exists.")
        self._save(
            ResearchAssetInventoryDocument(
                observations=document.observations,
                relations=(*document.relations, relation),
            )
        )
        return relation

    def record_dns_ingestion(
        self, run: ResearchKaliOperationRun
    ) -> ResearchAssetDnsIngestionResult:
        """Confirm one DNS lookup run's parsed result into durable observations.

        Always uses `run.program_id` — never a separately supplied program
        ID — so program isolation is structural, not a runtime check that
        could be bypassed. Every write is stamped
        `provenance=KALI_OPERATION_RESULT` with
        `source_operation_digest=run.operation_digest`. Recording the same
        run's result again only grows the observation/relation log; it never
        creates a second canonical asset (`assets_for_program` groups by
        canonical value, not by how many times it was observed).
        """
        if not isinstance(run, ResearchKaliOperationRun):
            raise ResearchError("Kali operation run is invalid.")
        parsed = parse_dns_lookup_result(run)
        hostname_observation = self.record_observation(
            run.program_id,
            ResearchAssetKind.HOSTNAME,
            parsed.hostname,
            note=f"Queried via a Kali DNS {parsed.record_type.value} lookup.",
            provenance=ResearchAssetProvenanceKind.KALI_OPERATION_RESULT,
            source_operation_digest=run.operation_digest,
        )
        address_observations: list[ResearchAssetObservationRecord] = []
        relations: list[ResearchAssetRelationRecord] = []
        for address in parsed.accepted_addresses:
            address_observations.append(
                self.record_observation(
                    run.program_id,
                    ResearchAssetKind.IP_ADDRESS,
                    address,
                    note=(
                        f"Resolved via a Kali DNS {parsed.record_type.value}"
                        f" lookup for {parsed.hostname}."
                    ),
                    provenance=ResearchAssetProvenanceKind.KALI_OPERATION_RESULT,
                    source_operation_digest=run.operation_digest,
                )
            )
            relations.append(
                self.record_relation(
                    run.program_id,
                    ResearchAssetKind.HOSTNAME,
                    parsed.hostname,
                    ResearchAssetKind.IP_ADDRESS,
                    address,
                    ResearchAssetRelationKind.RESOLVES_TO,
                    note=f"Kali DNS {parsed.record_type.value} lookup result.",
                    provenance=ResearchAssetProvenanceKind.KALI_OPERATION_RESULT,
                    source_operation_digest=run.operation_digest,
                )
            )
        return ResearchAssetDnsIngestionResult(
            program_id=run.program_id,
            operation_digest=run.operation_digest,
            hostname_observation=hostname_observation,
            address_observations=tuple(address_observations),
            relations=tuple(relations),
            rejected_rows=parsed.rejected_rows,
        )

    # -- derived read models -------------------------------------------------

    def assets_for_program(self, program_id: str) -> tuple[ResearchAsset, ...]:
        """Recompute this program's assets fresh from the persisted log."""
        document = self._load()
        return assets_for_program(program_id, document.observations)

    def relations_for_program(
        self, program_id: str
    ) -> tuple[ResearchAssetRelationRecord, ...]:
        """Return this program's recorded relations, in persisted order."""
        normalized = self._normalize_program_id(program_id)
        document = self._load()
        return tuple(
            relation
            for relation in document.relations
            if relation.program_id == normalized
        )

    def preview_dns_ingestion(
        self, run: ResearchKaliOperationRun
    ) -> ResearchAssetDnsIngestionPreview:
        """Side-effect-free preview of what confirming `run` would record.

        Mirrors `kali_operation_evidence_candidate_for_run`'s discipline:
        reading the current inventory to report what is already known is not
        a durable write, and `observations_recorded`/`relations_recorded` are
        hard-pinned `False` on the returned preview.
        """
        if not isinstance(run, ResearchKaliOperationRun):
            raise ResearchError("Kali operation run is invalid.")
        parsed = parse_dns_lookup_result(run)
        document = self._load()
        hostname_asset = ResearchAssetDnsIngestionAssetPreview(
            kind=ResearchAssetKind.HOSTNAME,
            canonical_value=parsed.hostname,
            already_known=self._has_observation(
                document.observations,
                run.program_id,
                ResearchAssetKind.HOSTNAME,
                parsed.hostname,
            ),
        )
        address_assets = tuple(
            ResearchAssetDnsIngestionAddressPreview(
                asset=ResearchAssetDnsIngestionAssetPreview(
                    kind=ResearchAssetKind.IP_ADDRESS,
                    canonical_value=address,
                    already_known=self._has_observation(
                        document.observations,
                        run.program_id,
                        ResearchAssetKind.IP_ADDRESS,
                        address,
                    ),
                ),
                resolves_to_relation_already_known=self._has_relation(
                    document.relations, run.program_id, parsed.hostname, address
                ),
            )
            for address in parsed.accepted_addresses
        )
        return ResearchAssetDnsIngestionPreview(
            program_id=run.program_id,
            operation_digest=run.operation_digest,
            hostname_asset=hostname_asset,
            record_type=parsed.record_type,
            address_assets=address_assets,
            rejected_rows=parsed.rejected_rows,
        )

    @staticmethod
    def current_scope_resolution(
        asset: ResearchAsset,
        active_revision: ResearchProgramScopeRevision | None,
    ) -> ResearchAssetScopeResolutionView:
        """Dispatch to the unchanged live resolver; never persisted, never cached.

        Returns an explicit "no active scope revision for this program"
        signal when `active_revision` is `None`, rather than fabricating a
        resolution. A `RESOLVES_TO` relation involving `asset` plays no part
        in this computation.
        """
        if not isinstance(asset, ResearchAsset):
            raise ResearchError("Asset scope resolution requires a valid asset.")
        if active_revision is None:
            return ResearchAssetScopeResolutionView(
                has_active_scope_revision=False, resolution=None
            )
        if not isinstance(active_revision, ResearchProgramScopeRevision):
            raise ResearchError(
                "Asset scope resolution requires a valid scope revision."
            )
        if active_revision.program_id != asset.program_id:
            raise ResearchError(
                "Asset scope resolution requires a revision for the same program."
            )
        if asset.kind is ResearchAssetKind.HOSTNAME:
            resolution = active_revision.scope.resolve_hostname(asset.canonical_value)
        elif asset.kind is ResearchAssetKind.IP_ADDRESS:
            # Named explicitly rather than as an `else`, so a future asset kind
            # fails closed here instead of silently inheriting address rules.
            (resolution,) = active_revision.scope.resolve_addresses(
                (asset.canonical_value,)
            )
        else:
            raise ResearchError("Asset kind is not resolvable against scope.")
        return ResearchAssetScopeResolutionView(
            has_active_scope_revision=True, resolution=resolution
        )

    # -- Brain intents -------------------------------------------------------

    @staticmethod
    def is_observation_record_request(request: BrainRequest) -> bool:
        return (
            request.metadata.get("intent") == RESEARCH_ASSET_OBSERVATION_RECORD_INTENT
        )

    @staticmethod
    def is_relation_record_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == RESEARCH_ASSET_RELATION_RECORD_INTENT

    @staticmethod
    def is_inventory_preview_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == RESEARCH_ASSET_INVENTORY_PREVIEW_INTENT

    @staticmethod
    def is_dns_ingestion_preview_request(request: BrainRequest) -> bool:
        return (
            request.metadata.get("intent")
            == RESEARCH_ASSET_DNS_INGESTION_PREVIEW_INTENT
        )

    @staticmethod
    def is_dns_ingestion_record_request(request: BrainRequest) -> bool:
        return (
            request.metadata.get("intent") == RESEARCH_ASSET_DNS_INGESTION_RECORD_INTENT
        )

    def process_observation_record(self, request: BrainRequest) -> BrainResponse:
        try:
            program_id = request.metadata.get("program_id")
            kind = request.metadata.get("kind")
            value = request.metadata.get("value")
            note = request.metadata.get("note", "")
            # Provenance is never taken from the request. A hand-typed desktop
            # value is operator-authored by construction, and reading it from
            # metadata would be a ready-made seam for claiming tool
            # attestation the moment recon ingestion adds a second member.
            provenance = ResearchAssetProvenanceKind.OPERATOR_AUTHORED
            if not isinstance(program_id, str):
                raise ResearchError("Asset observation requires a program ID.")
            if not isinstance(kind, ResearchAssetKind):
                raise ResearchError("Asset observation requires a valid kind.")
            if not isinstance(value, str):
                raise ResearchError("Asset observation requires an explicit value.")
            if not isinstance(note, str):
                raise ResearchError("Asset observation note is invalid.")
            if not isinstance(provenance, ResearchAssetProvenanceKind):
                raise ResearchError("Asset observation provenance is invalid.")
            observation = self.record_observation(
                program_id, kind, value, note, provenance
            )
        except ResearchError as error:
            return self._response_composer.research_asset_observation_record_failure(
                request, str(error)
            )
        return self._response_composer.research_asset_observation_record(
            request, observation
        )

    def process_relation_record(self, request: BrainRequest) -> BrainResponse:
        try:
            program_id = request.metadata.get("program_id")
            source_kind = request.metadata.get("source_kind")
            source_value = request.metadata.get("source_value")
            related_kind = request.metadata.get("related_kind")
            related_value = request.metadata.get("related_value")
            kind = request.metadata.get("kind")
            note = request.metadata.get("note", "")
            if not isinstance(program_id, str):
                raise ResearchError("Asset relation requires a program ID.")
            if not isinstance(source_kind, ResearchAssetKind) or not isinstance(
                related_kind, ResearchAssetKind
            ):
                raise ResearchError("Asset relation requires valid asset kinds.")
            if not isinstance(source_value, str) or not isinstance(related_value, str):
                raise ResearchError("Asset relation requires explicit values.")
            if not isinstance(kind, ResearchAssetRelationKind):
                raise ResearchError("Asset relation requires a valid relation kind.")
            if not isinstance(note, str):
                raise ResearchError("Asset relation note is invalid.")
            relation = self.record_relation(
                program_id,
                source_kind,
                source_value,
                related_kind,
                related_value,
                kind,
                note,
            )
        except ResearchError as error:
            return self._response_composer.research_asset_relation_record_failure(
                request, str(error)
            )
        return self._response_composer.research_asset_relation_record(request, relation)

    def process_inventory_preview(self, request: BrainRequest) -> BrainResponse:
        try:
            program_id = request.metadata.get("program_id")
            if not isinstance(program_id, str) or not program_id.strip():
                raise ResearchError("Asset inventory preview requires a program ID.")
            active_revision = self._active_revision_for_program(program_id)
            assets = self.assets_for_program(program_id)
            relations = self.relations_for_program(program_id)
            entries = tuple(
                ResearchAssetInventoryEntry(
                    asset=asset,
                    scope=self.current_scope_resolution(asset, active_revision),
                )
                for asset in assets
            )
        except ResearchError as error:
            return self._response_composer.research_asset_inventory_preview_failure(
                request, str(error)
            )
        return self._response_composer.research_asset_inventory_preview(
            request, entries, relations
        )

    def process_dns_ingestion_preview(self, request: BrainRequest) -> BrainResponse:
        try:
            run = request.metadata.get("kali_operation_run")
            if not isinstance(run, ResearchKaliOperationRun):
                raise ResearchError(
                    "DNS ingestion preview requires a completed Kali operation run."
                )
            preview = self.preview_dns_ingestion(run)
        except ResearchError as error:
            return self._response_composer.research_asset_dns_ingestion_preview_failure(
                request, str(error)
            )
        return self._response_composer.research_asset_dns_ingestion_preview(
            request, preview
        )

    def process_dns_ingestion_record(self, request: BrainRequest) -> BrainResponse:
        try:
            run = request.metadata.get("kali_operation_run")
            if not isinstance(run, ResearchKaliOperationRun):
                raise ResearchError(
                    "DNS ingestion record requires a completed Kali operation run."
                )
            result = self.record_dns_ingestion(run)
        except ResearchError as error:
            return self._response_composer.research_asset_dns_ingestion_record_failure(
                request, str(error)
            )
        return self._response_composer.research_asset_dns_ingestion_record(
            request, result
        )

    # -- internals -------------------------------------------------------

    def _load(self) -> ResearchAssetInventoryDocument:
        try:
            return self._store.load()
        except ResearchError:
            raise
        except Exception as error:
            raise ResearchError("Unable to restore the asset inventory.") from error

    def _save(self, document: ResearchAssetInventoryDocument) -> None:
        try:
            self._store.save(document)
        except ResearchError:
            raise
        except Exception as error:
            raise ResearchError("Unable to persist the asset inventory.") from error

    def _new_id(self) -> str:
        value = self._id_factory()
        if not isinstance(value, str) or not value.strip():
            raise ResearchError("Asset inventory identifier cannot be empty.")
        return value

    def _now(self) -> datetime:
        value = self._clock()
        if not isinstance(value, datetime) or value.utcoffset() is None:
            raise ResearchError("Asset inventory clock must be timezone-aware.")
        return value.astimezone(UTC)

    def _active_revision_for_program(
        self, program_id: str
    ) -> ResearchProgramScopeRevision | None:
        """Look up the one currently-valid scope revision fresh, never cached.

        Returns `None` (never a fabricated or stale resolution) when no
        program-scope revision store is wired, or when this program has no
        revision that is confirmed, unexpired, and unrevoked right now.
        """
        if self._program_scope_revision_store is None:
            return None
        normalized = self._normalize_program_id(program_id)
        now = self._now()
        matches = [
            revision
            for revision in self._program_scope_revision_store.load()
            if revision.program_id == normalized and revision.valid_at(now)
        ]
        if len(matches) > 1:
            raise ResearchError("Program scope revision history is contradictory.")
        return matches[0] if matches else None

    @staticmethod
    def _normalize_program_id(program_id: str) -> str:
        if not isinstance(program_id, str) or not program_id.strip():
            raise ResearchError("Asset inventory program ID cannot be empty.")
        return program_id.strip()

    @staticmethod
    def _has_observation(
        observations: tuple[ResearchAssetObservationRecord, ...],
        program_id: str,
        kind: ResearchAssetKind,
        canonical_value: str,
    ) -> bool:
        return any(
            observation.program_id == program_id
            and observation.kind == kind
            and observation.canonical_value == canonical_value
            for observation in observations
        )

    @staticmethod
    def _has_relation(
        relations: tuple[ResearchAssetRelationRecord, ...],
        program_id: str,
        hostname: str,
        address: str,
    ) -> bool:
        return any(
            relation.program_id == program_id
            and relation.kind == ResearchAssetRelationKind.RESOLVES_TO
            and relation.source_kind == ResearchAssetKind.HOSTNAME
            and relation.source_value == hostname
            and relation.related_kind == ResearchAssetKind.IP_ADDRESS
            and relation.related_value == address
            for relation in relations
        )
