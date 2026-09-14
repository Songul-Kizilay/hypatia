"""Immutable outcome of one real research operation for a plan step."""

from __future__ import annotations

from dataclasses import dataclass, field

from core.Exceptions import ResearchError
from research.ResearchSourcePreview import ResearchSourcePreview
from research.SemanticComparisonStepResult import SemanticComparisonStepResult
from research.SemanticEvidenceStepResult import SemanticEvidenceStepResult

MAX_RESEARCH_STEP_OPERATION_DETAIL_CHARACTERS = 500


@dataclass(frozen=True, slots=True)
class ResearchPlanStepOperationResult:
    """Report whether real work ran and one bounded factual summary.

    ``performed`` is set only by an operation that actually executed. It is the
    single signal allowed to mark a step as backed by real research work.

    ``succeeded`` is separate. An operation can genuinely run and still not
    achieve its outcome, so a real attempt is never rendered as success.
    """

    performed: bool
    detail: str
    succeeded: bool = True
    source_preview: ResearchSourcePreview | None = field(default=None, repr=False)
    semantic_evidence: SemanticEvidenceStepResult | None = field(
        default=None, repr=False
    )
    discovery_id: str = ""
    evidence_id: str = ""
    assessment_id: str = ""
    semantic_comparison: SemanticComparisonStepResult | None = field(
        default=None, repr=False
    )

    def __post_init__(self) -> None:
        if self.semantic_comparison is not None and (
            not isinstance(self.semantic_comparison, SemanticComparisonStepResult)
            or not self.performed
            or not self.succeeded
            or self.source_preview is not None
            or self.semantic_evidence is not None
            or self.discovery_id
            or self.evidence_id
            or self.assessment_id
        ):
            raise ResearchError(
                "Only successful comparison can carry tentative output."
            )
        for identity in (self.evidence_id, self.assessment_id):
            if not isinstance(identity, str) or len(identity) > 200:
                raise ResearchError("Operation record identity is invalid.")
            if identity and (not self.performed or not self.succeeded):
                raise ResearchError("Only successful work can carry record identity.")
        if not isinstance(self.discovery_id, str) or len(self.discovery_id) > 200:
            raise ResearchError("Operation discovery identity is invalid.")
        if self.discovery_id and (not self.performed or not self.succeeded):
            raise ResearchError("Only successful discovery can carry its identity.")
        if self.semantic_evidence is not None and (
            not isinstance(self.semantic_evidence, SemanticEvidenceStepResult)
            or not self.performed
            or not self.succeeded
            or self.source_preview is not None
        ):
            raise ResearchError("Only successful semantic work can carry proposals.")
        if self.source_preview is not None and (
            not isinstance(self.source_preview, ResearchSourcePreview)
            or not self.performed
            or not self.succeeded
        ):
            raise ResearchError("Only successful acquisition can carry source preview.")
        if not isinstance(self.performed, bool):
            raise ResearchError("Research step operation flag must be boolean.")
        if not isinstance(self.succeeded, bool):
            raise ResearchError("Research step operation outcome must be boolean.")
        if self.succeeded and not self.performed:
            raise ResearchError(
                "An operation that performed nothing cannot have succeeded."
            )
        if not isinstance(self.detail, str) or not self.detail.strip():
            raise ResearchError("Research step operation detail cannot be empty.")
        detail = self.detail.strip()
        if len(detail) > MAX_RESEARCH_STEP_OPERATION_DETAIL_CHARACTERS:
            raise ResearchError("Research step operation detail is too long.")
        object.__setattr__(self, "detail", detail)
