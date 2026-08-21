"""No-write decision for one evidence-linked research claim."""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchClaimConfidence import ResearchClaimConfidence
from research.ResearchClaimRecord import ResearchClaimRecord
from research.ResearchEpistemicState import ResearchEpistemicState
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSourceRecord import ResearchSourceRecord


@dataclass(frozen=True, slots=True)
class ResearchClaimWritePreview:
    """Validate exact authored claim inputs before a separate confirmation."""

    run_id: str
    run_status: ResearchRunStatus
    sources: tuple[ResearchSourceRecord, ...]
    evidence: tuple[ResearchEvidenceRecord, ...]
    text: str
    epistemic_state: ResearchEpistemicState
    confidence: ResearchClaimConfidence
    allowed: bool
    reason: str
    supersedes_claim: ResearchClaimRecord | None = None

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.run_id, "Research claim preview run ID"),
            (self.text, "Research claim preview text"),
            (self.reason, "Research claim preview reason"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ResearchError(f"{field_name} cannot be empty.")
        if not isinstance(self.run_status, ResearchRunStatus):
            raise ResearchError("Research claim preview run status is invalid.")
        if (
            not isinstance(self.sources, tuple)
            or not self.sources
            or not all(
                isinstance(record, ResearchSourceRecord) for record in self.sources
            )
        ):
            raise ResearchError("Research claim preview sources are invalid.")
        if (
            not isinstance(self.evidence, tuple)
            or not self.evidence
            or not all(
                isinstance(record, ResearchEvidenceRecord) for record in self.evidence
            )
        ):
            raise ResearchError("Research claim preview evidence is invalid.")
        source_ids = tuple(record.document_id for record in self.sources)
        evidence_source_ids = tuple(
            dict.fromkeys(record.source_document_id for record in self.evidence)
        )
        if source_ids != evidence_source_ids:
            raise ResearchError("Research claim preview provenance is inconsistent.")
        if not isinstance(self.epistemic_state, ResearchEpistemicState):
            raise ResearchError("Research claim preview epistemic state is invalid.")
        if not isinstance(self.confidence, ResearchClaimConfidence):
            raise ResearchError("Research claim preview confidence is invalid.")
        if not isinstance(self.allowed, bool):
            raise ResearchError("Research claim preview decision must be boolean.")
        if self.supersedes_claim is not None and not isinstance(
            self.supersedes_claim,
            ResearchClaimRecord,
        ):
            raise ResearchError("Superseded research claim is invalid.")
        object.__setattr__(self, "run_id", self.run_id.strip())
        object.__setattr__(self, "text", self.text.strip())
        object.__setattr__(self, "reason", self.reason.strip())
