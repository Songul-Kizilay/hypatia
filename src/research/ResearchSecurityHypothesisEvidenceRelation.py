"""How one cited evidence record bears on a security hypothesis.

Kept as two disjoint sets, never netted against each other, mirroring
`ResearchHypothesis`'s own supporting/opposing-never-merged discipline: a
count of three-for and two-against is a real situation someone has to look
at, and collapsing it into a single score would destroy exactly that.
"""

from __future__ import annotations

from enum import StrEnum


class ResearchSecurityHypothesisEvidenceRelation(StrEnum):
    """Name which side of a security hypothesis one cited evidence record is on."""

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
