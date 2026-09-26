"""One immutable, append-only fact: cited evidence bears on a security finding.

References evidence by stable identity only (`evidence_id`) — never copies
evidence content, exactly like
`research.ResearchSecurityHypothesisEvidenceLinkRecord`. This is deliberate
and structural, not merely a style choice: an instruction-shaped string
embedded inside evidence (a header value, tool output, source prose) can
only ever reach this layer as an opaque identifier, so it has no path to
alter a finding field, a status, or a rendered response. `evidence_id` is
validated as a real `is_http_evidence_id` shape when `evidence_kind` is
`HTTP_EVIDENCE` — the only evidence kind that exists yet, so any other kind
fails closed rather than being validated by guesswork.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.Exceptions import ResearchError
from research.ResearchHttpEvidenceRecord import is_http_evidence_id
from research.ResearchSecurityFindingEvidenceKind import (
    ResearchSecurityFindingEvidenceKind,
)
from research.ResearchSecurityFindingEvidenceRelation import (
    ResearchSecurityFindingEvidenceRelation,
)

MAX_SECURITY_FINDING_EVIDENCE_LINK_ID_CHARACTERS = 200
MAX_SECURITY_FINDING_EVIDENCE_LINK_FINDING_ID_CHARACTERS = 200
MAX_SECURITY_FINDING_EVIDENCE_LINK_PROGRAM_ID_CHARACTERS = 200


def _bounded_identifier(value: object, label: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise ResearchError(f"{label} is invalid.")
    normalized = value.strip()
    if any(ord(character) < 32 or ord(character) == 127 for character in normalized):
        raise ResearchError(f"{label} must be single-line text.")
    return normalized


@dataclass(frozen=True, slots=True)
class ResearchSecurityFindingEvidenceLinkRecord:
    """One recorded fact: this evidence bears on this finding (see relation)."""

    link_id: str
    finding_id: str
    program_id: str
    evidence_kind: ResearchSecurityFindingEvidenceKind
    evidence_id: str
    relation: ResearchSecurityFindingEvidenceRelation
    recorded_at: datetime

    def __post_init__(self) -> None:
        link_id = _bounded_identifier(
            self.link_id,
            "Security finding evidence link ID",
            MAX_SECURITY_FINDING_EVIDENCE_LINK_ID_CHARACTERS,
        )
        finding_id = _bounded_identifier(
            self.finding_id,
            "Security finding evidence link finding ID",
            MAX_SECURITY_FINDING_EVIDENCE_LINK_FINDING_ID_CHARACTERS,
        )
        program_id = _bounded_identifier(
            self.program_id,
            "Security finding evidence link program ID",
            MAX_SECURITY_FINDING_EVIDENCE_LINK_PROGRAM_ID_CHARACTERS,
        )
        if not isinstance(self.evidence_kind, ResearchSecurityFindingEvidenceKind):
            raise ResearchError("Security finding evidence kind is invalid.")
        if self.evidence_kind is ResearchSecurityFindingEvidenceKind.HTTP_EVIDENCE:
            if not is_http_evidence_id(self.evidence_id):
                raise ResearchError("Security finding evidence ID is invalid.")
        else:
            # No other evidence kind exists yet. Fail closed rather than
            # accept a shape nothing here can honestly validate — this branch
            # only becomes reachable once a future milestone adds a second
            # `ResearchSecurityFindingEvidenceKind` member and its own
            # validation alongside it.
            raise ResearchError("Security finding evidence kind is invalid.")
        if not isinstance(self.relation, ResearchSecurityFindingEvidenceRelation):
            raise ResearchError("Security finding evidence relation is invalid.")
        if (
            not isinstance(self.recorded_at, datetime)
            or self.recorded_at.utcoffset() is None
        ):
            raise ResearchError(
                "Security finding evidence link recorded time must be"
                " timezone-aware."
            )
        object.__setattr__(self, "link_id", link_id)
        object.__setattr__(self, "finding_id", finding_id)
        object.__setattr__(self, "program_id", program_id)
