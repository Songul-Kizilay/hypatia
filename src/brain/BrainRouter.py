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
        words = set(request.message.casefold().split())
        return "greeting" if words.intersection(self._GREETING_WORDS) else "message"
