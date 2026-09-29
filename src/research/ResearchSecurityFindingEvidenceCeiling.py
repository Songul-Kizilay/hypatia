"""What the recorded evidence *structure* on one security finding can
defensibly support — never a truth-confidence, never a probability.

A ceiling names an upper bound the record's own shape cannot honestly
exceed, exactly the distinction `research.ResearchClaimCalibrator`'s own
module docstring already draws for the unrelated general-research claim
subsystem ("None of these verdicts is about truth"). This is a *different*
type, deliberately not a reuse of `ResearchClaimConfidence`: that subsystem's
ceilings are computed from `ResearchInformationTrust` (operator-authored,
per-source trust) and `ResearchSourceIndependence` (operator-authored,
per-source independence) — dimensions a security finding's evidence has no
equivalent of. `ResearchSecurityFindingEvidenceLinkRecord` carries only an
`evidence_id` and a `relation` (`SUPPORTS`/`CONTRADICTS`/`VALIDATES`); the
`ResearchHttpEvidenceRecord` it cites carries exactly one
`ResearchHttpEvidenceProvenanceKind` member today, so every citation shares
identical provenance — there is no trust gradient, and no way to tell two
citations "the same observation restated" from "two independently obtained
observations" (only `research.ResearchSourceIndependence`, an operator
judgement over research-claim sources, records that distinction, and no
finding evidence link carries anything like it).

Consequently `HIGH` is a member of this vocabulary, matching
`ResearchClaimConfidence`'s own four-tier shape for forward
extensibility, but it is *never returned* by
`ResearchSecurityFinding.evidence_ceiling` today — see that property's own
docstring for the exact reachable-tier rule and why `HIGH` stays
unreachable until finding evidence gains an independence/trust dimension
of its own. It is entirely acceptable, and expected, for a bounded
vocabulary to have members no current data can reach.
"""

from __future__ import annotations

from enum import StrEnum


class ResearchSecurityFindingEvidenceCeiling(StrEnum):
    """Name the most a finding's current evidence structure can support."""

    UNASSESSED = "unassessed"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
