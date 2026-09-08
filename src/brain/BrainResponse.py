"""Standard response model returned by the Hypatia Brain."""

from __future__ import annotations

from dataclasses import dataclass, field

from brain.SessionSummary import SessionSummary
from cognition.LiveInformationRequestKind import LiveInformationRequestKind
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
from memory.LearnedMemoryAuditReport import LearnedMemoryAuditReport
from research.BackgroundResearchTask import BackgroundResearchTask
from research.CanonicalResearchSummary import CanonicalResearchSummary
from research.CuriosityResearchProposal import CuriosityResearchProposal
from research.FailureMemoryRecallMatch import FailureMemoryRecallMatch
from research.HypothesisAppraisal import HypothesisAppraisal
from research.HypothesisHistoryView import HypothesisHistoryView
from research.KnowledgeReconciliationReport import (
    KnowledgeReconciliationReport,
)
from research.ResearchAutonomyResult import ResearchAutonomyResult
from research.ResearchCalibrationReport import ResearchCalibrationReport
from research.ResearchClaimContradictionPreview import (
    ResearchClaimContradictionPreview,
)
from research.ResearchClaimContradictionProposalPreview import (
    ResearchClaimContradictionProposalPreview,
)
from research.ResearchClaimContradictionWritePreview import (
    ResearchClaimContradictionWritePreview,
)
from research.ResearchClaimPreview import ResearchClaimPreview
from research.ResearchClaimRevisionPreparation import (
    ResearchClaimRevisionPreparation,
)
from research.ResearchClaimWritePreview import ResearchClaimWritePreview
from research.ResearchCuriosityPreview import ResearchCuriosityPreview
from research.ResearchCuriosityQuestion import ResearchCuriosityQuestion
from research.ResearchEvidenceIntegrityStatus import ResearchEvidenceIntegrityStatus
from research.ResearchExecutionContinuation import (
    ResearchExecutionContinuation,
)
from research.ResearchFailureLesson import ResearchFailureLesson
from research.ResearchKaliOperationAuthorization import (
    ResearchKaliOperationAuthorization,
)
from research.ResearchKaliOperationExecution import ResearchKaliOperationRun
from research.ResearchKaliOperationPreview import (
    ResearchKaliOperationFakeRun,
    ResearchKaliOperationPreview,
)
from research.ResearchKaliRuntimeEnvironment import ResearchKaliRuntimeReadiness
from research.ResearchPairedProviderQualityReport import (
    ResearchPairedProviderQualityReport,
)
from research.ResearchPlanAuthorization import ResearchPlanAuthorization
from research.ResearchPlanBudgetRequirement import ResearchPlanBudgetFit
from research.ResearchPlanDraftPreview import ResearchPlanDraftPreview
from research.ResearchPlanExecutionState import ResearchPlanExecutionState
from research.ResearchPlanFailureLessonTrace import ResearchPlanFailureLessonTrace
from research.ResearchProviderComparisonReport import (
    ResearchProviderComparisonReport,
)
from research.ResearchProviderQualityReport import ResearchProviderQualityReport
from research.ResearchReflectionReport import ResearchReflectionReport
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
from research.SourceLoadStage import SourceLoadStage
from research.SourceReputation import SourceReputation
from security.SecurityPostureReport import SecurityPostureReport
from security.VulnerabilityFamily import VulnerabilityFamily
from security.VulnerabilityFamilyGraph import RelatedFamily
from security.VulnerabilityRelation import VulnerabilityRelation


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
    research_claim_contradiction_proposal_preview: (
        ResearchClaimContradictionProposalPreview | None
    ) = None
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
    research_plan_draft_preview: ResearchPlanDraftPreview | None = None
    research_plan_failure_lesson_trace: ResearchPlanFailureLessonTrace | None = None
    learned_memory_audit: LearnedMemoryAuditReport | None = None
    research_plan_execution: ResearchPlanExecutionState | None = None
    research_execution_continuation: ResearchExecutionContinuation | None = None
    research_plan_budget_fit: ResearchPlanBudgetFit | None = None
    research_autonomy: ResearchAutonomyResult | None = None
    background_research_task: BackgroundResearchTask | None = None
    research_curiosity: ResearchCuriosityPreview | None = None
    curiosity_proposal: CuriosityResearchProposal | None = None
    canonical_research_summary: CanonicalResearchSummary | None = None
    live_information_request: LiveInformationRequestKind | None = None
    curiosity_question: ResearchCuriosityQuestion | None = None
    curiosity_questions: tuple[ResearchCuriosityQuestion, ...] = ()
    research_reflection: ResearchReflectionReport | None = None
    research_reflections: tuple[ResearchReflectionReport, ...] = ()
    failure_lessons: tuple[ResearchFailureLesson, ...] = ()
    failure_memory_recall_matches: tuple[FailureMemoryRecallMatch, ...] = ()
    research_calibration: ResearchCalibrationReport | None = None
    research_claim_revision_preparation: ResearchClaimRevisionPreparation | None = None
    research_provider_quality: ResearchProviderQualityReport | None = None
    research_paired_provider_quality: ResearchPairedProviderQualityReport | None = None
    research_provider_comparison: ResearchProviderComparisonReport | None = None
    kali_operation_preview: ResearchKaliOperationPreview | None = None
    kali_operation_authorization: ResearchKaliOperationAuthorization | None = None
    kali_operation_fake_run: ResearchKaliOperationFakeRun | None = None
    kali_runtime_readiness: ResearchKaliRuntimeReadiness | None = None
    kali_operation_run: ResearchKaliOperationRun | None = None
    research_plan_authorization: ResearchPlanAuthorization | None = None
    research_plan_authorizations: tuple[ResearchPlanAuthorization, ...] = ()
    source_reputations: tuple[SourceReputation, ...] = ()
    hypothesis_appraisal: HypothesisAppraisal | None = None
    hypothesis_history: HypothesisHistoryView | None = None
    hypothesis_appraisals: tuple[HypothesisAppraisal, ...] = ()
    source_load_stage: SourceLoadStage | None = None
    knowledge_reconciliation: KnowledgeReconciliationReport | None = None
    security_posture: SecurityPostureReport | None = None
    vulnerability_family: VulnerabilityFamily | None = None
    vulnerability_families: tuple[VulnerabilityFamily, ...] = ()
    vulnerability_relation: VulnerabilityRelation | None = None
    related_vulnerability_families: tuple[RelatedFamily, ...] = ()
    session_summaries: list[SessionSummary] = field(default_factory=list)
    session_delete_allowed: bool | None = None
