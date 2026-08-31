"""A record that somebody took back something they had said.

Retraction here means one thing only: this relationship must no longer be
treated as current. It does not mean the evidence was wrong, that the
hypothesis is settled either way, that the evidence belongs on the other side,
or that anything should be deleted. Evidence is a canonical record of an
observation and stays exactly as it was; what changes is a statement somebody
made about it.

The record exists so the correction is visible rather than silent. Removing an
identifier from a collection and saying nothing would leave a hypothesis that
looks as though the relationship had never been authored, which is a different
and less honest history than one showing it was authored and withdrawn.

Nothing here records *why*. A reason field would invite a sentence explaining a
judgement, and this file would then be storing judgements about evidence
alongside the bookkeeping — the operator's reasoning belongs in the places built
to hold it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from core.Exceptions import ResearchError
from research.HypothesisEvidenceRelation import HypothesisEvidenceRelation

MAX_HYPOTHESIS_RETRACTIONS = 200


@dataclass(frozen=True, slots=True)
class HypothesisEvidenceRetraction:
    """Record one withdrawn statement about evidence and a hypothesis."""

    evidence_id: str
    relation: HypothesisEvidenceRelation
    retracted_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.evidence_id, str) or not self.evidence_id.strip():
            raise ResearchError("A retracted evidence ID cannot be empty.")
        object.__setattr__(self, "evidence_id", self.evidence_id.strip())
        if not isinstance(self.relation, HypothesisEvidenceRelation):
            raise ResearchError("A retraction needs a known evidence relation.")
        if (
            not isinstance(self.retracted_at, datetime)
            or self.retracted_at.tzinfo is None
        ):
            raise ResearchError("A retraction time must be timezone aware.")
        if self.retracted_at > datetime.now(UTC):
            raise ResearchError("A retraction cannot be in the future.")

    def describes(self, evidence_id: str, relation: object) -> bool:
        """Say whether this record is about exactly that statement."""
        return self.evidence_id == evidence_id and self.relation is relation
