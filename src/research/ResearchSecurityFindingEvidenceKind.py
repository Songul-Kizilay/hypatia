"""What kind of evidence one security finding evidence link cites.

Exactly one member: HTTP Evidence is the only evidence kind the Finding
Lifecycle handles this milestone. This is deliberately its own enum, not a
re-export of `ResearchSecurityHypothesisEvidenceKind` — this codebase's own
convention (`ResearchAssetProvenanceKind` vs
`ResearchHttpEvidenceProvenanceKind`) is that each record type owns its
evidence/provenance vocabulary independently even where two enums currently
hold the same one member, so the two subsystems' evidence vocabularies can
evolve independently later.
"""

from __future__ import annotations

from enum import StrEnum


class ResearchSecurityFindingEvidenceKind(StrEnum):
    """Name the kind of evidence record one finding evidence link cites."""

    HTTP_EVIDENCE = "http_evidence"
