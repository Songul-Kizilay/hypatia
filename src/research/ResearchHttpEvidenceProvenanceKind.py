"""Who or what attested one recorded HTTP evidence record.

Exactly one answer exists today. `KALI_OPERATION_RESULT` names the one real
automated producer that exists: a completed, authorization-gated
`ResearchKaliOperationRun` whose `HTTPS_HEADER_LOOKUP` result has been parsed
by `research.ResearchHttpsHeaderLookupResultParser` into structured header
facts. This milestone builds no operator-authored HTTP evidence path, so a
second member would exist only for symmetry — the exact discipline
`ResearchAssetProvenanceKind` itself was built under before recon-result
ingestion existed.

Kept as its own narrow type rather than reusing `ResearchAssetProvenanceKind`:
HTTP evidence is a distinct concept from an asset observation, and conflating
the two enums would let an unrelated future asset-provenance member silently
become "valid" HTTP evidence provenance.
"""

from __future__ import annotations

from enum import StrEnum


class ResearchHttpEvidenceProvenanceKind(StrEnum):
    """Name the attested source of one recorded HTTP evidence record."""

    KALI_OPERATION_RESULT = "kali_operation_result"
