"""How one cited evidence record bears on a security finding.

Three disjoint relations, never netted against each other, mirroring
`ResearchSecurityHypothesisEvidenceRelation`'s own supporting/contradicting
discipline plus one addition this milestone needs: `VALIDATES`, the one and
only real gate for the `VALIDATED` status
(`ResearchSecurityFindingStatus.VALIDATED`; see
`cognition.ResearchSecurityFindingApplicationService.transition_status`).
This is deliberately its own enum, not a widened
`ResearchSecurityHypothesisEvidenceRelation` (which stays exactly `SUPPORTS`/
`CONTRADICTS`, untouched, unmodified).
"""

from __future__ import annotations

from enum import StrEnum


class ResearchSecurityFindingEvidenceRelation(StrEnum):
    """Name which side of a security finding one cited evidence record is on."""

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    VALIDATES = "validates"
