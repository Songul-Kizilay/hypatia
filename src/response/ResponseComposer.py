"""Central response composition contract for Hypatia."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from brain.SessionSummary import SessionSummary
from cognition.LiveInformationRequestKind import LiveInformationRequestKind
from knowledge.Chunk import Chunk
from knowledge.KnowledgeCitation import KnowledgeCitation
from knowledge.KnowledgeDocumentReference import KnowledgeDocumentReference
from knowledge.KnowledgeGraph import KnowledgeGraphView
from knowledge.KnowledgeRelationApplication import KnowledgeRelationApplication
from knowledge.KnowledgeRelationPreview import KnowledgeRelationPreview
from knowledge.KnowledgeRelationReference import KnowledgeRelationReference
from knowledge.KnowledgeRelationRevocation import KnowledgeRelationRevocation
from knowledge.KnowledgeRelationRevocationPreview import (
    KnowledgeRelationRevocationPreview,
)
from memory.LearnedMemoryAuditReport import LearnedMemoryAuditReport
from memory.MemoryRecord import MemoryRecord
from planner.Plan import Plan
from research.BackgroundResearchTask import BackgroundResearchTask
from research.CanonicalResearchSummary import CanonicalResearchSummary
from research.CuriosityResearchProposal import CuriosityResearchProposal
from research.HypothesisAppraisal import HypothesisAppraisal
from research.HypothesisHistoryView import HypothesisHistoryView
from research.KnowledgeReconciliationReport import (
    KnowledgeReconciliationReport,
)
from research.ResearchAttemptResolution import ResearchAttemptResolution
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
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchEvidenceIntegrityStatus import ResearchEvidenceIntegrityStatus
from research.ResearchExecutionAllowance import ResearchExecutionAllowance
from research.ResearchFailureLesson import ResearchFailureLesson
from research.ResearchPairedProviderQualityReport import (
    ResearchPairedProviderQualityReport,
)
from research.ResearchPlanAuthorization import ResearchPlanAuthorization
from research.ResearchPlanAuthorizationPreview import (
    ResearchPlanAuthorizationPreview,
)
from research.ResearchPlanAuthorizationVerdict import (
    ResearchPlanAuthorizationVerdict,
)
from research.ResearchPlanDraftPreview import ResearchPlanDraftPreview
from research.ResearchPlanExecutionSnapshot import (
    ResearchPlanExecutionSnapshot,
)
from research.ResearchPlanExecutionState import ResearchPlanExecutionState
from research.ResearchPlanStepStatus import ResearchPlanStepStatus
from research.ResearchProviderComparisonReport import (
    ResearchProviderComparisonReport,
)
from research.ResearchProviderQualityReport import (
    ResearchProviderQualityReport,
)
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
from response.HonestyPhrasebook import phrase
from response.ResponseLanguage import detect_response_language
from security.SecurityPostureReport import SecurityPostureReport
from security.VulnerabilityFamily import VulnerabilityFamily
from security.VulnerabilityFamilyGraph import RelatedFamily
from security.VulnerabilityRelation import VulnerabilityRelation
from session.SessionDeleteExecutionResult import SessionDeleteExecutionResult
from session.SessionDeletePolicy import SessionDeleteStatus
from session.SessionRecord import SessionRecord
from session.SessionRenamePreview import SessionRenamePreview
from session.SessionRenameResult import SessionRenameResult

#: How much of a hypothesis a list entry shows. A hypothesis may be 400
#: characters; a catalogue someone is scanning should stay scannable, and the
#: full wording is one appraisal away.
MAX_LISTED_HYPOTHESIS_STATEMENT_LENGTH = 160

#: Said on every approval response. The whole risk of recording permission is
#: that recording it reads like using it.
NO_RESEARCH_STARTED_NOTICE = (
    "No research execution was started. Nothing was fetched, no model was "
    "called, and no background work was queued."
)

#: One bounded note per verdict, for a person rather than for a parser. Nothing
#: reads these back; the verdict itself is the structured value.
_AUTHORIZATION_VERDICT_NOTES: dict[ResearchPlanAuthorizationVerdict, str] = {
    ResearchPlanAuthorizationVerdict.VALID: "This approval covers exactly this plan.",
    ResearchPlanAuthorizationVerdict.DIGEST_MISMATCH: (
        "The plan changed after it was previewed, so the approval no longer "
        "describes it. Preview the new plan and approve that instead."
    ),
    ResearchPlanAuthorizationVerdict.RUN_MISMATCH: (
        "This approval was given for a different research run."
    ),
    ResearchPlanAuthorizationVerdict.CAPABILITY_MISMATCH: (
        "The approval grants capabilities this plan does not declare."
    ),
    ResearchPlanAuthorizationVerdict.EXPIRED: (
        "This approval has expired. Approvals are not renewed; preview the "
        "plan again to give a new one."
    ),
    ResearchPlanAuthorizationVerdict.UNKNOWN: (
        "No recorded approval was named, or none with that identity exists."
    ),
    ResearchPlanAuthorizationVerdict.ALREADY_CONSUMED: (
        "This approval has already been used. One approval permits one "
        "attempt, whether or not that attempt succeeded."
    ),
    ResearchPlanAuthorizationVerdict.BUDGET_EXCEEDED: (
        "This work asks for a wider budget than was approved."
    ),
    ResearchPlanAuthorizationVerdict.DISCLOSURE_UNSATISFIED: (
        "This work asks to disclose more to a model than was approved."
    ),
    ResearchPlanAuthorizationVerdict.NOT_RECORDED: (
        "The approval could not be durably written as used, so nothing was "
        "started. An approval that is not recorded as spent would still be "
        "available after a restart."
    ),
}

_WEAKNESS_CLASS_DISCLAIMER = (
    "A weakness class is a concept, not a finding. Recording or relating "
    "one says nothing about whether any system, product, or person is affected."
)


class ResponseComposer:
    """Creates user-facing response models without orchestration logic."""

    _KNOWLEDGE_CONTEXT_MAX_CHARS_PER_RESULT = 600
    _TURKISH_GREETING_PHRASES = frozenset({"merhaba", "selam"})

    def greeting(self, request: BrainRequest) -> BrainResponse:
        """Compose the deterministic greeting response."""
        greeting_candidate = request.message.casefold().strip().rstrip("!?.")
        return BrainResponse(
            message=(
                "Merhaba! Ben Hypatia."
                if greeting_candidate in self._TURKISH_GREETING_PHRASES
                else "Hello! I am Hypatia."
            ),
            request_id=request.request_id,
            intent="greeting",
            memory_count=0,
        )

    def message(self, request: BrainRequest) -> BrainResponse:
        """Compose the deterministic generic message response."""
        return BrainResponse(
            message=f"I received your message: {request.message}",
            request_id=request.request_id,
            intent="message",
            memory_count=0,
        )

    def session_renamed(
        self,
        request: BrainRequest,
        result: SessionRenameResult,
    ) -> BrainResponse:
        """Compose a successful session rename response."""
        return BrainResponse(
            message="\n".join(
                [
                    "Rename complete:",
                    f"Source: {result.source_session_id}",
                    f"Target: {result.target_session_id}",
                    f"Memory records updated: {result.memory_record_count}",
                    "Active session changed: "
                    f"{'yes' if result.active_session_changed else 'no'}",
                    "Status: committed",
                ]
            ),
            request_id=request.request_id,
            intent="session_rename",
            memory_count=result.memory_record_count,
        )

    def session_rename_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose an unsuccessful session rename response."""
        return BrainResponse(
            message=f"Rename failed:\nReason: {message}",
            request_id=request.request_id,
            intent="session_rename",
            memory_count=0,
            success=False,
        )

    def session_rename_preview(
        self,
        request: BrainRequest,
        preview: SessionRenamePreview,
    ) -> BrainResponse:
        """Compose a successful read-only session rename preview."""
        memory_id_lines = (
            [
                "Memory IDs:",
                *(f"- {memory_id}" for memory_id in preview.memory_record_ids),
            ]
            if preview.memory_record_ids
            else []
        )
        return BrainResponse(
            message="\n".join(
                [
                    "Rename preview:",
                    f"Source: {preview.source_session_id}",
                    f"Target: {preview.target_session_id}",
                    f"Affected memories: {preview.memory_record_count}",
                    *memory_id_lines,
                    "Changes: ready",
                ]
            ),
            request_id=request.request_id,
            intent="session_rename_preview",
            memory_count=preview.memory_record_count,
        )

    def session_rename_preview_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose an unsuccessful session rename preview response."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="session_rename_preview",
            memory_count=0,
            success=False,
        )

    def session_delete_preview(
        self,
        request: BrainRequest,
        session_id: str,
        memory_ids: tuple[str, ...],
        decision_status: SessionDeleteStatus,
        decision_reason: str,
    ) -> BrainResponse:
        """Compose a deterministic, read-only delete preview."""
        lines = [
            "Delete preview:",
            f"Session: {session_id}",
        ]
        lines.append(f"Decision: {decision_status.value}")
        if decision_status is SessionDeleteStatus.ALLOW:
            lines.extend(
                [
                    f"Affected memories: {len(memory_ids)}",
                    "Changes: ready",
                ]
            )
        else:
            lines.append(f"Reason: {decision_reason}")
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="session_delete_preview",
            memory_count=len(memory_ids),
            session_delete_allowed=decision_status is SessionDeleteStatus.ALLOW,
        )

    def session_delete_preview_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose a failed, side-effect-free delete preview."""
        return BrainResponse(
            message=f"Delete preview failed:\nReason: {message}",
            request_id=request.request_id,
            intent="session_delete_preview",
            memory_count=0,
            success=False,
        )

    def session_deleted(
        self,
        request: BrainRequest,
        result: SessionDeleteExecutionResult,
    ) -> BrainResponse:
        """Compose a successful response for a committed session deletion."""
        return BrainResponse(
            message="\n".join(
                [
                    "Session deleted:",
                    f"ID: {result.session_id}",
                    f"Memory records removed: {result.memory_records_removed}",
                    "Status: committed",
                ]
            ),
            request_id=request.request_id,
            intent="session_delete",
            memory_count=result.memory_records_removed,
        )

    def session_delete_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose a failed pre-commit session deletion response."""
        return BrainResponse(
            message=f"Delete failed:\nReason: {message}",
            request_id=request.request_id,
            intent="session_delete",
            memory_count=0,
            success=False,
        )

    def session_delete_event_failure(
        self,
        request: BrainRequest,
        result: SessionDeleteExecutionResult,
    ) -> BrainResponse:
        """Compose a committed deletion with an event-publication warning."""
        return BrainResponse(
            message="\n".join(
                [
                    "Session deleted:",
                    f"ID: {result.session_id}",
                    f"Memory records removed: {result.memory_records_removed}",
                    "Status: committed",
                    "Warning: lifecycle event publication failed",
                ]
            ),
            request_id=request.request_id,
            intent="session_delete",
            memory_count=result.memory_records_removed,
        )

    def session_rename_help(self, request: BrainRequest) -> BrainResponse:
        """Compose deterministic usage guidance for session rename commands."""
        return BrainResponse(
            message=(
                "Rename session:\n"
                "rename session <source> -- <target>\n"
                "\n"
                "Preview:\n"
                "preview rename session <source> -- <target>\n"
                "\n"
                "Check target:\n"
                "check rename target <target>\n"
                "\n"
                "Example:\n"
                "rename session work -- archive"
            ),
            request_id=request.request_id,
            intent="session_rename_help",
            memory_count=0,
        )

    def session_rename_candidates(
        self,
        request: BrainRequest,
        sessions: list[SessionRecord],
        active_session_id: str,
    ) -> BrainResponse:
        """Compose a deterministic list of sessions eligible for rename."""
        if not sessions:
            message = "No renameable sessions."
        else:
            lines = ["Renameable sessions:"]
            for session in sessions:
                active_suffix = (
                    " (active)" if session.session_id == active_session_id else ""
                )
                lines.append(f"{session.session_id}{active_suffix}")
            message = "\n".join(lines)
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="session_rename_candidates",
            memory_count=0,
        )

    def session_active(
        self,
        request: BrainRequest,
        session: SessionRecord,
    ) -> BrainResponse:
        """Compose the deterministic current active-session status."""
        return BrainResponse(
            message=f"Active session: {session.session_id}",
            request_id=request.request_id,
            intent="session_active",
            memory_count=0,
        )

    def session_help(self, request: BrainRequest) -> BrainResponse:
        """Compose deterministic usage guidance for supported session commands."""
        return BrainResponse(
            message=(
                "Session commands:\n"
                "create session <session_id>\n"
                "list sessions\n"
                "use session <session_id>\n"
                "active session\n"
                "session overview\n"
                "session details <session_id>\n"
                "session recent <session_id>\n"
                "session activity <session_id>\n"
                "session search <session_id> <query>\n"
                "list renameable sessions\n"
                "check rename target <target>\n"
                "preview rename session <source> -- <target>\n"
                "rename session <source> -- <target>\n"
                "help rename session"
            ),
            request_id=request.request_id,
            intent="session_help",
            memory_count=0,
        )

    def session_rename_target_check(
        self,
        request: BrainRequest,
        target_session_id: str,
        available: bool,
    ) -> BrainResponse:
        """Compose the deterministic read-only rename-target availability status."""
        status = "available" if available else "unavailable"
        return BrainResponse(
            message=f"Session rename target {status}: {target_session_id}",
            request_id=request.request_id,
            intent="session_rename_target_check",
            memory_count=0,
        )

    def session_rename_target_check_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose a controlled rename-target availability validation failure."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="session_rename_target_check",
            memory_count=0,
            success=False,
        )

    def search_success(
        self,
        request: BrainRequest,
        results: list[Chunk],
    ) -> BrainResponse:
        """Compose a successful knowledge search response."""
        return BrainResponse(
            message=f"I found {len(results)} matching knowledge chunks.",
            request_id=request.request_id,
            intent="search",
            memory_count=0,
            knowledge_results=results,
            knowledge_citations=[
                KnowledgeCitation.from_chunk(result) for result in results
            ],
        )

    def search_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose an unsuccessful knowledge search response."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="search",
            memory_count=0,
            success=False,
        )

    def knowledge_context_success(
        self,
        request: BrainRequest,
        results: list[Chunk],
    ) -> BrainResponse:
        """Compose an explicit, citation-visible bounded local context response."""
        citations = [KnowledgeCitation.from_chunk(result) for result in results]
        if not results:
            message = "Knowledge context: no matching local knowledge found."
        else:
            items = "\n\n".join(
                self._knowledge_context_item(index, result, citation)
                for index, (result, citation) in enumerate(
                    zip(results, citations, strict=True),
                    start=1,
                )
            )
            message = f"Knowledge context:\n\n{items}"
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="knowledge_context",
            memory_count=0,
            knowledge_results=results,
            knowledge_citations=citations,
        )

    def knowledge_context_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose a failed explicit local knowledge-context response."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="knowledge_context",
            memory_count=0,
            success=False,
        )

    def knowledge_graph_success(
        self,
        request: BrainRequest,
        results: list[Chunk],
        graph_view: KnowledgeGraphView,
    ) -> BrainResponse:
        """Compose an explicit, citation-visible local structural graph view."""
        citations = [KnowledgeCitation.from_chunk(result) for result in results]
        nodes_by_id = {node.node_id: node for node in graph_view.nodes}
        if not results:
            message = "Knowledge graph: no matching local knowledge found."
        else:
            edges = "\n".join(
                "- "
                f"{nodes_by_id[edge.source_node_id].label} "
                f"--{edge.relation.value}--> "
                f"{nodes_by_id[edge.target_node_id].label}"
                for edge in graph_view.edges
            )
            message = f"Knowledge graph:\n{edges}"
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="knowledge_graph",
            memory_count=0,
            knowledge_results=results,
            knowledge_citations=citations,
        )

    def knowledge_graph_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose a failed explicit local structural-graph request."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="knowledge_graph",
            memory_count=0,
            success=False,
        )

    def knowledge_list_success(
        self,
        request: BrainRequest,
        documents: list[KnowledgeDocumentReference],
    ) -> BrainResponse:
        """Compose a deterministic catalog of loaded local source identities."""
        if not documents:
            message = "No local knowledge sources are loaded."
        else:
            lines = ["Knowledge sources:"]
            for document in documents:
                source = document.source or "local source unavailable"
                lines.append(
                    "- "
                    f"{document.title} | {source} | "
                    f"chunks: {document.chunk_count} | id: {document.document_id}"
                )
            message = "\n".join(lines)
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="knowledge_list",
            memory_count=0,
            knowledge_documents=documents,
        )

    def knowledge_load_success(
        self,
        request: BrainRequest,
        document: KnowledgeDocumentReference,
    ) -> BrainResponse:
        """Report one explicitly selected source after successful local indexing."""
        return BrainResponse(
            message="\n".join(
                [
                    "Local knowledge source loaded:",
                    f"Title: {document.title}",
                    f"Source: {document.source}",
                    f"Type: {document.document_type.value}",
                    f"Chunks: {document.chunk_count}",
                    f"ID: {document.document_id}",
                ]
            ),
            request_id=request.request_id,
            intent="knowledge_load",
            memory_count=0,
            knowledge_documents=[document],
        )

    def knowledge_load_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Report a rejected or failed local-source load without side effects."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="knowledge_load",
            memory_count=0,
            success=False,
        )

    def research_source_load_success(
        self,
        request: BrainRequest,
        document: KnowledgeDocumentReference,
        *,
        run: ResearchRun | None = None,
        stage: SourceLoadStage = SourceLoadStage.INDEXED_WITHOUT_RUN,
        intent: str = "research_source_load",
    ) -> BrainResponse:
        """Report how far one source load got, never further than it went.

        The headline is chosen from the stage rather than from the presence of a
        document. A document exists in both successful outcomes, so leading with
        "loaded" and quietly appending a run line let a knowledge-only index read
        as an accepted research source.
        """
        attached = stage.attached_to_run and run is not None
        lines = [
            (
                "Research source accepted into the run:"
                if attached
                else "Indexed locally, but NOT accepted into a research run:"
            ),
            f"Title: {document.title}",
            f"Source: {document.source}",
            f"Type: {document.document_type.value}",
            f"Chunks: {document.chunk_count}",
            f"Local document ID: {document.document_id}",
            f"Stage reached: {stage.value}",
        ]
        if attached:
            assert run is not None
            lines.append(f"Research run: {run.run_id}")
            lines.append(f"Accepted sources in this run: {len(run.sources)}")
        lines.append(stage.summary)
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent=intent,
            memory_count=0,
            knowledge_documents=[document],
            research_runs=[] if run is None else [run],
            source_load_stage=stage,
        )

    def research_source_load_failure(
        self,
        request: BrainRequest,
        message: str,
        *,
        intent: str = "research_source_load",
    ) -> BrainResponse:
        """Report rejected external acquisition without hiding its safe reason."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent=intent,
            memory_count=0,
            success=False,
        )

    def research_source_candidate_acceptance_preview_success(
        self,
        request: BrainRequest,
        preview: ResearchSourceCandidateAcceptancePreview,
    ) -> BrainResponse:
        """Render the immutable candidate decision before any acquisition."""
        return BrainResponse(
            message="\n".join(
                [
                    "Research source candidate acceptance preview:",
                    f"Title: {preview.candidate.title}",
                    f"URL: {preview.candidate.url}",
                    f"Run: {preview.run_id}",
                    f"Discovery: {preview.discovery_id}",
                    f"Allowed: {'yes' if preview.allowed else 'no'}",
                    f"Reason: {preview.reason}",
                    "Status: preview only; source content was not loaded",
                ]
            ),
            request_id=request.request_id,
            intent="research_source_candidate_acceptance_preview",
            memory_count=0,
            success=preview.allowed,
            research_source_candidate_acceptance_preview=preview,
        )

    def research_source_candidate_acceptance_preview_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Report invalid candidate selection without network or mutation."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="research_source_candidate_acceptance_preview",
            memory_count=0,
            success=False,
        )

    def research_source_discovery_success(
        self,
        request: BrainRequest,
        run: ResearchRun,
    ) -> BrainResponse:
        """Render unaccepted candidate metadata from the latest audit record."""
        discovery = run.discoveries[-1]
        lines = [
            "Research source candidates discovered:",
            f"Run: {run.run_id}",
            f"Provider: {discovery.provider}",
            f"Query: {discovery.query}",
            f"Candidates: {len(discovery.candidates)}",
        ]
        for rank, candidate in enumerate(discovery.candidates, start=1):
            lines.extend(
                [
                    f"{rank}. {candidate.title}",
                    f"   URL: {candidate.url}",
                    f"   Snippet: {candidate.snippet or '[no snippet]'}",
                ]
            )
        lines.append("Status: candidates only; no source content was loaded")
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="research_source_discover",
            memory_count=0,
            research_runs=[run],
        )

    def research_source_discovery_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Report a controlled discovery failure without accepting a source."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="research_source_discover",
            memory_count=0,
            success=False,
        )

    def research_run_create_success(
        self,
        request: BrainRequest,
        run: ResearchRun,
        prior_lessons: tuple[ResearchFailureLesson, ...] = (),
    ) -> BrainResponse:
        """Report a newly persisted auditable research run.

        Prior lessons are printed after the run, never instead of it. The run
        exists by the time this is composed, so nothing in the advisory section
        may read as a condition on it.
        """
        lines = [
            "Research run created:",
            f"Question: {run.question}",
            f"Status: {run.status.value}",
            f"Sources: {len(run.sources)}",
            f"Discoveries: {len(run.discoveries)}",
            f"Evidence: {len(run.evidence)}",
            f"Assessments: {len(run.assessments)}",
            f"Comparison notes: {len(run.comparison_notes)}",
            f"Claims: {len(run.claims)}",
            f"Failures: {len(run.failures)}",
            f"ID: {run.run_id}",
        ]
        if prior_lessons:
            lines.extend(("", f"Possibly relevant prior lessons: {len(prior_lessons)}"))
            for lesson in prior_lessons:
                lines.append(f"- [{lesson.kind.value}] {lesson.statement}")
                lines.append(f"  from: {', '.join(lesson.provenance)}")
            lines.append(
                "These are advisory. This run was created either way, nothing "
                "was blocked, and no plan, claim, or confidence changed."
            )
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="research_run_create",
            memory_count=0,
            research_runs=[run],
            failure_lessons=prior_lessons,
        )

    def research_source_content_restoration_status(
        self,
        request: BrainRequest,
        status: ResearchSourceContentRestorationStatus,
    ) -> BrainResponse:
        """Render the captured aggregate without persistence or source details."""
        document_count: int | str = status.restored_document_count
        paragraph_count: int | str = status.restored_paragraph_count
        if not status.available:
            document_count = "unavailable"
            paragraph_count = "unavailable"
        return BrainResponse(
            message="\n".join(
                (
                    "Research content restoration status:",
                    f"Runtime: {status.state}",
                    f"Restored documents: {document_count}",
                    f"Restored paragraphs: {paragraph_count}",
                    "Network access: not used",
                    "Persistent writes: not used",
                )
            ),
            request_id=request.request_id,
            intent="research_source_content_restoration_status",
            memory_count=0,
            research_source_content_restoration_status=status,
        )

    def research_evidence_integrity_status(
        self,
        request: BrainRequest,
        status: ResearchEvidenceIntegrityStatus,
    ) -> BrainResponse:
        """Render aggregate evidence integrity without record or content details."""
        recorded: int | str = status.recorded_evidence_count
        matched: int | str = status.matched_evidence_count
        missing: int | str = status.missing_evidence_count
        changed: int | str = status.changed_evidence_count
        if not status.available:
            recorded = matched = missing = changed = "unavailable"
        return BrainResponse(
            message="\n".join(
                (
                    "Research evidence integrity status:",
                    f"Runtime: {status.state}",
                    f"Recorded evidence: {recorded}",
                    f"Matched restored paragraphs: {matched}",
                    f"Missing restored paragraphs: {missing}",
                    f"Changed restored paragraphs: {changed}",
                    "Network access: not used",
                    "Persistent writes: not used",
                )
            ),
            request_id=request.request_id,
            intent="research_evidence_integrity_status",
            memory_count=0,
            research_evidence_integrity_status=status,
        )

    def research_plan_draft_preview(
        self,
        request: BrainRequest,
        preview: ResearchPlanDraftPreview,
    ) -> BrainResponse:
        """Render one inert authored plan or its bounded validation reason."""
        plan = preview.plan
        if not preview.allowed:
            message = "\n".join(
                (
                    "Research plan draft rejected:",
                    f"Reason: {preview.reason}",
                    "Persistent writes: not used",
                    "Execution: not started",
                )
            )
        else:
            assert plan is not None
            lines = [
                "Research plan draft preview:",
                f"Question: {plan.question}",
                f"Steps: {len(plan.steps)}",
                f"Selected sources: {len(plan.selected_source_document_ids)}",
            ]
            for index, step in enumerate(plan.steps, start=1):
                selected_sources = ", ".join(step.selected_source_document_ids)
                lines.extend(
                    (
                        f"{index}. {step.instruction}",
                        f"   Selected sources: {selected_sources or 'none'}",
                    )
                )
                if step.discovery_provider is not None:
                    lines.append(
                        "   Source discovery provider: "
                        f"{step.discovery_provider.label}"
                    )
            lines.extend(
                (
                    f"Plan ID: {plan.plan_id}",
                    "Status: ready for explicit confirmation",
                    "Persistent writes: not used",
                    "Execution: not started",
                )
            )
            message = "\n".join(lines)
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="research_plan_draft_preview",
            memory_count=0,
            success=preview.allowed,
            research_plan_draft_preview=preview,
        )

    def learned_memory_audit(
        self,
        request: BrainRequest,
        report: LearnedMemoryAuditReport,
    ) -> BrainResponse:
        """Render bounded learned-memory health without any stored value."""
        lines = [
            "Learned memory audit:",
            f"Total learned records: {report.total_learned_records}",
            f"Active: {report.active_memories}",
            f"Superseded: {report.superseded_memories}",
            f"Superseded share: {report.superseded_ratio:.0%}",
            f"Distinct identities: {report.identities}",
            f"Identities with history: {report.identities_with_multiple_versions}",
            f"Most versions for one identity: {report.max_versions_for_one_identity}",
            f"Conflicting-history identities: {report.conflicting_history_identities}",
            f"Duplicate value candidates: {report.duplicate_value_candidates}",
        ]
        if report.conflicting_history_samples:
            lines.append("Conflicting history (sample):")
            lines.extend(
                f"- {sample.kind} | {sample.key} | versions: {sample.versions}"
                for sample in report.conflicting_history_samples
            )
        if report.duplicate_value_candidate_samples:
            lines.append("Duplicate value candidates (sample):")
            lines.extend(
                f"- {candidate.first_kind} | {candidate.first_key}"
                f" <-> {candidate.second_kind} | {candidate.second_key}"
                for candidate in report.duplicate_value_candidate_samples
            )
        if report.samples_truncated:
            lines.append("Samples truncated: yes")
        lines.extend(
            (
                "Candidates are for review only; no equivalence was decided.",
                "Persistent writes: not used",
                "Merges, deletions, and rewrites: not performed",
            )
        )
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="learned_memory_audit",
            memory_count=report.active_memories,
            learned_memory_audit=report,
        )

    def research_plan_execution_status(
        self,
        request: BrainRequest,
        state: ResearchPlanExecutionState,
        allowance: ResearchExecutionAllowance | None = None,
        next_capability: str = "",
    ) -> BrainResponse:
        """Render bounded execution state without implying performed research."""
        lines = [
            "Research plan execution:",
            f"Plan ID: {state.plan_id}",
            f"Status: {state.status.value}",
            f"Steps: {len(state.steps)}",
            f"Completed steps: {state.completed_steps}",
            f"Pending steps: {state.pending_steps}",
            f"Running step: {state.running_step_id or 'none'}",
        ]
        if next_capability:
            lines.append(f"Next step capability: {next_capability}")
        if allowance is not None:
            lines.append("")
            lines.extend(allowance.lines())
            lines.append(
                "Another advance is allowed: "
                + ("yes" if not allowance.exhausted else "no, the budget is spent")
            )
            lines.append("")
        for index, step in enumerate(state.steps, start=1):
            detail = f" | {step.detail}" if step.detail else ""
            operation = f" | operation: {step.operation}" if step.operation else ""
            lines.append(
                f"{index}. {step.step_id}: {step.status.value}{operation}{detail}"
            )
        if state.detail:
            lines.append(f"Detail: {state.detail}")
        interrupted = [
            step.step_id
            for step in state.steps
            if step.status is ResearchPlanStepStatus.INTERRUPTED
        ]
        if interrupted:
            lines.append("")
            lines.append(
                "Attempt interrupted; outcome unknown: " + ", ".join(interrupted) + "."
            )
            lines.append(
                "The attempt was charged and may have reached its provider "
                "before the process ended, so whether it did anything is not "
                "known. Advancing will not run it again."
            )
        ruled = [
            step
            for step in state.steps
            if step.resolution is not ResearchAttemptResolution.NONE
        ]
        for step in ruled:
            lines.append(f"Operator ruling on {step.step_id}: {step.resolution.value}")
        lines.append(f"Research operations performed: {state.steps_with_research_work}")
        if not state.performed_research_work:
            lines.append("No research work has run; this reports execution state only.")
        lines.extend(
            (
                "A completed operation means the operation ran; it is not "
                "evidence and not a verified claim.",
                "Evidence, assessment, and claims: not established here",
                "Persistent writes: not used",
                "Execution state: in-memory only, lost when Hypatia exits",
            )
        )
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="research_plan_execution",
            memory_count=0,
            research_plan_execution=state,
        )

    def background_task_status(
        self,
        request: BrainRequest,
        task: BackgroundResearchTask,
    ) -> BrainResponse:
        """Render one background task without any research content."""
        message = "\n".join(
            (
                "Background research task:",
                f"Task ID: {task.task_id}",
                f"Execution ID: {task.execution_id}",
                f"Status: {task.status.value}",
                f"Retries: {task.retry_count} of {task.max_retries}",
                f"Last outcome: {task.outcome or 'none'}",
                "Budget: "
                f"{task.budget.max_step_advances} step(s), "
                f"{task.budget.max_network_operations} network, "
                f"{task.budget.max_llm_operations} model, "
                f"{task.budget.max_seconds:.0f}s",
                "Scheduling only; running a task establishes no evidence and "
                "verifies no claim.",
            )
        )
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="background_research_task",
            memory_count=0,
            background_research_task=task,
        )

    def background_task_missing(
        self,
        request: BrainRequest,
        task_id: str,
    ) -> BrainResponse:
        """Report an unknown task without inventing one."""
        message = "\n".join(
            (
                "Background research task not found:",
                f"Task ID: {task_id}",
                "No task with that identifier is known to this scheduler.",
            )
        )
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="background_research_task",
            memory_count=0,
            success=False,
        )

    def background_task_rejected(
        self,
        request: BrainRequest,
        reason: str,
    ) -> BrainResponse:
        """Report one bounded refusal without changing any task."""
        message = "\n".join(
            (
                "Background research task rejected:",
                f"Reason: {reason}",
                "No task state changed.",
            )
        )
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="background_research_task",
            memory_count=0,
            success=False,
        )

    def background_task_list(
        self,
        request: BrainRequest,
        tasks: tuple[BackgroundResearchTask, ...],
    ) -> BrainResponse:
        """Render bounded task identities and statuses only."""
        lines = [f"Background research tasks: {len(tasks)}"]
        lines.extend(
            f"- {task.task_id}: {task.status.value}"
            f" (retries {task.retry_count}/{task.max_retries})"
            for task in tasks
        )
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="background_research_task",
            memory_count=0,
        )

    def background_worker_cycle(
        self,
        request: BrainRequest,
        ran: tuple[BackgroundResearchTask, ...],
        tasks: tuple[BackgroundResearchTask, ...],
    ) -> BrainResponse:
        """Report exactly what one bounded worker cycle did."""
        lines = [
            "Background worker cycle:",
            f"Tasks run this cycle: {len(ran)}",
        ]
        lines.extend(
            f"- {task.task_id}: {task.status.value} ({task.outcome or 'none'})"
            for task in ran
        )
        lines.extend(
            (
                f"Known tasks: {len(tasks)}",
                "One cycle runs a bounded number of approved tasks and stops.",
                "Running a task establishes no evidence and verifies no claim.",
            )
        )
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="background_research_task",
            memory_count=0,
        )

    def live_research_not_performed(
        self,
        request: BrainRequest,
        kind: LiveInformationRequestKind,
        summary: CanonicalResearchSummary,
    ) -> BrainResponse:
        """Say plainly that no live research ran, and offer the real workflow.

        The statement comes first and the counters follow. Someone asking a
        normal question should learn in the first sentence that nothing was
        researched, without reading a diagnostic to find out.
        """
        language = detect_response_language(request.message)
        if kind is LiveInformationRequestKind.URL_ACCESS:
            return self._url_not_opened(request, kind, summary)
        lines = [
            phrase("no_live_research", language),
            phrase("use_research", language),
            "",
            phrase("details_heading", language),
            f"- request kind: {kind.value}",
            *(f"- {line}" for line in summary.lines()),
        ]
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="live_research_declined",
            memory_count=0,
            canonical_research_summary=summary,
            live_information_request=kind,
        )

    def _url_not_opened(
        self,
        request: BrainRequest,
        kind: LiveInformationRequestKind,
        summary: CanonicalResearchSummary,
    ) -> BrainResponse:
        """Report that a link was not opened, and claim nothing about the site.

        Not fetching a page and a page being unreachable are different facts,
        and only one of them was established. Saying the site is inaccessible
        would be a claim about someone else's server made without contacting it.
        """
        language = detect_response_language(request.message)
        lines = [
            phrase("url_not_opened", language),
            phrase("url_unknown_reachability", language),
            phrase("url_use_research", language),
            "",
            phrase("details_heading", language),
            *(f"- {line}" for line in summary.lines()),
        ]
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="live_research_declined",
            memory_count=0,
            canonical_research_summary=summary,
            live_information_request=kind,
        )

    def research_evidence_provenance(
        self,
        request: BrainRequest,
        summary: CanonicalResearchSummary,
    ) -> BrainResponse:
        """Answer an evidence question from persisted counts, never from prose."""
        language = detect_response_language(request.message)
        lines = [
            phrase(self._evidence_phrase_key(summary), language),
            phrase("nothing_fabricated", language),
            "",
            phrase("evidence_heading", language),
            *(f"- {line}" for line in summary.lines()),
        ]
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="research_evidence_provenance",
            memory_count=0,
            canonical_research_summary=summary,
            live_information_request=(LiveInformationRequestKind.EVIDENCE_PROVENANCE),
        )

    @staticmethod
    def _evidence_phrase_key(summary: CanonicalResearchSummary) -> str:
        """Choose the sentence from the same counters the reply prints.

        The previous version branched on whether anything at all was recorded,
        so a run with no sources fell through to "Sources exist but no evidence
        record does" while printing "Sources accepted: 0" two lines above. The
        prose now reads the same two numbers the reader can see.
        """
        if summary.evidence_count:
            return "evidence_recorded"
        if summary.source_count:
            return "evidence_sources_without_evidence"
        return "evidence_none_at_all"

    def research_reflection(
        self,
        request: BrainRequest,
        report: ResearchReflectionReport,
        stored: bool,
    ) -> BrainResponse:
        """Render how a run went, never what its subject turned out to be."""
        lines = [
            "Research reflection:",
            f"Run ID: {report.run_id}",
            f"Findings: {len(report.findings)} ({len(report.lessons)} to learn from)",
            "",
        ]
        lines.extend(
            f"- [{finding.kind.value}] {finding.detail}" for finding in report.findings
        )
        lines.extend(
            (
                "",
                "Canonical research state for this run:",
                *report.summary.lines(),
                "",
                "Stored." if stored else "Not stored.",
                "This describes how the research went, not whether its "
                "conclusions are true. Reflecting performed no operation, "
                "established no evidence, and promoted nothing.",
            )
        )
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="research_reflection",
            memory_count=0,
            research_reflection=report,
        )

    def research_reflection_list(
        self,
        request: BrainRequest,
        reports: tuple[ResearchReflectionReport, ...],
    ) -> BrainResponse:
        """Render stored reflections without producing a new one."""
        lines = [f"Stored reflections: {len(reports)}"]
        lines.extend(
            f"- {report.report_id}: {len(report.findings)} finding(s), "
            f"{len(report.lessons)} lesson(s)"
            for report in reports
        )
        lines.append("Listing reflections performs no research.")
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="research_reflection",
            memory_count=0,
            research_reflections=reports,
        )

    def research_reflection_persistence_failed(
        self,
        request: BrainRequest,
        report: ResearchReflectionReport,
    ) -> BrainResponse:
        """Report a reflection that exists here but was not written down."""
        return BrainResponse(
            message="\n".join(
                (
                    "This reflection was not durably written.",
                    f"Report: {report.report_id}",
                    "Durable write: failed.",
                    "Restarting Hypatia may lose it.",
                    "Reflecting on this run again retries the write.",
                    "No research run, claim, evidence, or assessment changed.",
                )
            ),
            request_id=request.request_id,
            intent="research_reflection",
            memory_count=0,
            success=False,
            research_reflection=report,
        )

    def research_reflection_rejected(
        self,
        request: BrainRequest,
        reason: str,
    ) -> BrainResponse:
        """Report one bounded refusal without storing anything."""
        message = "\n".join(
            (
                "Research reflection rejected:",
                f"Reason: {reason}",
                "Nothing was stored and no run changed.",
            )
        )
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="research_reflection",
            memory_count=0,
            success=False,
        )

    def failure_lessons(
        self,
        request: BrainRequest,
        lessons: tuple[ResearchFailureLesson, ...],
        stored: bool,
        *,
        dropped: int = 0,
    ) -> BrainResponse:
        """Render lessons together with the records that make them checkable."""
        lines = [
            "Failure lessons:",
            f"Lessons: {len(lessons)}",
            "",
        ]
        for lesson in lessons:
            lines.append(f"- [{lesson.kind.value}] {lesson.statement}")
            lines.append(f"  from: {', '.join(lesson.provenance)}")
        if dropped:
            lines.append(f"Beyond the per-run limit, not derived: {dropped}")
        lines.extend(
            (
                "",
                "Remembered." if stored else "Not remembered.",
                "A lesson records that something did not work here, not that it "
                "cannot work. Deriving one performed no research and changed no "
                "run, hypothesis, claim, or assessment.",
            )
        )
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="failure_memory",
            memory_count=0,
            failure_lessons=lessons,
        )

    def failure_lesson_list(
        self,
        request: BrainRequest,
        lessons: tuple[ResearchFailureLesson, ...],
    ) -> BrainResponse:
        """Render everything remembered, deriving nothing new.

        The lesson leads, for the reason the hypothesis listing does: a
        catalogue identified only by record ID cannot be read by anyone
        deciding what to do about it.
        """
        lines = [f"Remembered failure lessons: {len(lessons)}"]
        for lesson in lessons:
            lines.append(f"- [{lesson.kind.value}] {lesson.statement}")
            lines.append(f"  {lesson.lesson_id} ({len(lesson.provenance)} record(s))")
        lines.append("Listing lessons performs no research.")
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="failure_memory",
            memory_count=0,
            failure_lessons=lessons,
        )

    def failure_lessons_persistence_failed(
        self,
        request: BrainRequest,
        lessons: tuple[ResearchFailureLesson, ...],
        *,
        dropped: int = 0,
    ) -> BrainResponse:
        """Report lessons retained only in memory after a durable-write failure."""
        lines = [
            "Failure lessons were not durably remembered.",
            f"Lessons retained in this process: {len(lessons)}",
        ]
        if dropped:
            lines.append(f"Beyond the per-run limit, not derived: {dropped}")
        lines.extend(
            (
                "Durable write: failed.",
                "Restarting Hypatia may lose these in-memory lessons.",
                "No research run, hypothesis, claim, or assessment changed.",
            )
        )
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="failure_memory",
            memory_count=0,
            success=False,
            failure_lessons=lessons,
        )

    def failure_lesson_recall(
        self,
        request: BrainRequest,
        lessons: tuple[ResearchFailureLesson, ...],
    ) -> BrainResponse:
        """Offer prior lessons as advice, never as a decision."""
        lines = [
            "Possibly relevant prior lessons:",
            f"Lessons: {len(lessons)}",
            "",
        ]
        for lesson in lessons:
            lines.append(f"- [{lesson.kind.value}] {lesson.statement}")
            lines.append(f"  from: {', '.join(lesson.provenance)}")
        if not lessons:
            lines.append("Nothing remembered overlaps this question.")
        lines.extend(
            (
                "",
                "These are advisory. Nothing was blocked, no capability was "
                "refused, and no claim was downgraded. Something failing once "
                "is not a reason not to try it.",
            )
        )
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="failure_memory",
            memory_count=0,
            failure_lessons=lessons,
        )

    def failure_memory_rejected(
        self,
        request: BrainRequest,
        reason: str,
    ) -> BrainResponse:
        """Report one bounded refusal without remembering anything."""
        message = "\n".join(
            (
                "Failure memory request rejected:",
                f"Reason: {reason}",
                "Nothing was remembered and no run changed.",
            )
        )
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="failure_memory",
            memory_count=0,
            success=False,
        )

    def research_calibration(
        self,
        request: BrainRequest,
        report: ResearchCalibrationReport,
    ) -> BrainResponse:
        """Render the fit between authored claims and their own support."""
        lines = [
            "Claim calibration:",
            f"Run ID: {report.run_id}",
            f"Claims: {len(report.calibrations)}",
            f"Needing a second look: {len(report.needing_attention)}",
            f"Claims with source warnings: {len(report.warned)} "
            f"({report.warning_count} warning(s))",
            "",
        ]
        for entry in report.calibrations:
            lines.append(f"- {entry.claim_id} [{entry.verdict.value}]")
            lines.append("  Claim:")
            lines.extend(f"    {line}" for line in entry.claim_text.splitlines())
            lines.append(f"  {entry.summary()}")
            lines.append(f"  evidence IDs: {', '.join(entry.evidence_ids)}")
            lines.append(
                "  source document IDs: " f"{', '.join(entry.source_document_ids)}"
            )
            lines.append(
                f"  sources {entry.profile.source_count}, "
                f"evidence {entry.profile.evidence_count}, "
                f"assessed {entry.profile.assessed_source_count}"
            )
            # The warnings are listed under the claim but never folded into its
            # verdict. They answer a different question: not whether the claim
            # outruns its support, but whether somebody who read one of those
            # sources wrote down a reason to look again.
            for warning in entry.warnings:
                lines.append(f"  ! {warning.summary()}")
            if not entry.warnings:
                lines.append("  No assessment-aware warnings.")
        if not report.calibrations:
            lines.append("This run has no active claims to calibrate.")
        lines.extend(
            (
                "",
                "No claim was changed. A supported ceiling is what our own "
                "record can carry, not a verdict on the claim: meeting it does "
                "not make a claim true, and exceeding it does not make one "
                "false. Understating is never reported as a problem.",
                "",
                "Warnings are warnings only. Nothing was corrected: no "
                "confidence was lowered, no claim withdrawn, no evidence "
                "removed, and no source rejected. They report what a person "
                "recorded about a source, which is a reason to look rather "
                "than a finding that the claim is wrong. A claim with no "
                "warnings has not been verified — it may simply be resting on "
                "sources nobody has assessed yet.",
            )
        )
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="research_calibration",
            memory_count=0,
            research_calibration=report,
        )

    def research_calibration_rejected(
        self,
        request: BrainRequest,
        reason: str,
    ) -> BrainResponse:
        """Report one bounded refusal without changing any claim."""
        message = "\n".join(
            (
                "Claim calibration rejected:",
                f"Reason: {reason}",
                "No claim changed.",
            )
        )
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="research_calibration",
            memory_count=0,
            success=False,
        )

    def research_claim_revision_preparation(
        self,
        request: BrainRequest,
        preparation: ResearchClaimRevisionPreparation,
    ) -> BrainResponse:
        """Render one inert bridge from calibration to human authoring."""
        calibration = preparation.calibration
        lines = [
            "Claim review preparation:",
            f"Run ID: {preparation.run_id}",
            f"Current claim ID: {calibration.claim_id}",
            "Current claim:",
        ]
        lines.extend(f"  {line}" for line in calibration.claim_text.splitlines())
        lines.extend(
            (
                f"Calibration: {calibration.summary()}",
                f"Verdict: {calibration.verdict.value}",
                "Current evidence IDs: "
                f"{', '.join(preparation.current_evidence_ids)}",
                "Current source document IDs: "
                f"{', '.join(preparation.current_source_document_ids)}",
                "If you choose to author a replacement, supersedes claim ID: "
                f"{preparation.supersedes_claim_id}",
            )
        )
        for warning in calibration.warnings:
            lines.append(f"Warning to review: {warning.summary()}")
        if not calibration.warnings:
            lines.append("No assessment-aware warning accompanies this mismatch.")
        lines.extend(
            (
                "",
                "No replacement was drafted or recorded. Hypatia did not choose "
                "new claim text, an epistemic state, or confidence. The IDs above "
                "describe the current claim only; a person must decide what, if "
                "anything, a separately previewed revision should say and cite.",
                "No claim, evidence, source, plan, authorization, execution, or "
                "background task changed.",
            )
        )
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="research_calibration_revision_prepare",
            memory_count=0,
            research_claim_revision_preparation=preparation,
        )

    def research_claim_revision_preparation_rejected(
        self,
        request: BrainRequest,
        reason: str,
    ) -> BrainResponse:
        """Refuse an invalid preparation request without changing a claim."""
        return BrainResponse(
            message="\n".join(
                (
                    "Claim review preparation rejected:",
                    f"Reason: {reason}",
                    "No claim, confidence, evidence, or research state changed.",
                )
            ),
            request_id=request.request_id,
            intent="research_calibration_revision_prepare",
            memory_count=0,
            success=False,
        )

    def provider_comparison(
        self,
        request: BrainRequest,
        report: ResearchProviderComparisonReport,
    ) -> BrainResponse:
        """Render both provider result sets, preferring neither."""
        return BrainResponse(
            message="\n".join(report.lines()),
            request_id=request.request_id,
            intent="provider_comparison",
            memory_count=0,
            research_provider_comparison=report,
        )

    def provider_comparison_rejected(
        self,
        request: BrainRequest,
        reason: str,
    ) -> BrainResponse:
        """Explain why there is nothing to compare, having compared nothing."""
        return BrainResponse(
            message="\n".join(
                (
                    "Provider comparison rejected:",
                    f"Reason: {reason}",
                    "No provider was contacted and nothing was changed.",
                )
            ),
            request_id=request.request_id,
            intent="provider_comparison",
            memory_count=0,
            success=False,
        )

    def provider_quality(
        self,
        request: BrainRequest,
        report: ResearchProviderQualityReport,
    ) -> BrainResponse:
        """Render how assessed provider samples performed, choosing nothing."""
        return BrainResponse(
            message="\n".join(
                ("Provider quality — descriptive only:", "", *report.lines())
            ),
            request_id=request.request_id,
            intent="provider_quality",
            memory_count=0,
            research_provider_quality=report,
        )

    def paired_provider_quality(
        self,
        request: BrainRequest,
        report: ResearchPairedProviderQualityReport,
    ) -> BrainResponse:
        """Render aligned same-question observations, choosing nothing."""
        return BrainResponse(
            message="\n".join(
                ("Paired provider quality — descriptive only:", "", *report.lines())
            ),
            request_id=request.request_id,
            intent="paired_provider_quality",
            memory_count=0,
            research_paired_provider_quality=report,
        )

    def source_reputation(
        self,
        request: BrainRequest,
        reputations: tuple[SourceReputation, ...],
    ) -> BrainResponse:
        """Render our own assessment history per origin, gating nothing."""
        lines = [
            "Source reputation:",
            f"Origins: {len(reputations)}",
            "",
        ]
        for reputation in reputations:
            lines.extend(f"  {line}" for line in reputation.lines())
            lines.append("")
        if not reputations:
            lines.append("No accepted source matches, so there is nothing to report.")
            lines.append("")
        lines.extend(
            (
                "This counts our own assessments, not the publisher. A standing "
                "of provisional means the sample is too small to generalise "
                "from, and no standing gates anything: no fetch was refused, no "
                "evidence discounted, no source pre-assessed, and no assessment "
                "changed.",
            )
        )
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="source_reputation",
            memory_count=0,
            source_reputations=reputations,
        )

    def source_reputation_rejected(
        self,
        request: BrainRequest,
        reason: str,
    ) -> BrainResponse:
        """Report one bounded refusal without changing any assessment."""
        message = "\n".join(
            (
                "Source reputation request rejected:",
                f"Reason: {reason}",
                "No assessment changed.",
            )
        )
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="source_reputation",
            memory_count=0,
            success=False,
        )

    def hypothesis_appraisal(
        self,
        request: BrainRequest,
        appraisal: HypothesisAppraisal,
    ) -> BrainResponse:
        """Render one hypothesis and its standing, concluding nothing."""
        lines = [
            "Research hypothesis:",
            f"ID: {appraisal.hypothesis.hypothesis_id}",
            *appraisal.lines(),
            "",
            "Supporting and opposing evidence are counted separately and never "
            "netted. No status here means the hypothesis is true: supported "
            "requires more than one independent supporting source, an active "
            "authored trust assessment of at least medium for every supporting "
            "source, and no opposing evidence. That is still where most "
            "abandoned theories stood right until the observation that undid "
            "them.",
        ]
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="research_hypothesis",
            memory_count=0,
            hypothesis_appraisal=appraisal,
        )

    def hypothesis_history(
        self,
        request: BrainRequest,
        view: HypothesisHistoryView,
    ) -> BrainResponse:
        """Render one hypothesis's standing beside what was withdrawn from it."""
        return BrainResponse(
            message="\n".join(view.lines()),
            request_id=request.request_id,
            intent="research_hypothesis_history",
            memory_count=0,
            hypothesis_history=view,
        )

    def hypothesis_list(
        self,
        request: BrainRequest,
        appraisals: tuple[HypothesisAppraisal, ...],
    ) -> BrainResponse:
        """Render every hypothesis with its derived standing.

        The statement leads. A list that identified each entry only by record
        ID is unreadable by anyone deciding which hypothesis to act on, which
        is the entire reason to look at the list.
        """
        lines = [f"Research hypotheses: {len(appraisals)}"]
        for appraisal in appraisals:
            statement = appraisal.hypothesis.one_line_statement(
                MAX_LISTED_HYPOTHESIS_STATEMENT_LENGTH
            )
            lines.append(f'- [{appraisal.status.value}] "{statement}"')
            lines.append(
                f"  {appraisal.hypothesis.hypothesis_id} | "
                f"for {appraisal.supporting_source_count} / "
                f"against {appraisal.opposing_source_count} source(s); "
                f"support trust {appraisal.supporting_assessed_source_count}/"
                f"{appraisal.supporting_source_count} assessed, lowest "
                f"{appraisal.lowest_supporting_trust.value}"
            )
        lines.append("Listing hypotheses performs no research and settles nothing.")
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="research_hypothesis",
            memory_count=0,
            hypothesis_appraisals=appraisals,
        )

    def hypothesis_rejected(
        self,
        request: BrainRequest,
        reason: str,
    ) -> BrainResponse:
        """Report one bounded refusal without changing any hypothesis."""
        message = "\n".join(
            (
                "Research hypothesis request rejected:",
                f"Reason: {reason}",
                "No hypothesis changed.",
            )
        )
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="research_hypothesis",
            memory_count=0,
            success=False,
        )

    def hypothesis_persistence_failed(
        self,
        request: BrainRequest,
        appraisal: HypothesisAppraisal,
    ) -> BrainResponse:
        """Report a hypothesis change retained only in the current process."""
        return BrainResponse(
            message="\n".join(
                (
                    "Research hypothesis was not durably saved.",
                    f"ID: {appraisal.hypothesis.hypothesis_id}",
                    f"Status in this process: {appraisal.status.value}",
                    "Durable write: failed.",
                    "Restarting Hypatia may lose this in-memory change.",
                    "No status here means the hypothesis is true.",
                )
            ),
            request_id=request.request_id,
            intent="research_hypothesis",
            memory_count=0,
            success=False,
            hypothesis_appraisal=appraisal,
        )

    def vulnerability_family(
        self,
        request: BrainRequest,
        family: VulnerabilityFamily,
    ) -> BrainResponse:
        """Render one recorded weakness class."""
        message = "\n".join(
            (
                "Vulnerability family recorded:",
                f"ID: {family.family_id}",
                f"Name: {family.name}",
                f"Weakness: {family.summary}",
                f"Generally prevented by: {family.prevention}",
                _WEAKNESS_CLASS_DISCLAIMER,
            )
        )
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="vulnerability_graph",
            memory_count=0,
            vulnerability_family=family,
        )

    def vulnerability_relation(
        self,
        request: BrainRequest,
        relation: VulnerabilityRelation,
    ) -> BrainResponse:
        """Render one authored edge between two weakness classes."""
        message = "\n".join(
            (
                "Vulnerability relation recorded:",
                f"{relation.from_family_id} {relation.kind.value} "
                f"{relation.to_family_id}",
                f"Because: {relation.rationale}",
                _WEAKNESS_CLASS_DISCLAIMER,
            )
        )
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="vulnerability_graph",
            memory_count=0,
            vulnerability_relation=relation,
        )

    def vulnerability_neighbourhood(
        self,
        request: BrainRequest,
        family: VulnerabilityFamily,
        related: tuple[RelatedFamily, ...],
        ancestors: tuple[VulnerabilityFamily, ...],
    ) -> BrainResponse:
        """Render what else is worth thinking about near one weakness class."""
        lines = [
            f"Around {family.name}:",
            f"Weakness: {family.summary}",
            "",
        ]
        if ancestors:
            lines.append("More general classes:")
            lines.extend(f"- {entry.name}" for entry in ancestors)
            lines.append("")
        lines.append(f"Related classes: {len(related)}")
        lines.extend(
            f"- {entry.family.name} ({entry.via.value}, depth {entry.depth})"
            for entry in related
        )
        if not related:
            lines.append("Nothing recorded relates to this one yet.")
        lines.extend(
            (
                "",
                "These are suggestions about what to read next, not about what "
                "to attack. " + _WEAKNESS_CLASS_DISCLAIMER,
            )
        )
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="vulnerability_graph",
            memory_count=0,
            vulnerability_family=family,
            related_vulnerability_families=related,
        )

    def vulnerability_family_list(
        self,
        request: BrainRequest,
        families: tuple[VulnerabilityFamily, ...],
    ) -> BrainResponse:
        """Render every recorded weakness class."""
        lines = [f"Vulnerability families: {len(families)}"]
        lines.extend(f"- {entry.family_id}: {entry.name}" for entry in families)
        lines.append(_WEAKNESS_CLASS_DISCLAIMER)
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="vulnerability_graph",
            memory_count=0,
            vulnerability_families=families,
        )

    def research_plan_authorization_preview(
        self,
        request: BrainRequest,
        preview: ResearchPlanAuthorizationPreview,
    ) -> BrainResponse:
        """Show exactly what confirming would record, having recorded nothing."""
        if preview.authorization is None:
            return BrainResponse(
                message="\n".join(
                    (
                        "Research plan approval preview:",
                        f"Reason: {preview.reason}",
                        "Nothing was approved and no research was started.",
                    )
                ),
                request_id=request.request_id,
                intent="research_plan_authorization",
                memory_count=0,
                success=False,
            )
        authorization = preview.authorization
        lines = [
            "Research plan approval preview:",
            f"Approval ID: {authorization.authorization_id}",
            "",
            # Both identities, adjacent and labelled. Someone approving needs
            # to see that the preview they are looking at is not the thing
            # being approved.
            f"Plan (this preview): {preview.plan_id}",
            f"Plan content approved: {authorization.plan_digest}",
            f"Research run: {authorization.research_run_id}",
            "",
            *self._authorization_terms(authorization),
            *_discovery_provider_lines(preview.discovery_providers),
            "",
            "Nothing is recorded until you confirm this exact approval.",
            preview.reason,
        ]
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="research_plan_authorization",
            memory_count=0,
            research_plan_authorization=authorization,
        )

    def research_plan_authorization_confirmed(
        self,
        request: BrainRequest,
        authorization: ResearchPlanAuthorization,
    ) -> BrainResponse:
        """Report one durably recorded approval that started nothing."""
        lines = [
            "Research plan approval recorded.",
            f"Approval ID: {authorization.authorization_id}",
            f"Plan content approved: {authorization.plan_digest}",
            f"Research run: {authorization.research_run_id}",
            "",
            *self._authorization_terms(authorization),
            "",
            NO_RESEARCH_STARTED_NOTICE,
        ]
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="research_plan_authorization",
            memory_count=0,
            research_plan_authorization=authorization,
        )

    def research_plan_authorization_write_failed(
        self,
        request: BrainRequest,
        authorization: ResearchPlanAuthorization,
    ) -> BrainResponse:
        """Report an approval kept here but not written down."""
        lines = [
            "This approval was not durably recorded.",
            f"Approval ID: {authorization.authorization_id}",
            "Durable write: failed.",
            "Restarting Hypatia may lose it.",
            "Approving the same plan again retries the write.",
            NO_RESEARCH_STARTED_NOTICE,
        ]
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="research_plan_authorization",
            memory_count=0,
            success=False,
            research_plan_authorization=authorization,
        )

    def research_plan_authorization_refused(
        self,
        request: BrainRequest,
        verdict: ResearchPlanAuthorizationVerdict,
    ) -> BrainResponse:
        """Report why a previewed approval no longer covers this work."""
        message = "\n".join(
            (
                "That approval was not recorded.",
                f"Verification: {verdict.value}",
                _AUTHORIZATION_VERDICT_NOTES[verdict],
                "Nothing was approved and no research was started.",
            )
        )
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="research_plan_authorization",
            memory_count=0,
            success=False,
        )

    def research_plan_authorization_rejected(
        self,
        request: BrainRequest,
        reason: str,
    ) -> BrainResponse:
        """Report one bounded refusal without recording anything."""
        message = "\n".join(
            (
                "Research plan approval request rejected:",
                f"Reason: {reason}",
                "Nothing was approved and no research was started.",
            )
        )
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="research_plan_authorization",
            memory_count=0,
            success=False,
        )

    def research_plan_authorization_list(
        self,
        request: BrainRequest,
        authorizations: tuple[ResearchPlanAuthorization, ...],
        moment: datetime,
    ) -> BrainResponse:
        """Report recorded approvals and whether each is still valid now."""
        lines = [f"Recorded research plan approvals: {len(authorizations)}"]
        for authorization in authorizations:
            consumption = authorization.consumption
            if consumption is not None:
                standing = "used"
            elif authorization.has_expired_at(moment):
                standing = "expired"
            else:
                standing = "valid now"
            lines.append(
                f"- [{standing}] {authorization.authorization_id} "
                f"({authorization.disclosure.value})"
            )
            lines.append(
                f"  plan {authorization.plan_digest} in run "
                f"{authorization.research_run_id}"
            )
            if consumption is None:
                lines.append("  unused")
            else:
                lines.append(
                    f"  used by {consumption.execution_id} "
                    f"at {consumption.consumed_at.isoformat()}"
                )
        lines.append(
            "An approval is a record, not standing permission. "
            + NO_RESEARCH_STARTED_NOTICE
        )
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="research_plan_authorization",
            memory_count=0,
            research_plan_authorizations=authorizations,
        )

    @staticmethod
    def _authorization_terms(
        authorization: ResearchPlanAuthorization,
    ) -> tuple[str, ...]:
        """Render the exact terms being approved, in one bounded block."""
        capabilities = ", ".join(
            sorted(capability.value for capability in authorization.capabilities)
        )
        budget = authorization.budget
        return (
            f"Capabilities: {capabilities}",
            f"Budget: {budget.max_step_advances} step(s), "
            f"{budget.max_network_operations} network operation(s), "
            f"{budget.max_llm_operations} model call(s), "
            f"{budget.max_seconds:g} second(s)",
            f"Model disclosure: {authorization.disclosure.value}",
            f"Authorized by: {authorization.authorized_by.value}",
            f"Approved at: {authorization.authorized_at.isoformat()}",
            f"Expires at: {authorization.expires_at.isoformat()}",
        )

    def vulnerability_graph_persistence_failed(
        self,
        request: BrainRequest,
        *,
        family: VulnerabilityFamily | None = None,
        relation: VulnerabilityRelation | None = None,
    ) -> BrainResponse:
        """Report a taxonomy entry that exists here but was not written down.

        The entry is kept in this process rather than discarded, so the work is
        not lost while the session lasts. Saying it was recorded would be the
        more comfortable answer and the wrong one: a taxonomy someone believes
        is saved, and is not, is worse than one they know they must re-enter.
        """
        if family is not None:
            subject = f"Family: {family.family_id}"
        elif relation is not None:
            subject = f"Relation: {relation.from_family_id} -> {relation.to_family_id}"
        else:
            subject = "Entry recorded in this process."
        message = "\n".join(
            (
                "The vulnerability graph was not durably written.",
                subject,
                "Durable write: failed.",
                "Restarting Hypatia may lose this entry.",
                "Recording it again retries the write.",
                _WEAKNESS_CLASS_DISCLAIMER,
            )
        )
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="vulnerability_graph",
            memory_count=0,
            success=False,
            vulnerability_family=family,
            vulnerability_relation=relation,
        )

    def vulnerability_graph_rejected(
        self,
        request: BrainRequest,
        reason: str,
    ) -> BrainResponse:
        """Report one bounded refusal without changing the graph."""
        message = "\n".join(
            (
                "Vulnerability graph request rejected:",
                f"Reason: {reason}",
                "The graph did not change.",
            )
        )
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="vulnerability_graph",
            memory_count=0,
            success=False,
        )

    def security_posture(
        self,
        request: BrainRequest,
        report: SecurityPostureReport,
    ) -> BrainResponse:
        """Render what was examined alongside what was found."""
        highest = report.highest_severity
        lines = [
            "Security posture audit:",
            *report.scope_lines(),
            f"Findings: {len(report.findings)} "
            f"({len(report.needing_action)} needing action)",
            f"Highest severity: {'none' if highest is None else highest.value}",
            "",
        ]
        lines.extend(
            f"- [{finding.severity.value}] {finding.kind.value} "
            f"({finding.subject_id}): {finding.detail}"
            for finding in report.findings
        )
        if report.clean:
            lines.append(
                "Nothing was found. That means these specific properties held "
                "in the data just now, not that the system is safe."
            )
        lines.extend(
            (
                "",
                "This audit read Hypatia's own records. It contacted no external "
                "system, examined nobody else's infrastructure, and repaired "
                "nothing: what to do about a source already accepted and "
                "reasoned from is a judgement it cannot make for you.",
            )
        )
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="security_posture",
            memory_count=0,
            security_posture=report,
        )

    def security_posture_rejected(
        self,
        request: BrainRequest,
        reason: str,
    ) -> BrainResponse:
        """Report one bounded refusal without auditing anything."""
        message = "\n".join(
            (
                "Security posture audit rejected:",
                f"Reason: {reason}",
                "Nothing was examined and nothing changed.",
            )
        )
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="security_posture",
            memory_count=0,
            success=False,
        )

    def knowledge_reconciliation(
        self,
        request: BrainRequest,
        report: KnowledgeReconciliationReport,
    ) -> BrainResponse:
        """Render what is indexed against what research actually uses."""
        lines = [
            "Knowledge reconciliation:",
            *report.lines(),
            "",
            "Knowledge-only means indexed locally and not referenced by any "
            "research run. That is a normal state for anything loaded for local "
            "search, not a problem and not a cleanup list.",
        ]
        if report.broken_references:
            lines.append(
                "A broken reference is a research run naming a document the "
                "local index does not hold. That one is genuine breakage."
            )
        lines.append(
            "This report read state only. Nothing was deleted, merged, or " "repaired."
        )
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="knowledge_reconciliation",
            memory_count=0,
            knowledge_reconciliation=report,
        )

    def knowledge_only_resources(
        self,
        request: BrainRequest,
        report: KnowledgeReconciliationReport,
    ) -> BrainResponse:
        """List indexed resources no research run references."""
        records = report.knowledge_only
        lines = [f"Knowledge-only resources: {len(records)}"]
        lines.extend(f"- {record.line()}" for record in records)
        if not records:
            lines.append("Every indexed resource is referenced by a research run.")
        lines.extend(
            (
                "",
                "These are indexed and searchable locally. They are not research "
                "evidence, and nothing here removes them.",
            )
        )
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="knowledge_reconciliation",
            memory_count=0,
            knowledge_reconciliation=report,
        )

    def curiosity_gaps(
        self,
        request: BrainRequest,
        preview: ResearchCuriosityPreview,
    ) -> BrainResponse:
        """Report detected gaps, which are absences in our record, not findings."""
        lines = [
            "Knowledge gaps detected:",
            f"Run ID: {preview.run_id}",
            f"Gaps: {preview.gap_count}",
        ]
        lines.extend(f"- {gap.kind.value}: {gap.summary}" for gap in preview.gaps)
        lines.append(
            "A gap describes what our own record is missing, not what is true."
        )
        lines.append("Nothing was researched, proposed, or stored.")
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="curiosity",
            memory_count=0,
            research_curiosity=preview,
        )

    def curiosity_preview(
        self,
        request: BrainRequest,
        preview: ResearchCuriosityPreview,
    ) -> BrainResponse:
        """Render ranked proposals and say plainly that none of them ran."""
        lines = [
            "Curiosity proposals:",
            f"Run ID: {preview.run_id}",
            f"Gaps: {preview.gap_count}",
            f"Questions: {preview.question_count}",
        ]
        lines.extend(
            f"- [{question.rank_score}] {question.text}"
            for question in preview.questions
        )
        lines.append(
            "Stored as proposals." if preview.stored else "Nothing was stored."
        )
        lines.append(
            "A proposed question is a suggestion, not a plan: none of these "
            "was researched, and none will run on its own."
        )
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="curiosity",
            memory_count=0,
            research_curiosity=preview,
        )

    def curiosity_question_list(
        self,
        request: BrainRequest,
        questions: tuple[ResearchCuriosityQuestion, ...],
    ) -> BrainResponse:
        """Render every stored proposal in rank order."""
        lines = [f"Curiosity questions: {len(questions)}"]
        lines.extend(
            f"- {question.question_id} [{question.rank_score}] "
            f"({question.status.value}): {question.text}"
            for question in questions
        )
        lines.append("Listing proposals performs no research.")
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="curiosity",
            memory_count=0,
            curiosity_questions=questions,
        )

    def curiosity_question_decided(
        self,
        request: BrainRequest,
        question: ResearchCuriosityQuestion,
    ) -> BrainResponse:
        """Record a ruling on one proposal without starting anything."""
        message = "\n".join(
            (
                "Curiosity question decided:",
                f"Question ID: {question.question_id}",
                f"Status: {question.status.value}",
                f"Rank: {question.rank_score}",
                "Accepting a question records intent only; it starts no "
                "research and queues no background task.",
            )
        )
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="curiosity",
            memory_count=0,
            curiosity_question=question,
        )

    def curiosity_question_missing(
        self,
        request: BrainRequest,
        question_id: str,
    ) -> BrainResponse:
        """Report an unknown proposal without inventing one."""
        message = "\n".join(
            (
                "Curiosity question not found:",
                f"Question ID: {question_id}",
                "No proposal with that identifier is stored.",
            )
        )
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="curiosity",
            memory_count=0,
            success=False,
        )

    def curiosity_persistence_failed(
        self,
        request: BrainRequest,
        subject: str,
    ) -> BrainResponse:
        """Report proposals or a ruling that exist here but were not written."""
        message = "\n".join(
            (
                "Curiosity was not durably written.",
                f"Kept in this process: {subject}.",
                "Durable write: failed.",
                "Restarting Hypatia may lose it.",
                "Repeating the request retries the write.",
                "No research run, claim, evidence, or assessment changed.",
            )
        )
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="curiosity",
            memory_count=0,
            success=False,
        )

    def curiosity_proposal(
        self,
        request: BrainRequest,
        proposal: CuriosityResearchProposal,
    ) -> BrainResponse:
        """Render one inert proposal, authorizing and starting nothing."""
        return BrainResponse(
            message="\n".join(proposal.lines()),
            request_id=request.request_id,
            intent="curiosity_prepare_proposal",
            memory_count=0,
            curiosity_proposal=proposal,
        )

    def curiosity_proposal_authorized(
        self,
        request: BrainRequest,
        proposal: CuriosityResearchProposal,
        authorization: ResearchPlanAuthorization,
    ) -> BrainResponse:
        """Report that a person approved this exact plan, and that it is idle.

        Both facts are stated because either alone is misleading. An approval
        that does not say it has not started reads like something happening; a
        plan that does not say it is approved reads like nothing was decided.
        """
        lines = [
            "RESEARCH PROPOSAL AUTHORIZED — approved by a person, not running",
            f"Curiosity question: {proposal.question}",
            f"Question ID: {proposal.curiosity_question_id}",
            f"Plan digest: {authorization.plan_digest}",
            f"Approval ID: {authorization.authorization_id}",
            f"Approved by: {authorization.authorized_by.value}",
            f"Approved at: {authorization.authorized_at.isoformat()}",
            f"Valid until: {authorization.expires_at.isoformat()}",
            "",
            "Nothing has started. This approval permits a later, separate "
            "action to begin exactly this plan; it does not begin it, and no "
            "step has run.",
        ]
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="curiosity_authorize_proposal",
            memory_count=0,
            curiosity_proposal=proposal,
            research_plan_authorization=authorization,
        )

    def curiosity_proposal_execution_started(
        self,
        request: BrainRequest,
        proposal: CuriosityResearchProposal,
        authorization_id: str,
        state: ResearchPlanExecutionState,
    ) -> BrainResponse:
        """Report one approved foreground start without implying a step ran."""
        lines = [
            "AUTHORIZED CURIOSITY PROPOSAL STARTED — running, zero steps run",
            f"Curiosity question: {proposal.question}",
            f"Question ID: {proposal.curiosity_question_id}",
            f"Plan digest: {proposal.digest}",
            f"Approval ID used: {authorization_id}",
            f"Execution ID: {state.plan_id}",
            f"Execution status: {state.status.value}",
            f"Completed steps: {state.completed_steps}",
            f"Pending steps: {state.pending_steps}",
            "Research operations performed: 0",
            "",
            "The approval is now used. No provider was contacted and no "
            "research step ran. The first step still requires a separate "
            "explicit Advance action.",
        ]
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="curiosity_start_authorized_proposal",
            memory_count=0,
            curiosity_proposal=proposal,
            research_plan_execution=state,
        )

    def curiosity_proposal_execution_resumed(
        self,
        request: BrainRequest,
        proposal: CuriosityResearchProposal,
        authorization_id: str,
        state: ResearchPlanExecutionState,
    ) -> BrainResponse:
        """Report one recovered execution without implying anything ran.

        Resuming is bookkeeping, not progress: it makes an execution that was
        already approved and already started reachable again in this process.
        The counts shown are the recorded ones, so a step that finished before
        the restart still reads as finished and will not be repeated.
        """
        lines = [
            "DURABLE CURIOSITY EXECUTION RESUMED — no step run",
            f"Curiosity question: {proposal.question}",
            f"Question ID: {proposal.curiosity_question_id}",
            f"Plan digest: {proposal.digest}",
            f"Approval ID already used: {authorization_id}",
            f"Execution ID: {state.plan_id}",
            f"Execution status: {state.status.value}",
            f"Completed steps: {state.completed_steps}",
            f"Pending steps: {state.pending_steps}",
            "Research operations performed: 0",
            "",
            "No new approval was created and the original one stays used. "
            "Nothing was performed and no provider was contacted. Any further "
            "step still requires a separate explicit Advance action.",
        ]
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="curiosity_resume_execution",
            memory_count=0,
            curiosity_proposal=proposal,
            research_plan_execution=state,
        )

    def curiosity_rejected(
        self,
        request: BrainRequest,
        reason: str,
    ) -> BrainResponse:
        """Report one bounded refusal without changing any proposal."""
        message = "\n".join(
            (
                "Curiosity request rejected:",
                f"Reason: {reason}",
                "No proposal changed.",
            )
        )
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="curiosity",
            memory_count=0,
            success=False,
        )

    def research_autonomy_result(
        self,
        request: BrainRequest,
        result: ResearchAutonomyResult,
    ) -> BrainResponse:
        """Render exactly what an autonomous run consumed and why it stopped."""
        message = "\n".join(
            (
                "Autonomous research run:",
                f"Plan ID: {result.plan_id}",
                f"Stopped because: {result.stop_reason.value}",
                f"Execution status: {result.execution_status}",
                f"Steps attempted: {result.steps_attempted}",
                f"Operations performed: {result.operations_performed}",
                f"Network operations: {result.network_operations}",
                f"LLM operations: {result.llm_operations}",
                f"Elapsed seconds: {result.elapsed_seconds:.3f}",
                "Only steps already authored and authorized were run.",
                "A completed operation is not evidence, not a verified claim, "
                "and not a research conclusion.",
                "Stopping within budget is a normal outcome, not a failure.",
            )
        )
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="research_autonomy",
            memory_count=0,
            research_autonomy=result,
        )

    def research_autonomy_missing(
        self,
        request: BrainRequest,
        plan_id: str,
    ) -> BrainResponse:
        """Refuse autonomy for an execution this process cannot advance."""
        message = "\n".join(
            (
                "Autonomous research run rejected:",
                f"Plan ID: {plan_id}",
                "This process holds no live execution for that plan.",
                "A restored execution cannot be advanced, and autonomy never "
                "creates or authorizes a plan of its own.",
            )
        )
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="research_autonomy",
            memory_count=0,
            success=False,
        )

    def research_plan_execution_restored(
        self,
        request: BrainRequest,
        snapshot: ResearchPlanExecutionSnapshot,
    ) -> BrainResponse:
        """Render restored durable state without implying a resumable run."""
        lines = [
            "Research plan execution (restored):",
            f"Plan ID: {snapshot.plan_id}",
            f"Status: {snapshot.status.value}",
            f"Steps: {len(snapshot.steps)}",
        ]
        for index, step in enumerate(snapshot.steps, start=1):
            operation = f" | operation: {step.operation}" if step.operation else ""
            lines.append(f"{index}. {step.step_id}: {step.status.value}{operation}")
        interrupted = sum(
            1
            for step in snapshot.steps
            if step.status is ResearchPlanStepStatus.INTERRUPTED
        )
        if interrupted:
            lines.append(
                f"Interrupted steps: {interrupted}. What those operations did is "
                "unknown; nothing was replayed."
            )
        lines.extend(
            (
                "Restored from durable state; this execution is not running.",
                "Authored step instructions and authorizations were not persisted, "
                "so a restored execution cannot be advanced.",
                "A completed operation means the operation ran; it is not "
                "evidence and not a verified claim.",
            )
        )
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="research_plan_execution",
            memory_count=0,
        )

    def research_plan_execution_missing(
        self,
        request: BrainRequest,
        plan_id: str,
    ) -> BrainResponse:
        """Report absent ephemeral state without inventing a resumable run."""
        message = "\n".join(
            (
                "Research plan execution not found:",
                f"Plan ID: {plan_id}",
                "This process holds no execution state for that plan.",
                "Execution state is in-memory only and is lost when Hypatia exits.",
                "It is not resumed after a restart.",
            )
        )
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="research_plan_execution",
            memory_count=0,
            success=False,
        )

    def research_plan_execution_budget_refused(
        self,
        request: BrainRequest,
        plan_id: str,
        capability: str,
        allowance: ResearchExecutionAllowance,
    ) -> BrainResponse:
        """Report an advance refused before anything was attempted or charged.

        Not a failure. The step was never begun, so nothing spent a network
        call, nothing ran, and the budget below is exactly what it was before
        the request arrived.
        """
        lines = [
            "Research plan execution was not advanced.",
            "Reason: the approved budget does not cover the next step.",
            f"Execution: {plan_id}",
            f"Next step capability: {capability}",
            "",
            *allowance.lines(),
            "",
            "Execution: not reached",
            "Nothing was attempted, charged, fetched, or written.",
        ]
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="research_plan_execution",
            memory_count=0,
            success=False,
        )

    def research_plan_execution_unauthorized(
        self,
        request: BrainRequest,
        verdict: ResearchPlanAuthorizationVerdict,
    ) -> BrainResponse:
        """Report work that was never reached, rather than work that failed.

        An execution that was not permitted to begin has no state, no steps,
        and no result. Calling it a failure would put a research failure in the
        record for something research never attempted.
        """
        message = "\n".join(
            (
                "Research plan execution was not authorized.",
                f"Authorization: {verdict.value}",
                _AUTHORIZATION_VERDICT_NOTES[verdict],
                "Execution: not reached",
                "No approval was spent, no step ran, and nothing was written.",
            )
        )
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="research_plan_execution",
            memory_count=0,
            success=False,
        )

    def research_plan_execution_rejected(
        self,
        request: BrainRequest,
        reason: str,
    ) -> BrainResponse:
        """Report one bounded refusal without starting or changing execution."""
        message = "\n".join(
            (
                "Research plan execution rejected:",
                f"Reason: {reason}",
                "Execution: not started",
                "Persistent writes: not used",
            )
        )
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="research_plan_execution",
            memory_count=0,
            success=False,
        )

    def research_run_list_success(
        self,
        request: BrainRequest,
        runs: list[ResearchRun],
    ) -> BrainResponse:
        """Compose a deterministic audit catalog without reading source content."""
        if not runs:
            message = "No research runs are stored."
        else:
            lines = ["Research runs:"]
            for run in runs:
                lines.append(
                    "- "
                    f"{run.question} | status: {run.status.value} | "
                    f"sources: {len(run.sources)} | "
                    f"discoveries: {len(run.discoveries)} | "
                    f"evidence: {len(run.evidence)} | "
                    f"assessments: {len(run.assessments)} | "
                    f"comparison notes: {len(run.comparison_notes)} | "
                    f"claims: {len(run.claims)} | "
                    f"failures: {len(run.failures)} | "
                    f"id: {run.run_id}"
                )
            message = "\n".join(lines)
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="research_run_list",
            memory_count=0,
            research_runs=runs,
        )

    def research_run_failure(
        self,
        request: BrainRequest,
        message: str,
        *,
        intent: str = "research_run_create",
    ) -> BrainResponse:
        """Report a safe run persistence failure without exposing store paths."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent=intent,
            memory_count=0,
            success=False,
        )

    def research_run_markdown_export_preview_success(
        self,
        request: BrainRequest,
        preview: ResearchRunMarkdownExportPreview,
    ) -> BrainResponse:
        """Render a bounded export preview without writing a document."""
        return BrainResponse(
            message=(
                "Research Markdown export preview:\n"
                f"Run: {preview.run_id}\n"
                f"Status: {preview.run_status.value}\n"
                f"Snapshot updated: {preview.snapshot_updated_at.isoformat()}\n"
                f"Suggested filename: {preview.suggested_filename}\n"
                f"Complete characters: {preview.total_character_count}\n"
                f"Omitted from preview: {preview.omitted_character_count}\n"
                f"Content SHA-256: {preview.content_sha256}\n"
                "Status: read-only preview; no file was written\n\n"
                f"{preview.markdown_preview}"
            ),
            request_id=request.request_id,
            intent="research_run_markdown_export_preview",
            memory_count=0,
            research_run_markdown_export_preview=preview,
        )

    def research_run_markdown_export_preview_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Report an invalid export selection without exposing store details."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="research_run_markdown_export_preview",
            memory_count=0,
            success=False,
        )

    def research_run_markdown_export_save_success(
        self,
        request: BrainRequest,
        result: ResearchRunMarkdownExportResult,
    ) -> BrainResponse:
        """Report the exact verified new Markdown file created for the user."""
        return BrainResponse(
            message=(
                "Research Markdown export saved:\n"
                f"Run: {result.run_id}\n"
                f"Snapshot updated: {result.snapshot_updated_at.isoformat()}\n"
                f"File: {result.destination_path}\n"
                f"Bytes: {result.byte_count}\n"
                f"Content SHA-256: {result.content_sha256}\n"
                "Status: new file created; no existing file was replaced"
            ),
            request_id=request.request_id,
            intent="research_run_markdown_export_save",
            memory_count=0,
            research_run_markdown_export_result=result,
        )

    def research_run_markdown_export_save_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Report a safe no-write export failure without exposing internals."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="research_run_markdown_export_save",
            memory_count=0,
            success=False,
        )

    def research_run_markdown_export_verify_success(
        self,
        request: BrainRequest,
        verification: ResearchRunMarkdownExportVerification,
    ) -> BrainResponse:
        """Report an exact read-only local export integrity comparison."""
        status = "MATCH" if verification.matches else "DOES NOT MATCH"
        return BrainResponse(
            message=(
                "Research Markdown export verification:\n"
                f"Run: {verification.run_id}\n"
                f"Snapshot updated: {verification.snapshot_updated_at.isoformat()}\n"
                f"File: {verification.source_path}\n"
                f"Result: {status}\n"
                f"Expected bytes: {verification.expected_byte_count}\n"
                f"Observed bytes: {verification.observed_byte_count}\n"
                "Expected SHA-256: "
                f"{verification.expected_content_sha256}\n"
                "Observed SHA-256: "
                f"{verification.observed_content_sha256}\n"
                "Status: read-only verification; no data was imported or changed"
            ),
            request_id=request.request_id,
            intent="research_run_markdown_export_verify",
            memory_count=0,
            research_run_markdown_export_verification=verification,
        )

    def research_run_markdown_export_verify_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Report a controlled local verification failure without path details."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="research_run_markdown_export_verify",
            memory_count=0,
            success=False,
        )

    def research_evidence_record_success(
        self,
        request: BrainRequest,
        run: ResearchRun,
    ) -> BrainResponse:
        """Report the exact persisted evidence identity and source locator."""
        evidence = run.evidence[-1]
        return BrainResponse(
            message="\n".join(
                [
                    "Research evidence recorded:",
                    f"Run: {run.run_id}",
                    f"Source document: {evidence.source_document_id}",
                    f"Paragraph: {evidence.chunk_index + 1}",
                    f"Chunk: {evidence.chunk_id}",
                    f"Evidence ID: {evidence.evidence_id}",
                ]
            ),
            request_id=request.request_id,
            intent="research_evidence_record",
            memory_count=0,
            research_runs=[run],
        )

    def research_evidence_record_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Report a controlled evidence-selection failure without mutation."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="research_evidence_record",
            memory_count=0,
            success=False,
        )

    def research_evidence_list_success(
        self,
        request: BrainRequest,
        run: ResearchRun,
    ) -> BrainResponse:
        """Render persisted bounded evidence without consulting live knowledge."""
        if not run.evidence:
            message = f"No research evidence is stored for run {run.run_id}."
        else:
            lines = [f"Research evidence for {run.run_id}:"]
            for evidence in run.evidence:
                truncation = (
                    " [excerpt truncated]" if evidence.excerpt_truncated else ""
                )
                lines.extend(
                    [
                        f"- {evidence.note}",
                        (
                            f"  source: {evidence.source_document_id} | "
                            f"paragraph: {evidence.chunk_index + 1} | "
                            f"chunk: {evidence.chunk_id} | "
                            f"id: {evidence.evidence_id}"
                        ),
                        f"  excerpt: {evidence.excerpt}{truncation}",
                    ]
                )
            message = "\n".join(lines)
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="research_evidence_list",
            memory_count=0,
            research_runs=[run],
        )

    def research_evidence_list_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Report an unavailable evidence catalog without changing state."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="research_evidence_list",
            memory_count=0,
            success=False,
        )

    def research_source_assessment_preview_success(
        self,
        request: BrainRequest,
        preview: ResearchSourceAssessmentPreview,
    ) -> BrainResponse:
        """Render provenance and only explicitly stored evidence for one source."""
        source = preview.source
        lines = [
            "Research source assessment preview:",
            f"Run: {preview.run_id}",
            f"Run status: {preview.run_status.value}",
            f"Title: {source.title}",
            f"URL: {source.url}",
            f"Type: {source.content_type}",
            f"Document ID: {source.document_id}",
            f"Data taint: {source.taint_label}",
            f"Instruction authority: {source.instruction_authority}",
            f"Recorded evidence: {len(preview.evidence)}",
            f"Reason: {preview.reason}",
            "Status: information trust is user-authored in assessments; external "
            "source instruction authority remains none",
        ]
        for evidence in preview.evidence:
            truncation = " [excerpt truncated]" if evidence.excerpt_truncated else ""
            lines.extend(
                [
                    f"- {evidence.note}",
                    (
                        f"  paragraph: {evidence.chunk_index + 1} | "
                        f"chunk: {evidence.chunk_id} | id: {evidence.evidence_id}"
                    ),
                    f"  excerpt: {evidence.excerpt}{truncation}",
                ]
            )
        lines.append(f"Recorded assessments: {len(preview.assessments)}")
        superseded_ids = {
            assessment.supersedes_assessment_id
            for assessment in preview.assessments
            if assessment.supersedes_assessment_id is not None
        }
        for assessment in preview.assessments:
            lines.extend(
                [
                    f"- Assessment: {assessment.assessment_id}",
                    f"  evidence IDs: {', '.join(assessment.evidence_ids)}",
                    f"  information trust: {assessment.information_trust.value}",
                    f"  text: {assessment.text}",
                    (
                        "  supersedes: "
                        f"{assessment.supersedes_assessment_id or 'none'}"
                    ),
                    (
                        "  state: superseded"
                        if assessment.assessment_id in superseded_ids
                        else "  state: current"
                    ),
                    f"  recorded: {assessment.recorded_at.isoformat()}",
                ]
            )
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="research_source_assessment_preview",
            memory_count=0,
            research_source_assessment_preview=preview,
        )

    def research_source_comparison_preview_success(
        self,
        request: BrainRequest,
        preview: ResearchSourceComparisonPreview,
    ) -> BrainResponse:
        """Render selected evidence columns without an automatic conclusion."""
        lines = [
            "Research source comparison preview:",
            f"Run: {preview.run_id}",
            f"Run status: {preview.run_status.value}",
            f"Question: {preview.question}",
            f"Selected sources: {len(preview.sources)}",
            f"Reason: {preview.reason}",
        ]
        for index, item in enumerate(preview.sources, start=1):
            source = item.source
            lines.extend(
                [
                    f"Source {index}:",
                    f"  Title: {source.title}",
                    f"  URL: {source.url}",
                    f"  Type: {source.content_type}",
                    f"  Document ID: {source.document_id}",
                    f"  Data taint: {source.taint_label}",
                    f"  Instruction authority: {source.instruction_authority}",
                    (
                        "  Selected evidence: showing "
                        f"{len(item.evidence)} of {item.total_evidence_count}"
                    ),
                ]
            )
            for evidence in item.evidence:
                truncation = (
                    " [excerpt truncated]" if evidence.excerpt_truncated else ""
                )
                lines.extend(
                    [
                        f"  - {evidence.evidence_id}: {evidence.note}",
                        (
                            f"    paragraph: {evidence.chunk_index + 1} | "
                            f"chunk: {evidence.chunk_id}"
                        ),
                        f"    excerpt: {evidence.excerpt}{truncation}",
                    ]
                )
            lines.append(
                "  Current assessments: showing "
                f"{len(item.current_assessments)} of "
                f"{item.total_current_assessment_count}"
            )
            for assessment in item.current_assessments:
                lines.extend(
                    [
                        f"  - Assessment: {assessment.assessment_id}",
                        f"    evidence IDs: {', '.join(assessment.evidence_ids)}",
                        (
                            "    information trust: "
                            f"{assessment.information_trust.value}"
                        ),
                        f"    text: {assessment.text}",
                        f"    recorded: {assessment.recorded_at.isoformat()}",
                    ]
                )
        lines.append(
            "Authored comparison notes: showing "
            f"{len(preview.comparison_notes)} of "
            f"{preview.total_comparison_note_count}"
        )
        for note in preview.comparison_notes:
            lines.extend(
                [
                    f"- Note: {note.note_id}",
                    f"  evidence IDs: {', '.join(note.evidence_ids)}",
                    f"  assessment IDs: {', '.join(note.assessment_ids)}",
                    f"  text: {note.text}",
                    f"  recorded: {note.recorded_at.isoformat()}",
                ]
            )
        lines.append(
            "Status: manual side-by-side preview only; no verdict, trust score, "
            "or automatic evidence selection"
        )
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="research_source_comparison_preview",
            memory_count=0,
            research_source_comparison_preview=preview,
        )

    def research_source_comparison_preview_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Report an invalid manual comparison selection without side effects."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="research_source_comparison_preview",
            memory_count=0,
            success=False,
        )

    def research_source_comparison_note_write_preview_success(
        self,
        request: BrainRequest,
        preview: ResearchSourceComparisonNoteWritePreview,
    ) -> BrainResponse:
        """Render exact authored text and persisted references before consent."""
        comparison = preview.comparison
        lines = [
            "Research comparison note write preview:",
            f"Run: {comparison.run_id}",
            f"Run status: {comparison.run_status.value}",
            f"Question: {comparison.question}",
            "Selected source IDs: "
            + ", ".join(item.source.document_id for item in comparison.sources),
            f"Authored note: {preview.text}",
            "Explicit evidence:",
        ]
        lines.extend(
            (
                f"- {record.evidence_id} | source: "
                f"{record.source_document_id} | note: {record.note}"
            )
            for record in preview.evidence
        )
        lines.append("Current assessments:")
        lines.extend(
            (
                f"- {record.assessment_id} | source: "
                f"{record.source_document_id} | text: {record.text}"
            )
            for record in preview.assessments
        )
        lines.extend(
            [
                f"Allowed: {'yes' if preview.allowed else 'no'}",
                f"Reason: {preview.reason}",
                "Status: user-authored text and explicit persisted references only; "
                "no verdict, score, or automatic evidence selection",
            ]
        )
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="research_source_comparison_note_write_preview",
            memory_count=0,
            success=preview.allowed,
            research_source_comparison_note_write_preview=preview,
        )

    def research_source_comparison_note_record_success(
        self,
        request: BrainRequest,
        run: ResearchRun,
    ) -> BrainResponse:
        """Report one comparison note only after its snapshot commits."""
        note = run.comparison_notes[-1]
        return BrainResponse(
            message=(
                "Research comparison note recorded:\n"
                f"ID: {note.note_id}\n"
                f"Source document IDs: {', '.join(note.source_document_ids)}\n"
                f"Evidence IDs: {', '.join(note.evidence_ids)}\n"
                f"Assessment IDs: {', '.join(note.assessment_ids)}\n"
                f"Authored note: {note.text}\n"
                "Status: committed user-authored note; no generated verdict or score"
            ),
            request_id=request.request_id,
            intent="research_source_comparison_note_record",
            memory_count=0,
            research_runs=[run],
        )

    def research_source_comparison_note_failure(
        self,
        request: BrainRequest,
        message: str,
        *,
        intent: str,
    ) -> BrainResponse:
        """Report invalid comparison-note preview or record input safely."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent=intent,
            memory_count=0,
            success=False,
        )

    def research_source_assessment_preview_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Report an invalid accepted-source selection without side effects."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="research_source_assessment_preview",
            memory_count=0,
            success=False,
        )

    def research_source_assessment_write_preview_success(
        self,
        request: BrainRequest,
        preview: ResearchSourceAssessmentWritePreview,
    ) -> BrainResponse:
        """Render one exact user-authored assessment before confirmation."""
        lines = [
            "Research source assessment write preview:",
            f"Run: {preview.run_id}",
            f"Run status: {preview.run_status.value}",
            f"Source: {preview.source.title}",
            f"Document ID: {preview.source.document_id}",
            f"Information trust: {preview.information_trust.value}",
            f"Instruction authority: {preview.source.instruction_authority}",
            f"Assessment: {preview.text}",
            (
                "Supersedes assessment: "
                + (
                    preview.supersedes_assessment.assessment_id
                    if preview.supersedes_assessment is not None
                    else "none"
                )
            ),
            "Explicit evidence:",
        ]
        lines.extend(
            f"- {record.evidence_id}: {record.note}" for record in preview.evidence
        )
        lines.extend(
            [
                f"Allowed: {'yes' if preview.allowed else 'no'}",
                f"Reason: {preview.reason}",
                "Status: user-authored information trust; no automatic score was "
                "assigned and instruction authority remains none",
            ]
        )
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="research_source_assessment_write_preview",
            memory_count=0,
            success=preview.allowed,
            research_source_assessment_write_preview=preview,
        )

    def research_source_assessment_record_success(
        self,
        request: BrainRequest,
        run: ResearchRun,
    ) -> BrainResponse:
        """Render an assessment only after its audit snapshot commits."""
        assessment = run.assessments[-1]
        return BrainResponse(
            message=(
                "Research source assessment recorded:\n"
                f"ID: {assessment.assessment_id}\n"
                f"Document ID: {assessment.source_document_id}\n"
                f"Evidence IDs: {', '.join(assessment.evidence_ids)}\n"
                f"Information trust: {assessment.information_trust.value}\n"
                "Instruction authority: none\n"
                f"Assessment: {assessment.text}\n"
                "Supersedes assessment: "
                f"{assessment.supersedes_assessment_id or 'none'}\n"
                "Status: committed user-authored assessment; no automatic score"
            ),
            request_id=request.request_id,
            intent="research_source_assessment_record",
            memory_count=0,
            research_runs=[run],
        )

    def research_source_assessment_write_failure(
        self,
        request: BrainRequest,
        message: str,
        *,
        intent: str,
    ) -> BrainResponse:
        """Report invalid assessment preview or record input safely."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent=intent,
            memory_count=0,
            success=False,
        )

    def research_claim_preview_success(
        self,
        request: BrainRequest,
        preview: ResearchClaimPreview,
    ) -> BrainResponse:
        """Render persisted claim history without creating a conclusion."""
        lines = [
            "Research claim history:",
            f"Run: {preview.run_id}",
            f"Question: {preview.question}",
            f"Run status: {preview.run_status.value}",
            f"Recorded claims: {len(preview.claims)}",
            f"Reason: {preview.reason}",
        ]
        superseded_ids = {
            claim.supersedes_claim_id
            for claim in preview.claims
            if claim.supersedes_claim_id is not None
        }
        for claim in preview.claims:
            lines.extend(
                (
                    f"- Claim: {claim.claim_id}",
                    (
                        "  audit state: superseded"
                        if claim.claim_id in superseded_ids
                        else "  audit state: current"
                    ),
                    f"  epistemic state: {claim.epistemic_state.value}",
                    f"  authored confidence: {claim.confidence.value}",
                    f"  source document IDs: {', '.join(claim.source_document_ids)}",
                    f"  evidence IDs: {', '.join(claim.evidence_ids)}",
                    f"  text: {claim.text}",
                    f"  supersedes: {claim.supersedes_claim_id or 'none'}",
                    f"  recorded: {claim.recorded_at.isoformat()}",
                )
            )
        lines.append(
            "Status: persisted user-authored claims only; no automatic extraction, "
            "truth score, or instruction authority"
        )
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="research_claim_preview",
            memory_count=0,
            research_claim_preview=preview,
        )

    def research_claim_preview_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Report an invalid claim-history request safely."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="research_claim_preview",
            memory_count=0,
            success=False,
        )

    def research_claim_write_preview_success(
        self,
        request: BrainRequest,
        preview: ResearchClaimWritePreview,
    ) -> BrainResponse:
        """Render exact authored claim metadata before confirmation."""
        lines = [
            "Research claim write preview:",
            f"Run: {preview.run_id}",
            f"Run status: {preview.run_status.value}",
            f"Claim: {preview.text}",
            f"Epistemic state: {preview.epistemic_state.value}",
            f"Authored confidence: {preview.confidence.value}",
            "Source document IDs: "
            + ", ".join(source.document_id for source in preview.sources),
            "Evidence IDs: "
            + ", ".join(record.evidence_id for record in preview.evidence),
            (
                "Supersedes claim: "
                + (
                    preview.supersedes_claim.claim_id
                    if preview.supersedes_claim is not None
                    else "none"
                )
            ),
            f"Allowed: {'yes' if preview.allowed else 'no'}",
            f"Reason: {preview.reason}",
            "Status: user-authored metadata only; no automatic fact determination",
        ]
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="research_claim_write_preview",
            memory_count=0,
            success=preview.allowed,
            research_claim_write_preview=preview,
        )

    def research_claim_record_success(
        self,
        request: BrainRequest,
        run: ResearchRun,
    ) -> BrainResponse:
        """Render one claim only after the audit snapshot commits."""
        claim = run.claims[-1]
        return BrainResponse(
            message=(
                "Research claim recorded:\n"
                f"ID: {claim.claim_id}\n"
                f"Claim: {claim.text}\n"
                f"Epistemic state: {claim.epistemic_state.value}\n"
                f"Authored confidence: {claim.confidence.value}\n"
                f"Source document IDs: {', '.join(claim.source_document_ids)}\n"
                f"Evidence IDs: {', '.join(claim.evidence_ids)}\n"
                f"Supersedes claim: {claim.supersedes_claim_id or 'none'}\n"
                "Status: committed user-authored claim; no automatic truth score"
            ),
            request_id=request.request_id,
            intent="research_claim_record",
            memory_count=0,
            research_runs=[run],
        )

    def research_claim_write_failure(
        self,
        request: BrainRequest,
        message: str,
        *,
        intent: str,
    ) -> BrainResponse:
        """Report invalid claim preview or record input safely."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent=intent,
            memory_count=0,
            success=False,
        )

    def research_claim_contradiction_preview_success(
        self,
        request: BrainRequest,
        preview: ResearchClaimContradictionPreview,
    ) -> BrainResponse:
        """Render persisted user-reviewed contradiction history without inference."""
        claims_by_id = {claim.claim_id: claim for claim in preview.claims}
        lines = [
            "Research claim contradiction history:",
            f"Run: {preview.run_id}",
            f"Question: {preview.question}",
            f"Run status: {preview.run_status.value}",
            f"Recorded contradictions: {len(preview.contradictions)}",
            f"Reason: {preview.reason}",
        ]
        for contradiction in preview.contradictions:
            first_claim = claims_by_id[contradiction.claim_ids[0]]
            second_claim = claims_by_id[contradiction.claim_ids[1]]
            lines.extend(
                (
                    f"- Contradiction: {contradiction.contradiction_id}",
                    f"  first claim: {first_claim.claim_id} — {first_claim.text}",
                    f"  second claim: {second_claim.claim_id} — {second_claim.text}",
                    f"  evidence IDs: {', '.join(contradiction.evidence_ids)}",
                    f"  user note: {contradiction.note}",
                    f"  recorded: {contradiction.recorded_at.isoformat()}",
                )
            )
        lines.append(
            "Status: persisted user-reviewed relationships only; no automatic "
            "detection, truth decision, claim rewrite, or instruction authority"
        )
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="research_claim_contradiction_preview",
            memory_count=0,
            research_claim_contradiction_preview=preview,
        )

    def research_claim_contradiction_preview_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Report an invalid contradiction-history request safely."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="research_claim_contradiction_preview",
            memory_count=0,
            success=False,
        )

    def research_claim_contradiction_proposal_success(
        self,
        request: BrainRequest,
        preview: ResearchClaimContradictionProposalPreview,
    ) -> BrainResponse:
        """Render model suggestions as non-persistent, untrusted review leads."""
        claims_by_id = {claim.claim_id: claim for claim in preview.claims}
        lines = [
            "Possible research claim contradictions:",
            f"Run: {preview.run_id}",
            f"Run status: {preview.run_status.value}",
            f"Snapshot: {preview.snapshot_updated_at.isoformat()}",
            f"Provider: {preview.provider_name}",
            f"Candidates: {len(preview.candidates)}",
            f"Reason: {preview.reason}",
        ]
        for index, candidate in enumerate(preview.candidates, start=1):
            first_claim = claims_by_id[candidate.claim_ids[0]]
            second_claim = claims_by_id[candidate.claim_ids[1]]
            lines.extend(
                (
                    f"- Candidate {index}",
                    f"  first claim: {first_claim.claim_id} — {first_claim.text}",
                    f"  second claim: {second_claim.claim_id} — {second_claim.text}",
                    f"  evidence IDs: {', '.join(candidate.evidence_ids)}",
                    f"  model rationale (untrusted suggestion): {candidate.rationale}",
                )
            )
        lines.append(
            "Status: read-only suggestions; nothing recorded, no truth decision, "
            "and manual preview plus confirmation are still required"
        )
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent="research_claim_contradiction_proposal",
            memory_count=0,
            research_claim_contradiction_proposal_preview=preview,
        )

    def research_claim_contradiction_proposal_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Report an unavailable or invalid read-only proposal safely."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="research_claim_contradiction_proposal",
            memory_count=0,
            success=False,
        )

    def research_claim_contradiction_write_preview_success(
        self,
        request: BrainRequest,
        preview: ResearchClaimContradictionWritePreview,
    ) -> BrainResponse:
        """Render exact relationship inputs before separate confirmation."""
        first_claim, second_claim = preview.claims
        return BrainResponse(
            message="\n".join(
                (
                    "Research claim contradiction preview:",
                    f"Run: {preview.run_id}",
                    f"Run status: {preview.run_status.value}",
                    f"First claim: {first_claim.claim_id} — {first_claim.text}",
                    f"Second claim: {second_claim.claim_id} — {second_claim.text}",
                    "Evidence IDs: "
                    + ", ".join(record.evidence_id for record in preview.evidence),
                    f"User note: {preview.note}",
                    f"Allowed: {'yes' if preview.allowed else 'no'}",
                    f"Reason: {preview.reason}",
                    "Status: user-reviewed relationship only; Hypatia does not "
                    "decide which claim is true",
                )
            ),
            request_id=request.request_id,
            intent="research_claim_contradiction_write_preview",
            memory_count=0,
            success=preview.allowed,
            research_claim_contradiction_write_preview=preview,
        )

    def research_claim_contradiction_record_success(
        self,
        request: BrainRequest,
        run: ResearchRun,
    ) -> BrainResponse:
        """Render one contradiction only after the audit snapshot commits."""
        contradiction = run.claim_contradictions[-1]
        return BrainResponse(
            message=(
                "Research claim contradiction recorded:\n"
                f"ID: {contradiction.contradiction_id}\n"
                f"Claim IDs: {', '.join(contradiction.claim_ids)}\n"
                f"Evidence IDs: {', '.join(contradiction.evidence_ids)}\n"
                f"User note: {contradiction.note}\n"
                "Status: committed user-reviewed relationship; no automatic truth "
                "decision or claim rewrite"
            ),
            request_id=request.request_id,
            intent="research_claim_contradiction_record",
            memory_count=0,
            research_runs=[run],
        )

    def research_claim_contradiction_write_failure(
        self,
        request: BrainRequest,
        message: str,
        *,
        intent: str,
    ) -> BrainResponse:
        """Report invalid contradiction preview or record input safely."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent=intent,
            memory_count=0,
            success=False,
        )

    def research_run_status_preview_success(
        self,
        request: BrainRequest,
        preview: ResearchRunStatusTransitionPreview,
    ) -> BrainResponse:
        """Render the current no-side-effect terminal transition decision."""
        decision = "allowed" if preview.allowed else "blocked"
        return BrainResponse(
            message="\n".join(
                [
                    "Research status transition preview:",
                    f"Run: {preview.run_id}",
                    f"Current status: {preview.current_status.value}",
                    f"Requested status: {preview.target_status.value}",
                    f"Decision: {decision}",
                    f"Reason: {preview.reason}",
                ]
            ),
            request_id=request.request_id,
            intent="research_run_status_preview",
            memory_count=0,
            research_run_status_transition_preview=preview,
        )

    def research_run_status_update_success(
        self,
        request: BrainRequest,
        run: ResearchRun,
    ) -> BrainResponse:
        """Report one atomically persisted terminal lifecycle transition."""
        return BrainResponse(
            message="\n".join(
                [
                    "Research run status updated:",
                    f"Run: {run.run_id}",
                    f"Status: {run.status.value}",
                ]
            ),
            request_id=request.request_id,
            intent="research_run_status_update",
            memory_count=0,
            research_runs=[run],
        )

    def research_run_status_failure(
        self,
        request: BrainRequest,
        message: str,
        *,
        intent: str = "research_run_status_update",
    ) -> BrainResponse:
        """Report a controlled transition failure without changing run state."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent=intent,
            memory_count=0,
            success=False,
        )

    def knowledge_relation_list_success(
        self,
        request: BrainRequest,
        relations: list[KnowledgeRelationReference],
    ) -> BrainResponse:
        """Compose a deterministic catalog of active local relationships."""
        if not relations:
            message = "No applied local knowledge relations are loaded."
        else:
            lines = ["Applied knowledge relations:"]
            for relation in relations:
                storage = "persisted" if relation.persisted else "in-memory only"
                lines.append(
                    "- "
                    f"{relation.source.title} | id: {relation.source.document_id} "
                    f"--{relation.relation.value}--> "
                    f"{relation.target.title} | id: {relation.target.document_id} "
                    f"| storage: {storage}"
                )
            message = "\n".join(lines)
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="knowledge_relation_list",
            memory_count=0,
            knowledge_relations=relations,
        )

    def knowledge_relation_preview_success(
        self,
        request: BrainRequest,
        preview: KnowledgeRelationPreview,
    ) -> BrainResponse:
        """Compose a no-side-effect preview for a manual document relation."""
        return BrainResponse(
            message="\n".join(
                [
                    "Knowledge relation preview:",
                    "Source: "
                    f"{preview.source.title} | id: {preview.source.document_id}",
                    f"Relation: {preview.relation.value}",
                    "Target: "
                    f"{preview.target.title} | id: {preview.target.document_id}",
                    "Changes: ready",
                ]
            ),
            request_id=request.request_id,
            intent="knowledge_relation_preview",
            memory_count=0,
            knowledge_relation_preview=preview,
        )

    def knowledge_relation_preview_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose a failed no-side-effect manual-relation preview."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="knowledge_relation_preview",
            memory_count=0,
            success=False,
        )

    def knowledge_relation_apply_success(
        self,
        request: BrainRequest,
        application: KnowledgeRelationApplication,
    ) -> BrainResponse:
        """Compose a successful, explicit in-memory relation application."""
        preview = application.preview
        return BrainResponse(
            message="\n".join(
                [
                    "Knowledge relation applied:",
                    "Source: "
                    f"{preview.source.title} | id: {preview.source.document_id}",
                    f"Relation: {preview.relation.value}",
                    "Target: "
                    f"{preview.target.title} | id: {preview.target.document_id}",
                    "Graph state: updated (memory only)",
                    (
                        "Relation storage: persisted"
                        if application.persisted
                        else "Relation storage: in-memory only"
                    ),
                    "JSON memory: unchanged",
                ]
            ),
            request_id=request.request_id,
            intent="knowledge_relation_apply",
            memory_count=0,
            knowledge_relation_application=application,
        )

    def knowledge_relation_apply_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose a failed explicit document-relation application."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="knowledge_relation_apply",
            memory_count=0,
            success=False,
        )

    def knowledge_relation_removal_preview_success(
        self,
        request: BrainRequest,
        preview: KnowledgeRelationRevocationPreview,
    ) -> BrainResponse:
        """Compose a no-side-effect preview for explicit relation removal."""
        relation = preview.relation
        return BrainResponse(
            message="\n".join(
                [
                    "Knowledge relation removal preview:",
                    "Source: "
                    f"{relation.source.title} | id: {relation.source.document_id}",
                    f"Relation: {relation.relation.value}",
                    "Target: "
                    f"{relation.target.title} | id: {relation.target.document_id}",
                    (
                        "Relation storage: persisted"
                        if preview.persisted
                        else "Relation storage: in-memory only"
                    ),
                    "Changes: ready to remove",
                ]
            ),
            request_id=request.request_id,
            intent="knowledge_relation_removal_preview",
            memory_count=0,
            knowledge_relation_revocation_preview=preview,
        )

    def knowledge_relation_removal_preview_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose a failed no-side-effect relation-removal preview."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="knowledge_relation_removal_preview",
            memory_count=0,
            success=False,
        )

    def knowledge_relation_remove_success(
        self,
        request: BrainRequest,
        revocation: KnowledgeRelationRevocation,
    ) -> BrainResponse:
        """Compose a successful explicit relation removal result."""
        relation = revocation.preview.relation
        return BrainResponse(
            message="\n".join(
                [
                    "Knowledge relation removed:",
                    "Source: "
                    f"{relation.source.title} | id: {relation.source.document_id}",
                    f"Relation: {relation.relation.value}",
                    "Target: "
                    f"{relation.target.title} | id: {relation.target.document_id}",
                    "Graph state: updated (memory only)",
                    (
                        "Relation storage: removed"
                        if revocation.preview.persisted
                        else "Relation storage: in-memory only"
                    ),
                    "JSON memory: unchanged",
                ]
            ),
            request_id=request.request_id,
            intent="knowledge_relation_remove",
            memory_count=0,
            knowledge_relation_revocation=revocation,
        )

    def knowledge_relation_remove_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose a failed explicit relation removal result."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="knowledge_relation_remove",
            memory_count=0,
            success=False,
        )

    def ask_knowledge_success(
        self,
        request: BrainRequest,
        answer: str,
        results: list[Chunk],
        citations: list[KnowledgeCitation],
    ) -> BrainResponse:
        """Compose an explicit local RAG answer with its visible source records."""
        return BrainResponse(
            message=answer,
            request_id=request.request_id,
            intent="ask_knowledge",
            memory_count=0,
            knowledge_results=results,
            knowledge_citations=citations,
        )

    def ask_knowledge_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose an unsuccessful explicit local RAG answer request."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="ask_knowledge",
            memory_count=0,
            success=False,
        )

    def _knowledge_context_item(
        self,
        index: int,
        result: Chunk,
        citation: KnowledgeCitation,
    ) -> str:
        source = citation.source or "local source unavailable"
        content = result.content
        if len(content) > self._KNOWLEDGE_CONTEXT_MAX_CHARS_PER_RESULT:
            content = (
                content[: self._KNOWLEDGE_CONTEXT_MAX_CHARS_PER_RESULT].rstrip() + "..."
            )
        return (
            f"{index}. {citation.document_title} | {source} | "
            f"paragraph {citation.chunk_index + 1}\n{content}"
        )

    def plan_success(
        self,
        request: BrainRequest,
        plan: Plan,
    ) -> BrainResponse:
        """Compose a successful ordered plan response."""
        task_lines = "\n".join(f"{task.order}. {task.title}" for task in plan.tasks)
        return BrainResponse(
            message=f"Plan created for: {plan.goal.description}\n\n{task_lines}",
            request_id=request.request_id,
            intent="plan",
            memory_count=0,
        )

    def plan_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose an unsuccessful planning response."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="plan",
            memory_count=0,
            success=False,
        )

    def recall_success(
        self,
        request: BrainRequest,
        records: list[MemoryRecord],
    ) -> BrainResponse:
        """Compose a successful explicit conversation recall response."""
        if not records:
            return BrainResponse(
                message="No matching conversation records found.",
                request_id=request.request_id,
                intent="recall",
                memory_count=0,
            )

        items = "\n\n".join(
            f"{index}. {record.content}"
            for index, record in enumerate(records, start=1)
        )
        return BrainResponse(
            message=f"Matching conversation records:\n\n{items}",
            request_id=request.request_id,
            intent="recall",
            memory_count=len(records),
        )

    def recall_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose an unsuccessful explicit conversation recall response."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="recall",
            memory_count=0,
            success=False,
        )

    def semantic_recall_success(
        self,
        request: BrainRequest,
        records: Sequence[tuple[MemoryRecord, float | None]],
        *,
        retrieval: str,
    ) -> BrainResponse:
        """Compose explicit semantic recall with a visible retrieval mode."""
        if not records:
            return BrainResponse(
                message=(
                    f"Semantic recall ({retrieval}): "
                    "no matching conversation records found."
                ),
                request_id=request.request_id,
                intent="semantic_recall",
                memory_count=0,
            )

        items = "\n\n".join(
            self._semantic_recall_item(
                index,
                record,
                score,
                score_label="rank score" if retrieval == "hybrid" else "similarity",
            )
            for index, (record, score) in enumerate(records, start=1)
        )
        return BrainResponse(
            message=f"Semantic recall ({retrieval}):\n\n{items}",
            request_id=request.request_id,
            intent="semantic_recall",
            memory_count=len(records),
        )

    def semantic_recall_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose an unsuccessful semantic recall response."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="semantic_recall",
            memory_count=0,
            success=False,
        )

    def semantic_recall_status(
        self,
        request: BrainRequest,
        *,
        runtime_state: str,
        indexed_memory_records: int | None,
        embedding_dimension: int | None,
        last_rebuild_error: str | None,
        last_update_error: str | None,
    ) -> BrainResponse:
        """Compose a read-only diagnostic for the optional semantic runtime."""
        available = indexed_memory_records is not None
        dimension = (
            embedding_dimension
            if embedding_dimension is not None
            else "not established"
        )
        last_rebuild = last_rebuild_error or (
            "in progress"
            if runtime_state in {"initializing", "refreshing"}
            else (
                "healthy" if runtime_state in {"ready", "updating"} else "unavailable"
            )
        )
        last_update = last_update_error or (
            "in progress"
            if runtime_state == "updating"
            else "healthy" if available else "unavailable"
        )
        return BrainResponse(
            message="\n".join(
                (
                    "Semantic recall status:",
                    f"Runtime: {runtime_state}",
                    "Indexed memory records: "
                    f"{indexed_memory_records if available else 'unavailable'}",
                    f"Embedding dimension: {dimension if available else 'unavailable'}",
                    f"Last rebuild: {last_rebuild}",
                    f"Last incremental update: {last_update}",
                )
            ),
            request_id=request.request_id,
            intent="semantic_recall_status",
            memory_count=0,
        )

    def semantic_recall_retry_started(
        self,
        request: BrainRequest,
        *,
        already_running: bool,
    ) -> BrainResponse:
        """Report an accepted single-flight background rebuild request."""
        return BrainResponse(
            message=(
                "Semantic recall rebuild is already in progress; no second rebuild "
                "was started."
                if already_running
                else "Semantic recall rebuild started in the background."
            ),
            request_id=request.request_id,
            intent="semantic_recall_retry",
            memory_count=0,
        )

    def semantic_recall_retry_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Report a safe explicit semantic-index rebuild failure."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="semantic_recall_retry",
            memory_count=0,
            success=False,
        )

    @staticmethod
    def _semantic_recall_item(
        index: int,
        record: MemoryRecord,
        score: float | None,
        *,
        score_label: str,
    ) -> str:
        if score is None:
            return f"{index}. {record.content}"
        return f"{index}. [{score_label}: {score:.3f}] {record.content}"

    def recent_conversations(
        self,
        request: BrainRequest,
        records: list[MemoryRecord],
        session: SessionRecord,
    ) -> BrainResponse:
        """Compose an ordered list of recent conversation records."""
        items = "\n".join(
            f"{index}. {record.content}"
            for index, record in enumerate(records, start=1)
        )
        return BrainResponse(
            message=f"Recent conversations in {session.session_id}:\n{items}",
            request_id=request.request_id,
            intent="recent_conversations",
            memory_count=len(records),
        )

    def recent_conversations_empty(
        self,
        request: BrainRequest,
        session: SessionRecord,
    ) -> BrainResponse:
        """Compose a successful empty recent-conversations response."""
        return BrainResponse(
            message=f"No conversations found in session: {session.session_id}",
            request_id=request.request_id,
            intent="recent_conversations",
            memory_count=0,
        )

    def recent_conversations_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose an unsuccessful recent-conversations response."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="recent_conversations",
            memory_count=0,
            success=False,
        )

    def conversation_search_results(
        self,
        request: BrainRequest,
        records: list[MemoryRecord],
        session: SessionRecord,
    ) -> BrainResponse:
        """Compose an ordered presentation of conversation search results."""
        items = "\n".join(
            f"{index}. {record.content}"
            for index, record in enumerate(records, start=1)
        )
        return BrainResponse(
            message=f"Conversation matches in {session.session_id}:\n{items}",
            request_id=request.request_id,
            intent="conversation_search",
            memory_count=len(records),
        )

    def conversation_search_empty(
        self,
        request: BrainRequest,
        session: SessionRecord,
    ) -> BrainResponse:
        """Compose a successful empty conversation-search response."""
        return BrainResponse(
            message=f"No matching conversations found in session: {session.session_id}",
            request_id=request.request_id,
            intent="conversation_search",
            memory_count=0,
        )

    def conversation_search_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose an unsuccessful conversation-search response."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="conversation_search",
            memory_count=0,
            success=False,
        )

    def session_created(
        self,
        request: BrainRequest,
        session: SessionRecord,
    ) -> BrainResponse:
        """Compose a successful session creation response."""
        return BrainResponse(
            message=(
                "Session created:\n" f"ID: {session.session_id}\n" "Status: ready"
            ),
            request_id=request.request_id,
            intent="session_create",
            memory_count=0,
        )

    def session_create_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose an unsuccessful session-creation response."""
        return BrainResponse(
            message=f"Session creation failed:\nReason: {message}",
            request_id=request.request_id,
            intent="session_create",
            memory_count=0,
            success=False,
        )

    def session_exists(
        self,
        request: BrainRequest,
        session: SessionRecord,
    ) -> BrainResponse:
        """Compose a successful duplicate-session response."""
        return BrainResponse(
            message=f"Session already exists: {session.session_id}",
            request_id=request.request_id,
            intent="session_create",
            memory_count=0,
        )

    def sessions_list(
        self,
        request: BrainRequest,
        sessions: list[SessionRecord],
        active_session: SessionRecord,
    ) -> BrainResponse:
        """Compose an ordered registry listing with one active-session marker."""
        session_lines = "\n".join(
            (
                f"{index}. {session.session_id} (active)"
                if session.session_id == active_session.session_id
                else f"{index}. {session.session_id}"
            )
            for index, session in enumerate(sessions, start=1)
        )
        return BrainResponse(
            message=f"Sessions:\n{session_lines}",
            request_id=request.request_id,
            intent="session_list",
            memory_count=0,
            session_summaries=self._session_summaries(
                sessions,
                active_session.session_id,
                {},
            ),
        )

    @staticmethod
    def _session_summaries(
        sessions: list[SessionRecord],
        active_session_id: str,
        conversation_counts: dict[str, int],
    ) -> list[SessionSummary]:
        """Expose ordered read-only session facts without a second store."""
        return [
            SessionSummary(
                session_id=session.session_id,
                active=session.session_id == active_session_id,
                conversation_count=conversation_counts.get(session.session_id, 0),
            )
            for session in sessions
        ]

    def session_overview(
        self,
        request: BrainRequest,
        sessions: list[SessionRecord],
        conversation_counts: dict[str, int],
        active_session_id: str,
    ) -> BrainResponse:
        """Compose an ordered overview of registered session conversations."""
        session_lines = "\n".join(
            self._session_overview_line(
                index,
                session,
                conversation_counts.get(session.session_id, 0),
                active_session_id,
            )
            for index, session in enumerate(sessions, start=1)
        )
        memory_count = sum(
            conversation_counts.get(session.session_id, 0) for session in sessions
        )
        return BrainResponse(
            message=f"Sessions:\n{session_lines}",
            request_id=request.request_id,
            intent="session_overview",
            memory_count=memory_count,
            session_summaries=self._session_summaries(
                sessions,
                active_session_id,
                conversation_counts,
            ),
        )

    def session_overview_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose an unsuccessful session-overview response."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="session_overview",
            memory_count=0,
            success=False,
        )

    def session_details(
        self,
        request: BrainRequest,
        session: SessionRecord,
        conversation_count: int,
        is_active: bool,
    ) -> BrainResponse:
        """Compose a read-only detail response for one registered session."""
        status = "active" if is_active else "inactive"
        conversation_label = (
            "conversation" if conversation_count == 1 else "conversations"
        )
        return BrainResponse(
            message=(
                f"Session: {session.session_id}\n"
                f"Status: {status}\n"
                f"Conversations: {conversation_count} {conversation_label}\n"
                f"Created: {session.created_at.isoformat()}"
            ),
            request_id=request.request_id,
            intent="session_details",
            memory_count=conversation_count,
        )

    def session_details_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose an unsuccessful session-details response."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="session_details",
            memory_count=0,
            success=False,
        )

    def session_activity(
        self,
        request: BrainRequest,
        session: SessionRecord,
        conversation_count: int,
        first_activity: datetime | None,
        last_activity: datetime | None,
    ) -> BrainResponse:
        """Compose a read-only conversation activity summary for one session."""
        first_value = first_activity.isoformat() if first_activity else "none"
        last_value = last_activity.isoformat() if last_activity else "none"
        return BrainResponse(
            message=(
                f"Session: {session.session_id}\n"
                f"Conversations: {conversation_count}\n"
                f"First activity: {first_value}\n"
                f"Last activity: {last_value}"
            ),
            request_id=request.request_id,
            intent="session_activity",
            memory_count=conversation_count,
        )

    def session_activity_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose an unsuccessful session-activity response."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="session_activity",
            memory_count=0,
            success=False,
        )

    def session_recent(
        self,
        request: BrainRequest,
        records: list[MemoryRecord],
        session: SessionRecord,
    ) -> BrainResponse:
        """Compose a recent-conversations response for a command-selected session."""
        items = "\n".join(
            f"{index}. {record.content}"
            for index, record in enumerate(records, start=1)
        )
        return BrainResponse(
            message=f"Recent conversations in {session.session_id}:\n{items}",
            request_id=request.request_id,
            intent="session_recent",
            memory_count=len(records),
        )

    def session_recent_empty(
        self,
        request: BrainRequest,
        session: SessionRecord,
    ) -> BrainResponse:
        """Compose a successful empty session-recent response."""
        return BrainResponse(
            message=f"No conversations found in session: {session.session_id}",
            request_id=request.request_id,
            intent="session_recent",
            memory_count=0,
        )

    def session_recent_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose an unsuccessful session-recent response."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="session_recent",
            memory_count=0,
            success=False,
        )

    def session_search_results(
        self,
        request: BrainRequest,
        session: SessionRecord,
        query: str,
        records: list[MemoryRecord],
    ) -> BrainResponse:
        """Compose a search response for a command-selected session."""
        items = "\n".join(
            f"{index}. {record.content}"
            for index, record in enumerate(records, start=1)
        )
        return BrainResponse(
            message=(
                f'Conversation matches in {session.session_id} for "{query}":\n{items}'
            ),
            request_id=request.request_id,
            intent="session_search",
            memory_count=len(records),
        )

    def session_search_empty(
        self,
        request: BrainRequest,
        session: SessionRecord,
        query: str,
    ) -> BrainResponse:
        """Compose a successful empty command-selected session search response."""
        return BrainResponse(
            message=(
                "No matching conversations found in session "
                f"{session.session_id} for: {query}"
            ),
            request_id=request.request_id,
            intent="session_search",
            memory_count=0,
        )

    def session_search_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose an unsuccessful command-selected session search response."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="session_search",
            memory_count=0,
            success=False,
        )

    def session_activated(
        self,
        request: BrainRequest,
        session: SessionRecord,
    ) -> BrainResponse:
        """Compose a successful active-session selection response."""
        return BrainResponse(
            message=f"Active session: {session.session_id}",
            request_id=request.request_id,
            intent="session_use",
            memory_count=0,
        )

    def session_failure(
        self,
        request: BrainRequest,
        message: str,
    ) -> BrainResponse:
        """Compose an unsuccessful session command response."""
        return BrainResponse(
            message=message,
            request_id=request.request_id,
            intent="session",
            memory_count=0,
            success=False,
        )

    @staticmethod
    def _session_overview_line(
        index: int,
        session: SessionRecord,
        count: int,
        active_session_id: str,
    ) -> str:
        """Format one session overview line without changing registry order."""
        conversation_label = "conversation" if count == 1 else "conversations"
        active_marker = " [active]" if session.session_id == active_session_id else ""
        return (
            f"{index}. {session.session_id} — {count} "
            f"{conversation_label}{active_marker}"
        )


def _discovery_provider_lines(
    providers: tuple[ResearchDiscoveryProviderName, ...],
) -> tuple[str, ...]:
    """Name the providers this approval would let a plan contact.

    Said out loud rather than left implicit. Approving a plan approves a network
    destination, and `none named` is worth stating too: it means a discovery
    step would use whichever provider this installation was configured with,
    which is a different and weaker thing to have agreed to.
    """
    if not providers:
        return (
            "Source discovery provider: none named "
            "(a discovery step would use the configured default)",
        )
    return tuple(
        f"Source discovery provider: {provider.label}" for provider in providers
    )
