"""Central response composition contract for Hypatia."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from brain.SessionSummary import SessionSummary
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
from research.ResearchClaimWritePreview import ResearchClaimWritePreview
from research.ResearchEvidenceIntegrityStatus import ResearchEvidenceIntegrityStatus
from research.ResearchPlanDraftPreview import ResearchPlanDraftPreview
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
from session.SessionDeleteExecutionResult import SessionDeleteExecutionResult
from session.SessionDeletePolicy import SessionDeleteStatus
from session.SessionRecord import SessionRecord
from session.SessionRenamePreview import SessionRenamePreview
from session.SessionRenameResult import SessionRenameResult


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
        intent: str = "research_source_load",
    ) -> BrainResponse:
        """Report one explicitly selected internet source after local indexing."""
        lines = [
            "Research source loaded:",
            f"Title: {document.title}",
            f"Source: {document.source}",
            f"Type: {document.document_type.value}",
            f"Chunks: {document.chunk_count}",
            f"ID: {document.document_id}",
        ]
        if run is not None:
            lines.append(f"Research run: {run.run_id}")
        return BrainResponse(
            message="\n".join(lines),
            request_id=request.request_id,
            intent=intent,
            memory_count=0,
            knowledge_documents=[document],
            research_runs=[] if run is None else [run],
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
    ) -> BrainResponse:
        """Report a newly persisted auditable research run."""
        return BrainResponse(
            message="\n".join(
                [
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
            ),
            request_id=request.request_id,
            intent="research_run_create",
            memory_count=0,
            research_runs=[run],
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
