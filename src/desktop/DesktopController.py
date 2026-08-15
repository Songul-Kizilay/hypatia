"""Testable desktop actions delegated to the existing Brain boundary."""

from __future__ import annotations

from typing import Protocol

from brain.BrainResponse import BrainResponse


class BrainProcessor(Protocol):
    """Minimum existing runtime capability needed by the desktop adapter."""

    def process(self, request: str) -> BrainResponse:
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

    def recall(self, query: str) -> BrainResponse:
        """Request explicit lexical recall without changing conversation memory."""
        return self._recall_command("recall", query)

    def semantic_recall(self, query: str) -> BrainResponse:
        """Request explicit semantic recall through the existing opt-in path."""
        return self._recall_command("semantic recall", query)

    def knowledge_context(self, query: str) -> BrainResponse:
        """Request bounded cited local knowledge context without an LLM call."""
        return self._knowledge_command("knowledge context", query)

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

    def _knowledge_command(self, command: str, query: str) -> BrainResponse:
        """Keep local knowledge retrieval explicit and query-bounded."""
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("A knowledge query cannot be empty.")
        return self._brain.process(f"{command} {normalized_query}")
