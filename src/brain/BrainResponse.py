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
from research.ResearchRun import ResearchRun
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
    session_summaries: list[SessionSummary] = field(default_factory=list)
    session_delete_allowed: bool | None = None
