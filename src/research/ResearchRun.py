"""Persistent audit record for one bounded research question."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.Exceptions import ResearchError
from research.ResearchClaimContradictionRecord import (
    ResearchClaimContradictionRecord,
)
from research.ResearchClaimRecord import ResearchClaimRecord
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchFailureRecord import ResearchFailureRecord
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSourceAssessmentRecord import ResearchSourceAssessmentRecord
from research.ResearchSourceComparisonNoteRecord import (
    ResearchSourceComparisonNoteRecord,
)
from research.ResearchSourceDiscoveryRecord import ResearchSourceDiscoveryRecord
from research.ResearchSourceRecord import ResearchSourceRecord


@dataclass(frozen=True, slots=True)
class ResearchRun:
    """Record a question, accepted source provenance, and safe failures."""

    run_id: str
    question: str
    status: ResearchRunStatus
    sources: tuple[ResearchSourceRecord, ...]
    failures: tuple[ResearchFailureRecord, ...]
    created_at: datetime
    updated_at: datetime
    evidence: tuple[ResearchEvidenceRecord, ...] = ()
    discoveries: tuple[ResearchSourceDiscoveryRecord, ...] = ()
    assessments: tuple[ResearchSourceAssessmentRecord, ...] = ()
    comparison_notes: tuple[ResearchSourceComparisonNoteRecord, ...] = ()
    claims: tuple[ResearchClaimRecord, ...] = ()
    claim_contradictions: tuple[ResearchClaimContradictionRecord, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, str) or not self.run_id.strip():
            raise ResearchError("Research run ID cannot be empty.")
        if not isinstance(self.question, str) or not self.question.strip():
            raise ResearchError("Research question cannot be empty.")
        if len(self.question.strip()) > 2_000:
            raise ResearchError("Research question is too long.")
        if not isinstance(self.status, ResearchRunStatus):
            raise ResearchError("Research run status is invalid.")
        if not isinstance(self.sources, tuple):
            raise ResearchError("Research run sources must be an immutable tuple.")
        if not all(isinstance(source, ResearchSourceRecord) for source in self.sources):
            raise ResearchError("Research run contains an invalid source record.")
        if len({source.document_id for source in self.sources}) != len(self.sources):
            raise ResearchError("Research run contains duplicate source documents.")
        if not isinstance(self.failures, tuple):
            raise ResearchError("Research run failures must be an immutable tuple.")
        if not all(
            isinstance(failure, ResearchFailureRecord) for failure in self.failures
        ):
            raise ResearchError("Research run contains an invalid failure record.")
        if not isinstance(self.evidence, tuple):
            raise ResearchError("Research run evidence must be an immutable tuple.")
        if not all(
            isinstance(record, ResearchEvidenceRecord) for record in self.evidence
        ):
            raise ResearchError("Research run contains an invalid evidence record.")
        evidence_ids = [record.evidence_id for record in self.evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ResearchError("Research run contains duplicate evidence IDs.")
        source_ids = {source.document_id for source in self.sources}
        if any(record.source_document_id not in source_ids for record in self.evidence):
            raise ResearchError("Research evidence must reference an accepted source.")
        if not isinstance(self.discoveries, tuple):
            raise ResearchError("Research run discoveries must be an immutable tuple.")
        if not all(
            isinstance(record, ResearchSourceDiscoveryRecord)
            for record in self.discoveries
        ):
            raise ResearchError("Research run contains an invalid discovery record.")
        discovery_ids = [record.discovery_id for record in self.discoveries]
        if len(discovery_ids) != len(set(discovery_ids)):
            raise ResearchError("Research run contains duplicate discovery IDs.")
        if not isinstance(self.assessments, tuple):
            raise ResearchError("Research run assessments must be an immutable tuple.")
        if not all(
            isinstance(record, ResearchSourceAssessmentRecord)
            for record in self.assessments
        ):
            raise ResearchError("Research run contains an invalid assessment record.")
        assessment_ids = [record.assessment_id for record in self.assessments]
        if len(assessment_ids) != len(set(assessment_ids)):
            raise ResearchError("Research run contains duplicate assessment IDs.")
        evidence_id_set = set(evidence_ids)
        if any(
            record.source_document_id not in source_ids for record in self.assessments
        ):
            raise ResearchError(
                "Research assessments must reference an accepted source."
            )
        if any(
            evidence_id not in evidence_id_set
            for record in self.assessments
            for evidence_id in record.evidence_ids
        ):
            raise ResearchError(
                "Research assessments must reference recorded evidence."
            )
        evidence_source_by_id = {
            record.evidence_id: record.source_document_id for record in self.evidence
        }
        if any(
            evidence_source_by_id[evidence_id] != record.source_document_id
            for record in self.assessments
            for evidence_id in record.evidence_ids
        ):
            raise ResearchError(
                "Research assessment evidence must belong to its source."
            )
        assessments_by_id: dict[str, ResearchSourceAssessmentRecord] = {}
        superseded_assessment_ids: set[str] = set()
        for record in self.assessments:
            superseded_id = record.supersedes_assessment_id
            if superseded_id is not None:
                superseded = assessments_by_id.get(superseded_id)
                if superseded is None:
                    raise ResearchError(
                        "Research assessment supersession must reference an earlier "
                        "assessment in the same run."
                    )
                if superseded.source_document_id != record.source_document_id:
                    raise ResearchError(
                        "Research assessment supersession must stay within one source."
                    )
                if superseded_id in superseded_assessment_ids:
                    raise ResearchError(
                        "A research source assessment cannot have multiple "
                        "superseding records."
                    )
                if record.recorded_at < superseded.recorded_at:
                    raise ResearchError(
                        "A superseding research assessment cannot precede its target."
                    )
                superseded_assessment_ids.add(superseded_id)
            assessments_by_id[record.assessment_id] = record
        if not isinstance(self.comparison_notes, tuple):
            raise ResearchError(
                "Research run comparison notes must be an immutable tuple."
            )
        if not all(
            isinstance(record, ResearchSourceComparisonNoteRecord)
            for record in self.comparison_notes
        ):
            raise ResearchError("Research run contains an invalid comparison note.")
        note_ids = [record.note_id for record in self.comparison_notes]
        if len(note_ids) != len(set(note_ids)):
            raise ResearchError("Research run contains duplicate comparison note IDs.")
        evidence_by_id = {record.evidence_id: record for record in self.evidence}
        for note in self.comparison_notes:
            selected_source_ids = set(note.source_document_ids)
            if not selected_source_ids.issubset(source_ids):
                raise ResearchError(
                    "Research comparison notes must reference accepted sources."
                )
            try:
                note_evidence = tuple(
                    evidence_by_id[evidence_id] for evidence_id in note.evidence_ids
                )
                note_assessments = tuple(
                    assessments_by_id[assessment_id]
                    for assessment_id in note.assessment_ids
                )
            except KeyError as error:
                raise ResearchError(
                    "Research comparison notes must reference persisted records."
                ) from error
            if {
                record.source_document_id for record in note_evidence
            } != selected_source_ids:
                raise ResearchError(
                    "Research comparison note evidence must cover its sources."
                )
            if {
                record.source_document_id for record in note_assessments
            } != selected_source_ids:
                raise ResearchError(
                    "Research comparison note assessments must cover its sources."
                )
            note_evidence_ids = set(note.evidence_ids)
            if any(
                not set(assessment.evidence_ids).issubset(note_evidence_ids)
                for assessment in note_assessments
            ):
                raise ResearchError(
                    "Research comparison notes must cite each assessment's evidence."
                )
        if not isinstance(self.claims, tuple):
            raise ResearchError("Research run claims must be an immutable tuple.")
        if not all(
            isinstance(claim_record, ResearchClaimRecord)
            for claim_record in self.claims
        ):
            raise ResearchError("Research run contains an invalid claim record.")
        claim_ids = [claim_record.claim_id for claim_record in self.claims]
        if len(claim_ids) != len(set(claim_ids)):
            raise ResearchError("Research run contains duplicate claim IDs.")
        claims_by_id: dict[str, ResearchClaimRecord] = {}
        superseded_claim_ids: set[str] = set()
        for claim_record in self.claims:
            if any(
                evidence_id not in evidence_id_set
                for evidence_id in claim_record.evidence_ids
            ):
                raise ResearchError("Research claims must reference recorded evidence.")
            expected_source_ids = tuple(
                dict.fromkeys(
                    evidence_source_by_id[evidence_id]
                    for evidence_id in claim_record.evidence_ids
                )
            )
            if claim_record.source_document_ids != expected_source_ids:
                raise ResearchError(
                    "Research claim sources must match its evidence provenance."
                )
            superseded_id = claim_record.supersedes_claim_id
            if superseded_id is not None:
                superseded_claim = claims_by_id.get(superseded_id)
                if superseded_claim is None:
                    raise ResearchError(
                        "Research claim supersession must reference an earlier claim."
                    )
                if superseded_id in superseded_claim_ids:
                    raise ResearchError(
                        "A research claim cannot have multiple superseding records."
                    )
                if claim_record.recorded_at < superseded_claim.recorded_at:
                    raise ResearchError(
                        "A superseding research claim cannot precede its target."
                    )
                superseded_claim_ids.add(superseded_id)
            claims_by_id[claim_record.claim_id] = claim_record
        if not isinstance(self.claim_contradictions, tuple):
            raise ResearchError(
                "Research run claim contradictions must be an immutable tuple."
            )
        if not all(
            isinstance(record, ResearchClaimContradictionRecord)
            for record in self.claim_contradictions
        ):
            raise ResearchError(
                "Research run contains an invalid claim contradiction record."
            )
        contradiction_ids = [
            record.contradiction_id for record in self.claim_contradictions
        ]
        if len(contradiction_ids) != len(set(contradiction_ids)):
            raise ResearchError(
                "Research run contains duplicate claim contradiction IDs."
            )
        contradiction_pairs: set[frozenset[str]] = set()
        for contradiction in self.claim_contradictions:
            try:
                related_claims = tuple(
                    claims_by_id[claim_id] for claim_id in contradiction.claim_ids
                )
            except KeyError as error:
                raise ResearchError(
                    "Research claim contradictions must reference persisted claims."
                ) from error
            expected_evidence_ids = tuple(
                dict.fromkeys(
                    evidence_id
                    for claim in related_claims
                    for evidence_id in claim.evidence_ids
                )
            )
            if contradiction.evidence_ids != expected_evidence_ids:
                raise ResearchError(
                    "Research claim contradiction evidence must match its claims."
                )
            pair = frozenset(contradiction.claim_ids)
            if pair in contradiction_pairs:
                raise ResearchError(
                    "Research run contains a duplicate claim contradiction pair."
                )
            contradiction_pairs.add(pair)
        for value, field_name in (
            (self.created_at, "Research run creation time"),
            (self.updated_at, "Research run update time"),
        ):
            if not isinstance(value, datetime) or value.utcoffset() is None:
                raise ResearchError(f"{field_name} must be timezone-aware.")
        if self.updated_at < self.created_at:
            raise ResearchError("Research run update time cannot precede creation.")
        if any(
            note.recorded_at < self.created_at or note.recorded_at > self.updated_at
            for note in self.comparison_notes
        ):
            raise ResearchError(
                "Research comparison note time must stay within its run lifecycle."
            )
        if any(
            claim.recorded_at < self.created_at or claim.recorded_at > self.updated_at
            for claim in self.claims
        ):
            raise ResearchError(
                "Research claim time must stay within its run lifecycle."
            )
        if any(
            contradiction.recorded_at < self.created_at
            or contradiction.recorded_at > self.updated_at
            for contradiction in self.claim_contradictions
        ):
            raise ResearchError(
                "Research claim contradiction time must stay within its run lifecycle."
            )
        object.__setattr__(self, "run_id", self.run_id.strip())
        object.__setattr__(self, "question", self.question.strip())
