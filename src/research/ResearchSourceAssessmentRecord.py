"""Persistent user-authored assessment of one accepted research source.

The prose and the trust label were here first, and they answer one question:
what did the person conclude about the information they took out of this source.
The structured dimensions added alongside them answer a different one: what did
the person conclude about the source itself — whether it was worth reading,
whether it bears on this run's question, whether it is its own witness or is
repeating another, whether the publication still stands, and how far it sits
from the thing it describes.

Every dimension defaults to `unknown`, and `unknown` is an answer rather than a
gap waiting to be filled. Most sources are never appraised, and reading silence
as any other value would be inventing a judgement nobody made.

What these do not do is the load-bearing part. They change no relevance score,
no relevance rank, no reputation, no evidence, no claim, and no confidence. They
do not accept or reject anything. Only `information_trust` reaches the
reputation ledger, and it reaches it exactly as it did before, so nothing here
can move a publisher's standing by a side effect.

The assessment stays bound to evidence the run actually recorded. That is a real
limit and worth naming: a source can only be appraised after it was accepted and
something was taken from it, so a candidate a person read and discarded without
recording anything cannot be judged here. Loosening that would mean an
assessment that names no evidence, which is a different record keyed on a
different identity, not a wider version of this one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.Exceptions import ResearchError
from research.ResearchInformationTrust import ResearchInformationTrust
from research.ResearchSourceApplicability import ResearchSourceApplicability
from research.ResearchSourceEvidenceType import ResearchSourceEvidenceType
from research.ResearchSourceIndependence import ResearchSourceIndependence
from research.ResearchSourcePublicationStatus import ResearchSourcePublicationStatus
from research.ResearchSourceUsefulness import ResearchSourceUsefulness

MAX_SOURCE_ASSESSMENT_CHARACTERS = 2_000


@dataclass(frozen=True, slots=True)
class ResearchSourceAssessmentRecord:
    """Append-only assessment text bound to explicitly selected evidence."""

    assessment_id: str
    source_document_id: str
    evidence_ids: tuple[str, ...]
    text: str
    recorded_at: datetime
    supersedes_assessment_id: str | None = None
    information_trust: ResearchInformationTrust = ResearchInformationTrust.UNASSESSED
    usefulness: ResearchSourceUsefulness = ResearchSourceUsefulness.UNKNOWN
    applicability: ResearchSourceApplicability = ResearchSourceApplicability.UNKNOWN
    independence: ResearchSourceIndependence = ResearchSourceIndependence.UNKNOWN
    publication_status: ResearchSourcePublicationStatus = (
        ResearchSourcePublicationStatus.UNKNOWN
    )
    evidence_type: ResearchSourceEvidenceType = ResearchSourceEvidenceType.UNKNOWN

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.assessment_id, "Research source assessment ID"),
            (self.source_document_id, "Research source assessment document ID"),
            (self.text, "Research source assessment text"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ResearchError(f"{field_name} cannot be empty.")
        if len(self.text.strip()) > MAX_SOURCE_ASSESSMENT_CHARACTERS:
            raise ResearchError("Research source assessment text is too long.")
        if not isinstance(self.evidence_ids, tuple) or not self.evidence_ids:
            raise ResearchError(
                "Research source assessment requires explicit evidence IDs."
            )
        if not all(
            isinstance(evidence_id, str) and evidence_id.strip()
            for evidence_id in self.evidence_ids
        ):
            raise ResearchError("Research source assessment evidence IDs are invalid.")
        normalized_evidence_ids = tuple(
            evidence_id.strip() for evidence_id in self.evidence_ids
        )
        if len(normalized_evidence_ids) != len(set(normalized_evidence_ids)):
            raise ResearchError(
                "Research source assessment contains duplicate evidence IDs."
            )
        if (
            not isinstance(self.recorded_at, datetime)
            or self.recorded_at.utcoffset() is None
        ):
            raise ResearchError(
                "Research source assessment time must be timezone-aware."
            )
        if not isinstance(self.information_trust, ResearchInformationTrust):
            raise ResearchError("Research source information trust is invalid.")
        for value, expected, label in (
            (self.usefulness, ResearchSourceUsefulness, "usefulness"),
            (self.applicability, ResearchSourceApplicability, "applicability"),
            (self.independence, ResearchSourceIndependence, "independence"),
            (
                self.publication_status,
                ResearchSourcePublicationStatus,
                "publication status",
            ),
            (self.evidence_type, ResearchSourceEvidenceType, "evidence type"),
        ):
            if not isinstance(value, expected):
                raise ResearchError(f"Research source {label} is invalid.")
        supersedes_assessment_id = self.supersedes_assessment_id
        if supersedes_assessment_id is not None:
            if (
                not isinstance(supersedes_assessment_id, str)
                or not supersedes_assessment_id.strip()
            ):
                raise ResearchError(
                    "Superseded research source assessment ID cannot be empty."
                )
            supersedes_assessment_id = supersedes_assessment_id.strip()
            if supersedes_assessment_id == self.assessment_id.strip():
                raise ResearchError(
                    "A research source assessment cannot supersede itself."
                )
        object.__setattr__(self, "assessment_id", self.assessment_id.strip())
        object.__setattr__(
            self,
            "source_document_id",
            self.source_document_id.strip(),
        )
        object.__setattr__(self, "evidence_ids", normalized_evidence_ids)
        object.__setattr__(self, "text", self.text.strip())
        object.__setattr__(
            self,
            "supersedes_assessment_id",
            supersedes_assessment_id,
        )
