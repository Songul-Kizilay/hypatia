"""Preview and confirmed-write results for ingesting one HTTPS header lookup run.

Kept in `research/`, not alongside the application service that builds them,
matching `ResearchAssetDnsIngestion.py`'s existing separation: so
`brain.BrainResponse` can reference these types without a cognition-layer
import cycle.

`ResearchHttpEvidenceIngestionPreview` is side-effect-free — it never claims a
write happened, mirroring `ResearchKaliOperationEvidenceCandidate`'s
`evidence_recorded` discipline. `ResearchHttpEvidenceIngestionResult` is only
ever constructed from a record a durable write (or an idempotent replay hit)
already produced; `already_recorded` distinguishes "this exact event already
existed" from "this write just created a new event," so an operator — and a
test — can tell the two apart without a second store read.

Both carry a `scope: ResearchAssetScopeResolutionView` — the target's current
live scope reading, computed the same way `ResearchAssetInventoryApplicationService
.current_scope_resolution` computes it for an asset, never cached or restored
from storage. Ingesting or previewing HTTP evidence never changes this
reading; it is always a fresh dispatch into the unchanged
`ResearchTargetScope.resolve_hostname`.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchAssetInventoryEntry import ResearchAssetScopeResolutionView
from research.ResearchHttpEvidenceRecord import (
    ResearchHttpEvidenceRecord,
    is_http_evidence_id,
)
from research.ResearchHttpHeaderRecord import ResearchHttpHeaderRecord
from research.ResearchHttpsHeaderLookupResultParser import (
    ResearchHttpsHeaderLookupRejectedLine,
)
from research.ResearchKaliOperationPreview import is_kali_operation_digest

MAX_HTTP_EVIDENCE_INGESTION_PROGRAM_ID_CHARACTERS = 200


@dataclass(frozen=True, slots=True)
class ResearchHttpEvidenceIngestionPreview:
    """A complete, side-effect-free preview of ingesting one HTTPS header run.

    `evidence_recorded` is hard-pinned `False`, mirroring
    `ResearchKaliOperationEvidenceCandidate`: this type gives the operator a
    bounded view without ever claiming a durable write happened.
    """

    program_id: str
    operation_digest: str
    evidence_id: str
    hostname: str
    status_code: int | None
    headers: tuple[ResearchHttpHeaderRecord, ...]
    rejected_lines: tuple[ResearchHttpsHeaderLookupRejectedLine, ...]
    already_recorded: bool
    scope: ResearchAssetScopeResolutionView
    evidence_recorded: bool = False

    def __post_init__(self) -> None:
        if (
            not isinstance(self.program_id, str)
            or not self.program_id.strip()
            or len(self.program_id) > MAX_HTTP_EVIDENCE_INGESTION_PROGRAM_ID_CHARACTERS
        ):
            raise ResearchError("HTTP evidence ingestion preview program ID invalid.")
        if not is_kali_operation_digest(self.operation_digest):
            raise ResearchError(
                "HTTP evidence ingestion preview operation digest is invalid."
            )
        if not is_http_evidence_id(self.evidence_id):
            raise ResearchError(
                "HTTP evidence ingestion preview evidence ID is invalid."
            )
        if not isinstance(self.hostname, str) or not self.hostname:
            raise ResearchError(
                "HTTP evidence ingestion preview hostname cannot be empty."
            )
        if self.status_code is not None:
            if isinstance(self.status_code, bool) or not isinstance(
                self.status_code, int
            ):
                raise ResearchError(
                    "HTTP evidence ingestion preview status code is invalid."
                )
        if not isinstance(self.headers, tuple) or any(
            not isinstance(header, ResearchHttpHeaderRecord) for header in self.headers
        ):
            raise ResearchError("HTTP evidence ingestion preview headers are invalid.")
        if not isinstance(self.rejected_lines, tuple) or any(
            not isinstance(row, ResearchHttpsHeaderLookupRejectedLine)
            for row in self.rejected_lines
        ):
            raise ResearchError(
                "HTTP evidence ingestion preview rejected lines are invalid."
            )
        if not isinstance(self.already_recorded, bool):
            raise ResearchError(
                "HTTP evidence ingestion preview known flag must be boolean."
            )
        if self.evidence_recorded is not False:
            raise ResearchError(
                "HTTP evidence ingestion preview must not claim a write."
            )
        if not isinstance(self.scope, ResearchAssetScopeResolutionView):
            raise ResearchError(
                "HTTP evidence ingestion preview requires a valid scope resolution"
                " view."
            )


@dataclass(frozen=True, slots=True)
class ResearchHttpEvidenceIngestionResult:
    """What one confirmed HTTP evidence ingestion actually recorded (or replayed).

    `already_recorded` is `True` exactly when the exact same event (identical
    `evidence_id`) was already stored before this call — in that case nothing
    new was written; `record` is simply the pre-existing one, returned rather
    than duplicated.
    """

    record: ResearchHttpEvidenceRecord
    already_recorded: bool
    scope: ResearchAssetScopeResolutionView

    def __post_init__(self) -> None:
        if not isinstance(self.record, ResearchHttpEvidenceRecord):
            raise ResearchError("HTTP evidence ingestion result record is invalid.")
        if not isinstance(self.already_recorded, bool):
            raise ResearchError(
                "HTTP evidence ingestion result known flag must be boolean."
            )
        if not isinstance(self.scope, ResearchAssetScopeResolutionView):
            raise ResearchError(
                "HTTP evidence ingestion result requires a valid scope resolution"
                " view."
            )
