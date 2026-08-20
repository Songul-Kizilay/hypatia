"""Testable desktop actions delegated to the existing Brain boundary."""

from __future__ import annotations

from typing import Protocol

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from research.ResearchRunMarkdownExportPreview import (
    ResearchRunMarkdownExportPreview,
)


class BrainProcessor(Protocol):
    """Minimum existing runtime capability needed by the desktop adapter."""

    def process(self, request: BrainRequest | str) -> BrainResponse:
        """Process a user request through the established Brain boundary."""


class DesktopController:
    """Keep UI actions small, explicit, and free of duplicate state."""

    def __init__(self, brain: BrainProcessor) -> None:
        self._brain = brain

    def submit_message(self, message: str) -> BrainResponse:
        """Send non-empty composer text unchanged to the existing Brain."""
        if not message.strip():
            raise ValueError("A desktop message cannot be empty.")
        return self._brain.process(message)

    def select_session(self, session_id: str) -> BrainResponse:
        """Activate an existing session through its explicit Brain command."""
        normalized_session_id = session_id.strip()
        if not normalized_session_id:
            raise ValueError("A session ID cannot be empty.")
        return self._brain.process(f"use session {normalized_session_id}")

    def session_overview(self) -> BrainResponse:
        """Request existing read-only session facts for desktop presentation."""
        return self._brain.process("session overview")

    def session_details(self, session_id: str) -> BrainResponse:
        """Request read-only details for the explicitly selected session."""
        return self._selected_session_command("session details", session_id)

    def session_recent(self, session_id: str) -> BrainResponse:
        """Request the selected session's read-only recent conversation view."""
        return self._selected_session_command("session recent", session_id)

    def session_activity(self, session_id: str) -> BrainResponse:
        """Request read-only first and last activity for the selected session."""
        return self._selected_session_command("session activity", session_id)

    def session_search(self, session_id: str, query: str) -> BrainResponse:
        """Search only the explicitly selected session without changing it."""
        normalized_session_id = session_id.strip()
        normalized_query = query.strip()
        if not normalized_session_id:
            raise ValueError("A session ID cannot be empty.")
        if not normalized_query:
            raise ValueError("A session search query cannot be empty.")
        return self._brain.process(
            f"session search {normalized_session_id} -- {normalized_query}"
        )

    def preview_session_rename(
        self,
        source_session_id: str,
        target_session_id: str,
    ) -> BrainResponse:
        """Validate a requested session rename without changing either store."""
        return self._session_rename_command(
            "preview rename session",
            source_session_id,
            target_session_id,
        )

    def rename_session(
        self,
        source_session_id: str,
        target_session_id: str,
    ) -> BrainResponse:
        """Rename only after the desktop has shown the runtime preview."""
        return self._session_rename_command(
            "rename session",
            source_session_id,
            target_session_id,
        )

    def preview_session_delete(self, session_id: str) -> BrainResponse:
        """Request the existing read-only delete decision for one session."""
        return self._selected_session_command("preview delete session", session_id)

    def delete_session(self, session_id: str) -> BrainResponse:
        """Send the existing guarded delete command after an allowed preview."""
        return self._selected_session_command("delete session", session_id)

    def recall(self, query: str) -> BrainResponse:
        """Request explicit lexical recall without changing conversation memory."""
        return self._recall_command("recall", query)

    def semantic_recall(self, query: str) -> BrainResponse:
        """Request explicit semantic recall through the existing opt-in path."""
        return self._recall_command("semantic recall", query)

    def knowledge_context(self, query: str) -> BrainResponse:
        """Request bounded cited local knowledge context without an LLM call."""
        return self._knowledge_command("knowledge context", query)

    def knowledge_graph(self, query: str) -> BrainResponse:
        """Request a bounded cited local source-structure view without an LLM."""
        return self._knowledge_command("knowledge graph", query)

    def ask_knowledge(self, query: str) -> BrainResponse:
        """Ask the enabled runtime using only bounded cited local knowledge."""
        return self._knowledge_command("ask knowledge", query)

    def load_knowledge(self, path: str) -> BrainResponse:
        """Load one explicitly selected local text or Markdown source through Brain."""
        normalized_path = path.strip()
        if not normalized_path:
            raise ValueError("A local knowledge source path cannot be empty.")
        return self._brain.process(
            BrainRequest(
                message="Load selected local knowledge source",
                source="desktop",
                metadata={
                    "intent": "knowledge_load",
                    "knowledge_path": normalized_path,
                },
            )
        )

    def create_research_run(self, question: str) -> BrainResponse:
        """Create one explicit, persistent research run through Brain."""
        normalized_question = question.strip()
        if not normalized_question:
            raise ValueError("A research question cannot be empty.")
        return self._brain.process(
            BrainRequest(
                message="Create internet research run",
                source="desktop",
                metadata={
                    "intent": "research_run_create",
                    "research_question": normalized_question,
                },
            )
        )

    def list_research_runs(self) -> BrainResponse:
        """List persistent research runs without fetching a network source."""
        return self._brain.process(
            BrainRequest(
                message="List internet research runs",
                source="desktop",
                metadata={"intent": "research_run_list"},
            )
        )

    def preview_research_run_markdown_export(
        self,
        research_run_id: str,
    ) -> BrainResponse:
        """Preview one terminal run as Markdown without writing a file."""
        normalized_run_id = research_run_id.strip()
        if not normalized_run_id:
            raise ValueError("A research run ID cannot be empty.")
        return self._brain.process(
            BrainRequest(
                message="Preview terminal research run as Markdown",
                source="desktop",
                metadata={
                    "intent": "research_run_markdown_export_preview",
                    "research_run_id": normalized_run_id,
                },
            )
        )

    def save_research_run_markdown_export(
        self,
        preview: ResearchRunMarkdownExportPreview,
        destination_path: str,
    ) -> BrainResponse:
        """Request one exact preview be saved to an explicitly selected new file."""
        if not isinstance(preview, ResearchRunMarkdownExportPreview):
            raise ValueError("A research Markdown export preview is required.")
        normalized_destination = destination_path.strip()
        if not normalized_destination:
            raise ValueError("A research export destination cannot be empty.")
        return self._brain.process(
            BrainRequest(
                message="Save previewed research run as Markdown",
                source="desktop",
                metadata={
                    "intent": "research_run_markdown_export_save",
                    "research_run_id": preview.run_id,
                    "research_export_snapshot_updated_at": (
                        preview.snapshot_updated_at.isoformat()
                    ),
                    "research_export_content_sha256": preview.content_sha256,
                    "research_export_destination_path": normalized_destination,
                },
            )
        )

    def discover_research_sources(self, research_run_id: str) -> BrainResponse:
        """Discover candidate metadata for one run without loading content."""
        normalized_run_id = research_run_id.strip()
        if not normalized_run_id:
            raise ValueError("A research run ID cannot be empty.")
        return self._brain.process(
            BrainRequest(
                message="Discover candidate research sources",
                source="desktop",
                metadata={
                    "intent": "research_source_discover",
                    "research_run_id": normalized_run_id,
                },
            )
        )

    def record_research_evidence(
        self,
        research_run_id: str,
        chunk_id: str,
        note: str,
    ) -> BrainResponse:
        """Record one explicit indexed paragraph as research evidence."""
        normalized_run_id = research_run_id.strip()
        normalized_chunk_id = chunk_id.strip()
        normalized_note = note.strip()
        if not normalized_run_id:
            raise ValueError("A research run ID cannot be empty.")
        if not normalized_chunk_id:
            raise ValueError("A research chunk ID cannot be empty.")
        if not normalized_note:
            raise ValueError("A research evidence note cannot be empty.")
        return self._brain.process(
            BrainRequest(
                message="Record selected research evidence",
                source="desktop",
                metadata={
                    "intent": "research_evidence_record",
                    "research_run_id": normalized_run_id,
                    "research_chunk_id": normalized_chunk_id,
                    "research_evidence_note": normalized_note,
                },
            )
        )

    def list_research_evidence(self, research_run_id: str) -> BrainResponse:
        """List persisted bounded evidence for one explicitly selected run."""
        normalized_run_id = research_run_id.strip()
        if not normalized_run_id:
            raise ValueError("A research run ID cannot be empty.")
        return self._brain.process(
            BrainRequest(
                message="List selected research evidence",
                source="desktop",
                metadata={
                    "intent": "research_evidence_list",
                    "research_run_id": normalized_run_id,
                },
            )
        )

    def preview_research_source_assessment(
        self,
        research_run_id: str,
        source_document_id: str,
    ) -> BrainResponse:
        """Preview accepted provenance and user-selected evidence only."""
        normalized_run_id = research_run_id.strip()
        normalized_document_id = source_document_id.strip()
        if not normalized_run_id:
            raise ValueError("A research run ID cannot be empty.")
        if not normalized_document_id:
            raise ValueError("A research source document ID cannot be empty.")
        return self._brain.process(
            BrainRequest(
                message="Preview accepted research source assessment",
                source="desktop",
                metadata={
                    "intent": "research_source_assessment_preview",
                    "research_run_id": normalized_run_id,
                    "research_source_document_id": normalized_document_id,
                },
            )
        )

    def preview_research_source_comparison(
        self,
        research_run_id: str,
        source_document_ids: str,
    ) -> BrainResponse:
        """Preview 2-5 explicitly selected accepted sources side by side."""
        normalized_run_id = research_run_id.strip()
        normalized_document_ids = [
            value.strip() for value in source_document_ids.split(",") if value.strip()
        ]
        if not normalized_run_id:
            raise ValueError("A research run ID cannot be empty.")
        if not 2 <= len(normalized_document_ids) <= 5:
            raise ValueError("Enter 2 to 5 research source document IDs.")
        if len(normalized_document_ids) != len(set(normalized_document_ids)):
            raise ValueError("Research source document IDs must be unique.")
        return self._brain.process(
            BrainRequest(
                message="Preview selected research sources side by side",
                source="desktop",
                metadata={
                    "intent": "research_source_comparison_preview",
                    "research_run_id": normalized_run_id,
                    "research_source_document_ids": normalized_document_ids,
                },
            )
        )

    def preview_research_source_comparison_note_write(
        self,
        research_run_id: str,
        source_document_ids: str,
        evidence_ids: str,
        assessment_ids: str,
        note_text: str,
    ) -> BrainResponse:
        """Preview one authored comparison note and its exact references."""
        metadata = self._research_source_comparison_note_metadata(
            research_run_id,
            source_document_ids,
            evidence_ids,
            assessment_ids,
            note_text,
        )
        return self._brain.process(
            BrainRequest(
                message="Preview user-authored research comparison note",
                source="desktop",
                metadata={
                    "intent": "research_source_comparison_note_write_preview",
                    **metadata,
                },
            )
        )

    def record_research_source_comparison_note(
        self,
        research_run_id: str,
        source_document_ids: str,
        evidence_ids: str,
        assessment_ids: str,
        note_text: str,
    ) -> BrainResponse:
        """Submit one comparison note only after desktop confirmation."""
        metadata = self._research_source_comparison_note_metadata(
            research_run_id,
            source_document_ids,
            evidence_ids,
            assessment_ids,
            note_text,
        )
        return self._brain.process(
            BrainRequest(
                message="Record user-authored research comparison note",
                source="desktop",
                metadata={
                    "intent": "research_source_comparison_note_record",
                    **metadata,
                },
            )
        )

    @staticmethod
    def _research_source_comparison_note_metadata(
        research_run_id: str,
        source_document_ids: str,
        evidence_ids: str,
        assessment_ids: str,
        note_text: str,
    ) -> dict[str, object]:
        normalized_run_id = research_run_id.strip()
        normalized_text = note_text.strip()
        normalized_document_ids = [
            value.strip() for value in source_document_ids.split(",") if value.strip()
        ]
        normalized_evidence_ids = [
            value.strip() for value in evidence_ids.split(",") if value.strip()
        ]
        normalized_assessment_ids = [
            value.strip() for value in assessment_ids.split(",") if value.strip()
        ]
        if not normalized_run_id:
            raise ValueError("A research run ID cannot be empty.")
        if not 2 <= len(normalized_document_ids) <= 5:
            raise ValueError("Enter 2 to 5 research source document IDs.")
        for values, label in (
            (normalized_document_ids, "Research source document IDs"),
            (normalized_evidence_ids, "Research comparison evidence IDs"),
            (normalized_assessment_ids, "Research comparison assessment IDs"),
        ):
            if not values:
                raise ValueError(f"{label} cannot be empty.")
            if len(values) != len(set(values)):
                raise ValueError(f"{label} cannot be duplicated.")
        if not normalized_text:
            raise ValueError("Research comparison note text cannot be empty.")
        return {
            "research_run_id": normalized_run_id,
            "research_source_document_ids": normalized_document_ids,
            "research_comparison_evidence_ids": normalized_evidence_ids,
            "research_comparison_assessment_ids": normalized_assessment_ids,
            "research_comparison_note_text": normalized_text,
        }

    def preview_research_source_assessment_write(
        self,
        research_run_id: str,
        source_document_id: str,
        evidence_ids: str,
        assessment_text: str,
        supersedes_assessment_id: str = "",
    ) -> BrainResponse:
        """Preview an authored assessment with explicit evidence references."""
        metadata = self._research_source_assessment_write_metadata(
            research_run_id,
            source_document_id,
            evidence_ids,
            assessment_text,
            supersedes_assessment_id,
        )
        return self._brain.process(
            BrainRequest(
                message="Preview user-authored research source assessment",
                source="desktop",
                metadata={
                    "intent": "research_source_assessment_write_preview",
                    **metadata,
                },
            )
        )

    def record_research_source_assessment(
        self,
        research_run_id: str,
        source_document_id: str,
        evidence_ids: str,
        assessment_text: str,
        supersedes_assessment_id: str = "",
    ) -> BrainResponse:
        """Submit one assessment only after the desktop confirmation step."""
        metadata = self._research_source_assessment_write_metadata(
            research_run_id,
            source_document_id,
            evidence_ids,
            assessment_text,
            supersedes_assessment_id,
        )
        return self._brain.process(
            BrainRequest(
                message="Record user-authored research source assessment",
                source="desktop",
                metadata={
                    "intent": "research_source_assessment_record",
                    **metadata,
                },
            )
        )

    @staticmethod
    def _research_source_assessment_write_metadata(
        research_run_id: str,
        source_document_id: str,
        evidence_ids: str,
        assessment_text: str,
        supersedes_assessment_id: str = "",
    ) -> dict[str, object]:
        normalized_run_id = research_run_id.strip()
        normalized_document_id = source_document_id.strip()
        normalized_text = assessment_text.strip()
        normalized_superseded_id = supersedes_assessment_id.strip()
        normalized_evidence_ids = [
            value.strip() for value in evidence_ids.split(",") if value.strip()
        ]
        if not normalized_run_id:
            raise ValueError("A research run ID cannot be empty.")
        if not normalized_document_id:
            raise ValueError("A research source document ID cannot be empty.")
        if not normalized_evidence_ids:
            raise ValueError("Research assessment evidence IDs cannot be empty.")
        if len(normalized_evidence_ids) != len(set(normalized_evidence_ids)):
            raise ValueError("Research assessment evidence IDs cannot be duplicated.")
        if not normalized_text:
            raise ValueError("Research source assessment text cannot be empty.")
        metadata: dict[str, object] = {
            "research_run_id": normalized_run_id,
            "research_source_document_id": normalized_document_id,
            "research_assessment_evidence_ids": normalized_evidence_ids,
            "research_assessment_text": normalized_text,
        }
        if normalized_superseded_id:
            metadata["research_assessment_supersedes_id"] = normalized_superseded_id
        return metadata

    def preview_research_run_status(
        self,
        research_run_id: str,
        target_status: str,
    ) -> BrainResponse:
        """Preview one requested terminal research status without mutation."""
        return self._research_status_request(
            "research_run_status_preview",
            "Preview selected research status",
            research_run_id,
            target_status,
        )

    def update_research_run_status(
        self,
        research_run_id: str,
        target_status: str,
    ) -> BrainResponse:
        """Apply one terminal status only after the desktop preview."""
        return self._research_status_request(
            "research_run_status_update",
            "Update selected research status",
            research_run_id,
            target_status,
        )

    def load_research_source(
        self,
        url: str,
        research_run_id: str = "",
    ) -> BrainResponse:
        """Load one explicit HTTPS source, optionally attaching it to a run."""
        normalized_url = url.strip()
        if not normalized_url:
            raise ValueError("A research source URL cannot be empty.")
        normalized_run_id = research_run_id.strip()
        metadata = {
            "intent": "research_source_load",
            "research_url": normalized_url,
        }
        if normalized_run_id:
            metadata["research_run_id"] = normalized_run_id
        return self._brain.process(
            BrainRequest(
                message="Load selected internet research source",
                source="desktop",
                metadata=metadata,
            )
        )

    def preview_research_source_candidate_acceptance(
        self,
        research_run_id: str,
        discovery_id: str,
        candidate_url: str,
    ) -> BrainResponse:
        """Preview one persisted discovery candidate without loading it."""
        return self._research_candidate_request(
            "research_source_candidate_acceptance_preview",
            "Preview selected research source candidate",
            research_run_id,
            discovery_id,
            candidate_url,
        )

    def accept_research_source_candidate(
        self,
        research_run_id: str,
        discovery_id: str,
        candidate_url: str,
    ) -> BrainResponse:
        """Accept one confirmed candidate through the guarded source loader."""
        return self._research_candidate_request(
            "research_source_candidate_accept",
            "Accept selected research source candidate",
            research_run_id,
            discovery_id,
            candidate_url,
        )

    def _research_candidate_request(
        self,
        intent: str,
        message: str,
        research_run_id: str,
        discovery_id: str,
        candidate_url: str,
    ) -> BrainResponse:
        normalized_run_id = research_run_id.strip()
        normalized_discovery_id = discovery_id.strip()
        normalized_url = candidate_url.strip()
        if not normalized_run_id:
            raise ValueError("A research run ID cannot be empty.")
        if not normalized_discovery_id:
            raise ValueError("A research source discovery ID cannot be empty.")
        if not normalized_url:
            raise ValueError("A research source candidate URL cannot be empty.")
        return self._brain.process(
            BrainRequest(
                message=message,
                source="desktop",
                metadata={
                    "intent": intent,
                    "research_run_id": normalized_run_id,
                    "research_discovery_id": normalized_discovery_id,
                    "research_url": normalized_url,
                },
            )
        )

    def preview_knowledge_relation(
        self,
        source_document_id: str,
        target_document_id: str,
    ) -> BrainResponse:
        """Validate a requested local document relation without changing it."""
        return self._knowledge_relation_command(
            "preview knowledge relation",
            source_document_id,
            target_document_id,
        )

    def apply_knowledge_relation(
        self,
        source_document_id: str,
        target_document_id: str,
    ) -> BrainResponse:
        """Apply a relation only after the desktop has shown its preview."""
        return self._knowledge_relation_command(
            "apply knowledge relation",
            source_document_id,
            target_document_id,
        )

    def preview_knowledge_relation_removal(
        self,
        source_document_id: str,
        target_document_id: str,
    ) -> BrainResponse:
        """Validate removal of an existing relation without changing it."""
        return self._knowledge_relation_command(
            "preview remove knowledge relation",
            source_document_id,
            target_document_id,
        )

    def remove_knowledge_relation(
        self,
        source_document_id: str,
        target_document_id: str,
    ) -> BrainResponse:
        """Remove a relation only after its desktop preview is confirmed."""
        return self._knowledge_relation_command(
            "remove knowledge relation",
            source_document_id,
            target_document_id,
        )

    def list_knowledge(self) -> BrainResponse:
        """Request the existing read-only catalog of loaded local sources."""
        return self._brain.process("list knowledge")

    def list_knowledge_relations(self) -> BrainResponse:
        """Request the read-only catalog of active local source relations."""
        return self._brain.process("list knowledge relations")

    def semantic_status(self) -> BrainResponse:
        """Request the read-only semantic runtime status without a query."""
        return self._brain.process("semantic recall status")

    def _selected_session_command(
        self,
        command: str,
        session_id: str,
    ) -> BrainResponse:
        """Keep session-specific desktop actions explicit and side-effect free."""
        normalized_session_id = session_id.strip()
        if not normalized_session_id:
            raise ValueError("A session ID cannot be empty.")
        return self._brain.process(f"{command} {normalized_session_id}")

    def _recall_command(self, command: str, query: str) -> BrainResponse:
        """Keep memory retrieval user-initiated and reject empty queries locally."""
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("A recall query cannot be empty.")
        return self._brain.process(f"{command} {normalized_query}")

    def _session_rename_command(
        self,
        command: str,
        source_session_id: str,
        target_session_id: str,
    ) -> BrainResponse:
        """Keep desktop rename input explicit before the transactional runtime path."""
        source_id = source_session_id.strip()
        target_id = target_session_id.strip()
        if not source_id or not target_id:
            raise ValueError("Both session IDs are required for a rename.")
        return self._brain.process(f"{command} {source_id} -- {target_id}")

    def _knowledge_command(self, command: str, query: str) -> BrainResponse:
        """Keep local knowledge retrieval explicit and query-bounded."""
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("A knowledge query cannot be empty.")
        return self._brain.process(f"{command} {normalized_query}")

    def _knowledge_relation_command(
        self,
        command: str,
        source_document_id: str,
        target_document_id: str,
    ) -> BrainResponse:
        """Send two explicit document IDs through the existing relation boundary."""
        source_id = source_document_id.strip()
        target_id = target_document_id.strip()
        if not source_id or not target_id:
            raise ValueError("Both knowledge source IDs are required.")
        return self._brain.process(f"{command} {source_id} -- {target_id}")

    def _research_status_request(
        self,
        intent: str,
        message: str,
        research_run_id: str,
        target_status: str,
    ) -> BrainResponse:
        normalized_run_id = research_run_id.strip()
        normalized_status = target_status.strip().casefold()
        if not normalized_run_id:
            raise ValueError("A research run ID cannot be empty.")
        if normalized_status not in {"completed", "failed", "cancelled"}:
            raise ValueError("A valid terminal research status is required.")
        return self._brain.process(
            BrainRequest(
                message=message,
                source="desktop",
                metadata={
                    "intent": intent,
                    "research_run_id": normalized_run_id,
                    "research_target_status": normalized_status,
                },
            )
        )
