"""Read-only HTTP evidence listing for one target — always recomputed, never stored.

Kept in `research/`, not alongside the application service that builds it, so
`brain.BrainResponse` can reference this type without a cognition-layer import
cycle (mirrors `ResearchAssetInventoryEntry.py`'s existing separation).
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchAssetInventoryEntry import ResearchAssetScopeResolutionView
from research.ResearchHttpEvidenceRecord import ResearchHttpEvidenceRecord


@dataclass(frozen=True, slots=True)
class ResearchHttpEvidenceForTargetView:
    """One target's stored HTTP evidence events, paired with a live scope reading.

    `records` is exactly what is persisted — this view performs no fetch, no
    scan, and no write. `scope` is always freshly recomputed against the
    currently active program scope revision, never cached or restored from
    storage; recording or reading HTTP evidence never changes it.
    """

    program_id: str
    canonical_hostname: str
    records: tuple[ResearchHttpEvidenceRecord, ...]
    scope: ResearchAssetScopeResolutionView

    def __post_init__(self) -> None:
        if not isinstance(self.program_id, str) or not self.program_id.strip():
            raise ResearchError("HTTP evidence target view program ID cannot be empty.")
        if not isinstance(self.canonical_hostname, str) or not self.canonical_hostname:
            raise ResearchError("HTTP evidence target view hostname cannot be empty.")
        if not isinstance(self.records, tuple) or any(
            not isinstance(record, ResearchHttpEvidenceRecord)
            for record in self.records
        ):
            raise ResearchError("HTTP evidence target view records are invalid.")
        for record in self.records:
            if record.program_id != self.program_id:
                raise ResearchError(
                    "HTTP evidence target view record belongs to a different"
                    " program."
                )
            if record.target_canonical_value != self.canonical_hostname:
                raise ResearchError(
                    "HTTP evidence target view record targets a different" " hostname."
                )
        if not isinstance(self.scope, ResearchAssetScopeResolutionView):
            raise ResearchError(
                "HTTP evidence target view requires a valid scope resolution view."
            )
