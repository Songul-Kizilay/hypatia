"""Testable desktop actions delegated to the existing Brain boundary."""

from __future__ import annotations

from typing import Protocol

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse


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
