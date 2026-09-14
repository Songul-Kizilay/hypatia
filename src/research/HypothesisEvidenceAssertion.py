"""When somebody said a piece of evidence stands in a relation to a hypothesis.

Membership lives where it always has: an identifier sits in one of the three
collections exactly while that relation stands. This annotates a member with the
moment it was authored, and exists only where that moment is known.

Absence is therefore meaningful and is the whole reason the record is separate.
A relation carried forward from a file written before times were kept has no
assertion record, and reads as authored at an unknown time — which is true.
Giving every member a record and filling the older ones in would have required a
number nobody recorded, and the only numbers available are wrong: the
hypothesis's update time moves with every later change, the retraction's time is
when the statement ended rather than began, and a load time is when the file was
read.

A record cannot exist for something that does not currently stand. That is
enforced by the hypothesis, so a time can never outlive the statement it is
about, and retracting a relation takes its assertion with it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from core.Exceptions import ResearchError
from research.HypothesisEvidenceRelation import HypothesisEvidenceRelation


@dataclass(frozen=True, slots=True)
class HypothesisEvidenceAssertion:
    """Record the moment one currently standing relation was authored."""

    evidence_id: str
    relation: HypothesisEvidenceRelation
    authored_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.evidence_id, str) or not self.evidence_id.strip():
            raise ResearchError("An asserted evidence ID cannot be empty.")
        object.__setattr__(self, "evidence_id", self.evidence_id.strip())
        if not isinstance(self.relation, HypothesisEvidenceRelation):
            raise ResearchError("An assertion needs a known evidence relation.")
        if (
            not isinstance(self.authored_at, datetime)
            or self.authored_at.tzinfo is None
        ):
            raise ResearchError("An assertion time must be timezone aware.")
        if self.authored_at > datetime.now(UTC):
            raise ResearchError("An assertion cannot be in the future.")

    def describes(self, evidence_id: str, relation: object) -> bool:
        """Say whether this record is about exactly that statement."""
        return self.evidence_id == evidence_id and self.relation is relation
