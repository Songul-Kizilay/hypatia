"""Simple deterministic intent detection for the first Brain iteration."""

from __future__ import annotations

from brain.BrainRequest import BrainRequest


class BrainRouter:
    """Identifies a small set of basic intents without an LLM."""

    _GREETING_WORDS = frozenset({"hello", "hi", "hey", "merhaba", "selam"})

    def detect_intent(self, request: BrainRequest) -> str:
        """Return the deterministic intent for a request."""
        declared_intent = request.metadata.get("intent")
        normalized_message = request.message.casefold().strip()
        if (
            declared_intent == "recall"
            or normalized_message == "recall"
            or normalized_message.startswith("recall ")
        ):
            return "recall"
        if (
            normalized_message == "search conversations"
            or normalized_message.startswith("search conversations ")
        ):
            return "conversation_search"
        if (
            normalized_message == "recent conversations"
            or normalized_message.startswith("recent conversations ")
        ):
            return "recent_conversations"
        if normalized_message == "session overview":
            return "session_overview"
        if normalized_message == "session details" or normalized_message.startswith(
            "session details "
        ):
            return "session_details"
        if normalized_message == "session recent" or normalized_message.startswith(
            "session recent "
        ):
            return "session_recent"
        if normalized_message == "session search" or normalized_message.startswith(
            "session search "
        ):
            return "session_search"
        if normalized_message == "session activity" or normalized_message.startswith(
            "session activity "
        ):
            return "session_activity"
        if normalized_message == "active session":
            return "session_active"
        if normalized_message == "help sessions":
            return "session_help"
        if normalized_message == "help rename session":
            return "session_rename_help"
        if normalized_message == "list renameable sessions":
            return "session_rename_candidates"
        if (
            normalized_message == "check rename target"
            or normalized_message.startswith("check rename target ")
        ):
            return "session_rename_target_check"
        if normalized_message == "rename session" or normalized_message.startswith(
            "rename session "
        ):
            return "session_rename"
        if (
            normalized_message == "preview rename session"
            or normalized_message.startswith("preview rename session ")
        ):
            return "session_rename_preview"
        if (
            normalized_message == "preview delete session"
            or normalized_message.startswith("preview delete session ")
        ):
            return "session_delete_preview"
        if normalized_message == "delete session" or normalized_message.startswith(
            "delete session "
        ):
            return "session_delete"
        if normalized_message == "create session" or normalized_message.startswith(
            "create session "
        ):
            return "session_create"
        if normalized_message == "list sessions":
            return "session_list"
        if normalized_message == "use session" or normalized_message.startswith(
            "use session "
        ):
            return "session_use"
        words = set(request.message.casefold().split())
        return "greeting" if words.intersection(self._GREETING_WORDS) else "message"
