"""Who authored one security finding.

Exactly one member until a second is truly needed, mirroring
`ResearchSecurityHypothesisOrigin`'s discipline against adding a member "for
symmetry" before a real capability needs it. No automatic/model-authored
origin exists this milestone: model output, if a future milestone ever
produces finding content, remains a proposal, never authority, and would
need its own explicit vocabulary member rather than silently reusing this
one.
"""

from __future__ import annotations

from enum import StrEnum


class ResearchSecurityFindingOrigin(StrEnum):
    """Name who attested one security finding."""

    OPERATOR_AUTHORED = "operator_authored"
