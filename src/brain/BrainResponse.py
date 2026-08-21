"""Standard response model returned by the Hypatia Brain."""

from __future__ import annotations

from dataclasses import dataclass, field

from brain.SessionSummary import SessionSummary
from knowledge.Chunk import Chunk
from knowledge.KnowledgeCitation import KnowledgeCitation
from knowledge.KnowledgeDocumentReference import KnowledgeDocumentReference
from knowledge.KnowledgeRelationApplication import KnowledgeRelationApplication
from knowledge.KnowledgeRelationPreview import KnowledgeRelationPreview
from knowledge.KnowledgeRelationReference import KnowledgeRelationReference
from knowledge.KnowledgeRelationRevocation import KnowledgeRelationRevocation
from knowledge.KnowledgeRelationRevocationPreview import (
    KnowledgeRelationRevocationPreview,
)
from research.ResearchClaimContradictionPreview import (
    ResearchClaimContradictionPreview,
)
from research.ResearchClaimContradictionWritePreview import (
    ResearchClaimContradictionWritePreview,
)
from research.ResearchClaimPreview import ResearchClaimPreview
from research.ResearchClaimWritePreview import ResearchClaimWritePreview
from research.ResearchEvidenceIntegrityStatus import ResearchEvidenceIntegrityStatus
from research.ResearchRun import ResearchRun
from research.ResearchRunMarkdownExportPreview import (
    ResearchRunMarkdownExportPreview,
)
from research.ResearchRunMarkdownExportResult import (
    ResearchRunMarkdownExportResult,
)
from research.ResearchRunMarkdownExportVerification import (
    ResearchRunMarkdownExportVerification,
)
from research.ResearchRunStatusTransitionPreview import (
    ResearchRunStatusTransitionPreview,
)
from research.ResearchSourceAssessmentPreview import ResearchSourceAssessmentPreview
from research.ResearchSourceAssessmentWritePreview import (
    ResearchSourceAssessmentWritePreview,
)
from research.ResearchSourceCandidateAcceptancePreview import (
    ResearchSourceCandidateAcceptancePreview,
)
from research.ResearchSourceComparisonNoteWritePreview import (
    ResearchSourceComparisonNoteWritePreview,
)
from research.ResearchSourceComparisonPreview import ResearchSourceComparisonPreview
from research.ResearchSourceContentRestorationStatus import (
    ResearchSourceContentRestorationStatus,
)


@dataclass(frozen=True, slots=True)
class BrainResponse:
    """Deterministic response from the first Brain implementation."""

    message: str
    request_id: str
    intent: str
    memory_count: int
    success: bool = True
    knowledge_results: list[Chunk] = field(default_factory=list)
    knowledge_citations: list[KnowledgeCitation] = field(default_factory=list)
    knowledge_documents: list[KnowledgeDocumentReference] = field(default_factory=list)
    knowledge_relations: list[KnowledgeRelationReference] = field(default_factory=list)
    knowledge_relation_preview: KnowledgeRelationPreview | None = None
    knowledge_relation_application: KnowledgeRelationApplication | None = None
    knowledge_relation_revocation_preview: KnowledgeRelationRevocationPreview | None = (
        None
    )
    knowledge_relation_revocation: KnowledgeRelationRevocation | None = None
    research_runs: list[ResearchRun] = field(default_factory=list)
    research_claim_preview: ResearchClaimPreview | None = None
    research_claim_write_preview: ResearchClaimWritePreview | None = None
    research_claim_contradiction_preview: ResearchClaimContradictionPreview | None = (
        None
    )
    research_claim_contradiction_write_preview: (
        ResearchClaimContradictionWritePreview | None
    ) = None
    research_run_markdown_export_preview: ResearchRunMarkdownExportPreview | None = None
    research_run_markdown_export_result: ResearchRunMarkdownExportResult | None = None
    research_run_markdown_export_verification: (
        ResearchRunMarkdownExportVerification | None
    ) = None
    research_run_status_transition_preview: (
        ResearchRunStatusTransitionPreview | None
    ) = None
    research_source_candidate_acceptance_preview: (
        ResearchSourceCandidateAcceptancePreview | None
    ) = None
    research_source_assessment_preview: ResearchSourceAssessmentPreview | None = None
    research_source_comparison_preview: ResearchSourceComparisonPreview | None = None
    research_source_comparison_note_write_preview: (
        ResearchSourceComparisonNoteWritePreview | None
    ) = None
    research_source_assessment_write_preview: (
        ResearchSourceAssessmentWritePreview | None
    ) = None
    research_source_content_restoration_status: (
        ResearchSourceContentRestorationStatus | None
    ) = None
    research_evidence_integrity_status: ResearchEvidenceIntegrityStatus | None = None
    session_summaries: list[SessionSummary] = field(default_factory=list)
    session_delete_allowed: bool | None = None
