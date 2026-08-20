"""Persistent audit record for one bounded research question."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.Exceptions import ResearchError
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchFailureRecord import ResearchFailureRecord
from research.ResearchRunStatus import ResearchRunStatus
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
        for value, field_name in (
            (self.created_at, "Research run creation time"),
            (self.updated_at, "Research run update time"),
        ):
            if not isinstance(value, datetime) or value.utcoffset() is None:
                raise ResearchError(f"{field_name} must be timezone-aware.")
        if self.updated_at < self.created_at:
            raise ResearchError("Research run update time cannot precede creation.")
        object.__setattr__(self, "run_id", self.run_id.strip())
        object.__setattr__(self, "question", self.question.strip())
