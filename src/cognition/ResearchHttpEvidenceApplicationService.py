"""Brain-facing boundary for HTTP evidence derived from Kali operation results.

Consumes one already-completed, authorization-gated `ResearchKaliOperationRun`
whose `HTTPS_HEADER_LOOKUP` result has been parsed by
`research.ResearchHttpsHeaderLookupResultParser`. This service itself performs
no HTTP request, no process, and no model call — ingestion only ever reads
facts a Kali runner already produced and an operator already authorized and
ran; it never triggers a new one. Scope resolution is always a fresh call into
the unchanged `ResearchTargetScope.resolve_hostname` against a caller-supplied
*currently active* `ResearchProgramScopeRevision` — never cached, never
persisted, and never substituted for a live check. Recorded HTTP evidence is
never by itself sufficient grounds for any authorization or execution
decision, and a `Location` header is never followed or treated as scope input
here or anywhere downstream.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from core.Exceptions import ResearchError
from research.JsonFileResearchHttpEvidenceStore import ResearchHttpEvidenceDocument
from research.ResearchAssetInventoryEntry import ResearchAssetScopeResolutionView
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchHttpEvidenceForTargetView import (
    ResearchHttpEvidenceForTargetView,
)
from research.ResearchHttpEvidenceIngestion import (
    ResearchHttpEvidenceIngestionPreview,
    ResearchHttpEvidenceIngestionResult,
)
from research.ResearchHttpEvidenceProvenanceKind import (
    ResearchHttpEvidenceProvenanceKind,
)
from research.ResearchHttpEvidenceRecord import (
    ResearchHttpEvidenceRecord,
    http_evidence_id,
)
from research.ResearchHttpsHeaderLookupResultParser import (
    parse_https_header_lookup_result,
)
from research.ResearchKaliOperationExecution import ResearchKaliOperationRun
from research.ResearchProgramScopeRevision import ResearchProgramScopeRevision
from research.ResearchTargetScope import canonical_dns_hostname
from response.ResponseComposer import ResponseComposer

RESEARCH_HTTP_EVIDENCE_INGESTION_PREVIEW_INTENT = (
    "research_http_evidence_ingestion_preview"
)
RESEARCH_HTTP_EVIDENCE_INGESTION_RECORD_INTENT = (
    "research_http_evidence_ingestion_record"
)
RESEARCH_HTTP_EVIDENCE_FOR_TARGET_INTENT = "research_http_evidence_for_target"


class ResearchHttpEvidenceStore(Protocol):
    def load(self) -> ResearchHttpEvidenceDocument: ...

    def save(self, document: ResearchHttpEvidenceDocument) -> None: ...


class ActiveProgramScopeRevisionReader(Protocol):
    """Read-only view of the program-scope revision history.

    Deliberately narrower than a revision store that can also `save`, so this
    service can never write the authority history it reads. Structural typing
    keeps the real store compatible.
    """

    def load(self) -> list[ResearchProgramScopeRevision]: ...


class ResearchHttpEvidenceApplicationService:
    """Ingest structured HTTP evidence from completed Kali runs; derive read models."""

    def __init__(
        self,
        store: ResearchHttpEvidenceStore,
        response_composer: ResponseComposer,
        *,
        clock: Callable[[], datetime] | None = None,
        program_scope_revision_store: ActiveProgramScopeRevisionReader | None = None,
    ) -> None:
        self._store = store
        self._response_composer = response_composer
        self._clock = clock or (lambda: datetime.now(UTC))
        self._program_scope_revision_store = program_scope_revision_store

    # -- side-effect-free preview / durable write ----------------------------

    def preview_https_header_evidence_ingestion(
        self, run: ResearchKaliOperationRun
    ) -> ResearchHttpEvidenceIngestionPreview:
        """Side-effect-free preview of what confirming `run` would record.

        Mirrors `kali_operation_evidence_candidate_for_run`'s discipline:
        reading the current store to report whether this exact event is
        already known is not a durable write, and `evidence_recorded` is
        hard-pinned `False` on the returned preview.
        """
        if not isinstance(run, ResearchKaliOperationRun):
            raise ResearchError("Kali operation run is invalid.")
        parsed = parse_https_header_lookup_result(run)
        evidence_id = self._evidence_id_for_run(run)
        return ResearchHttpEvidenceIngestionPreview(
            program_id=run.program_id,
            operation_digest=run.operation_digest,
            evidence_id=evidence_id,
            hostname=parsed.hostname,
            status_code=parsed.status_code,
            headers=parsed.headers,
            rejected_lines=parsed.rejected_lines,
            already_recorded=self._find_evidence(self._load(), evidence_id) is not None,
            scope=self._current_scope_for_target(run.program_id, parsed.hostname),
        )

    def record_https_header_evidence_ingestion(
        self, run: ResearchKaliOperationRun
    ) -> ResearchHttpEvidenceIngestionResult:
        """Confirm one HTTPS header lookup run's parsed result into durable evidence.

        Always uses `run.program_id` — never a separately supplied program ID
        — so program isolation is structural, not a runtime check that could
        be bypassed. The deterministic `evidence_id` is computed first; if
        that exact event is already stored, the existing record is returned
        unchanged and nothing new is written — this is what makes replay
        idempotent, not a separate dedup pass. A genuinely different response
        from the same reviewed operation (different exit code, timeout flag,
        or stdout) yields a different `evidence_id` and is preserved as a
        second, distinct event.
        """
        if not isinstance(run, ResearchKaliOperationRun):
            raise ResearchError("Kali operation run is invalid.")
        parsed = parse_https_header_lookup_result(run)
        evidence_id = self._evidence_id_for_run(run)
        document = self._load()
        existing = self._find_evidence(document, evidence_id)
        scope = self._current_scope_for_target(run.program_id, parsed.hostname)
        if existing is not None:
            return ResearchHttpEvidenceIngestionResult(
                record=existing, already_recorded=True, scope=scope
            )
        record = ResearchHttpEvidenceRecord(
            evidence_id=evidence_id,
            program_id=run.program_id,
            target_kind=ResearchAssetKind.HOSTNAME,
            target_canonical_value=parsed.hostname,
            scheme="https",
            port=443,
            path="/",
            request_method="HEAD",
            request_headers_observed=False,
            response_status_code=parsed.status_code,
            response_headers=parsed.headers,
            response_body_observed=False,
            provenance=ResearchHttpEvidenceProvenanceKind.KALI_OPERATION_RESULT,
            source_operation_digest=run.operation_digest,
            recorded_at=self._now(),
        )
        self._save(ResearchHttpEvidenceDocument(records=(*document.records, record)))
        return ResearchHttpEvidenceIngestionResult(
            record=record, already_recorded=False, scope=scope
        )

    # -- derived read models -------------------------------------------------

    def evidence_for_target(
        self, program_id: str, canonical_hostname: str
    ) -> tuple[ResearchHttpEvidenceRecord, ...]:
        """Return this program's stored HTTP evidence for one canonical hostname."""
        normalized_program_id = self._normalize_program_id(program_id)
        if not isinstance(
            canonical_hostname, str
        ) or canonical_hostname != canonical_dns_hostname(canonical_hostname):
            raise ResearchError("HTTP evidence lookup hostname is not canonical.")
        document = self._load()
        return tuple(
            record
            for record in document.records
            if record.program_id == normalized_program_id
            and record.target_canonical_value == canonical_hostname
        )

    @staticmethod
    def current_scope_resolution(
        canonical_hostname: str,
        program_id: str,
        active_revision: ResearchProgramScopeRevision | None,
    ) -> ResearchAssetScopeResolutionView:
        """Dispatch to the unchanged live resolver; never persisted, never cached.

        Returns an explicit "no active scope revision for this program" signal
        when `active_revision` is `None`, rather than fabricating a
        resolution. No stored HTTP evidence record — including any `Location`
        header text — plays any part in this computation.
        """
        if active_revision is None:
            return ResearchAssetScopeResolutionView(
                has_active_scope_revision=False, resolution=None
            )
        if not isinstance(active_revision, ResearchProgramScopeRevision):
            raise ResearchError(
                "HTTP evidence scope resolution requires a valid scope revision."
            )
        if active_revision.program_id != program_id:
            raise ResearchError(
                "HTTP evidence scope resolution requires a revision for the same"
                " program."
            )
        resolution = active_revision.scope.resolve_hostname(canonical_hostname)
        return ResearchAssetScopeResolutionView(
            has_active_scope_revision=True, resolution=resolution
        )

    # -- Brain intents -------------------------------------------------------

    @staticmethod
    def is_ingestion_preview_request(request: BrainRequest) -> bool:
        return (
            request.metadata.get("intent")
            == RESEARCH_HTTP_EVIDENCE_INGESTION_PREVIEW_INTENT
        )

    @staticmethod
    def is_ingestion_record_request(request: BrainRequest) -> bool:
        return (
            request.metadata.get("intent")
            == RESEARCH_HTTP_EVIDENCE_INGESTION_RECORD_INTENT
        )

    @staticmethod
    def is_evidence_for_target_request(request: BrainRequest) -> bool:
        return (
            request.metadata.get("intent") == RESEARCH_HTTP_EVIDENCE_FOR_TARGET_INTENT
        )

    def process_ingestion_preview(self, request: BrainRequest) -> BrainResponse:
        try:
            run = request.metadata.get("kali_operation_run")
            if not isinstance(run, ResearchKaliOperationRun):
                raise ResearchError(
                    "HTTP evidence ingestion preview requires a completed Kali"
                    " operation run."
                )
            preview = self.preview_https_header_evidence_ingestion(run)
        except ResearchError as error:
            composer = self._response_composer
            return composer.research_http_evidence_ingestion_preview_failure(
                request, str(error)
            )
        return self._response_composer.research_http_evidence_ingestion_preview(
            request, preview
        )

    def process_ingestion_record(self, request: BrainRequest) -> BrainResponse:
        try:
            run = request.metadata.get("kali_operation_run")
            if not isinstance(run, ResearchKaliOperationRun):
                raise ResearchError(
                    "HTTP evidence ingestion record requires a completed Kali"
                    " operation run."
                )
            result = self.record_https_header_evidence_ingestion(run)
        except ResearchError as error:
            composer = self._response_composer
            return composer.research_http_evidence_ingestion_record_failure(
                request, str(error)
            )
        return self._response_composer.research_http_evidence_ingestion_record(
            request, result
        )

    def process_evidence_for_target(self, request: BrainRequest) -> BrainResponse:
        try:
            program_id = request.metadata.get("program_id")
            hostname = request.metadata.get("hostname")
            if not isinstance(program_id, str) or not program_id.strip():
                raise ResearchError("HTTP evidence lookup requires a program ID.")
            if not isinstance(hostname, str) or not hostname.strip():
                raise ResearchError("HTTP evidence lookup requires a hostname.")
            normalized_program_id = self._normalize_program_id(program_id)
            canonical_hostname = canonical_dns_hostname(hostname)
            records = self.evidence_for_target(
                normalized_program_id, canonical_hostname
            )
            active_revision = self._active_revision_for_program(normalized_program_id)
            scope = self.current_scope_resolution(
                canonical_hostname, normalized_program_id, active_revision
            )
            view = ResearchHttpEvidenceForTargetView(
                program_id=normalized_program_id,
                canonical_hostname=canonical_hostname,
                records=records,
                scope=scope,
            )
        except ResearchError as error:
            return self._response_composer.research_http_evidence_for_target_failure(
                request, str(error)
            )
        return self._response_composer.research_http_evidence_for_target(request, view)

    # -- internals -------------------------------------------------------

    def _current_scope_for_target(
        self, program_id: str, canonical_hostname: str
    ) -> ResearchAssetScopeResolutionView:
        """Compute one target's live scope reading, fresh, for the preview/record path.

        Thin wrapper around `_active_revision_for_program`/
        `current_scope_resolution` so `preview_https_header_evidence_ingestion`/
        `record_https_header_evidence_ingestion` never fabricate or cache a
        resolution — every call re-queries the active revision store.
        """
        active_revision = self._active_revision_for_program(program_id)
        return self.current_scope_resolution(
            canonical_hostname, program_id, active_revision
        )

    @staticmethod
    def _evidence_id_for_run(run: ResearchKaliOperationRun) -> str:
        return http_evidence_id(
            program_id=run.program_id,
            operation_digest=run.operation_digest,
            exit_code=run.process_result.exit_code,
            timed_out=run.process_result.timed_out,
            stdout_lines=run.process_result.stdout_lines,
        )

    @staticmethod
    def _find_evidence(
        document: ResearchHttpEvidenceDocument, evidence_id: str
    ) -> ResearchHttpEvidenceRecord | None:
        for record in document.records:
            if record.evidence_id == evidence_id:
                return record
        return None

    def _load(self) -> ResearchHttpEvidenceDocument:
        try:
            return self._store.load()
        except ResearchError:
            raise
        except Exception as error:
            raise ResearchError("Unable to restore HTTP evidence.") from error

    def _save(self, document: ResearchHttpEvidenceDocument) -> None:
        try:
            self._store.save(document)
        except ResearchError:
            raise
        except Exception as error:
            raise ResearchError("Unable to persist HTTP evidence.") from error

    def _now(self) -> datetime:
        value = self._clock()
        if not isinstance(value, datetime) or value.utcoffset() is None:
            raise ResearchError("HTTP evidence clock must be timezone-aware.")
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
            raise ResearchError("HTTP evidence program ID cannot be empty.")
        return program_id.strip()
