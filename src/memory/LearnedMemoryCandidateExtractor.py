"""Typed boundary for learned-memory candidate extraction."""

from typing import Protocol

from memory.LearnedMemoryCandidate import LearnedMemoryCandidateBatch


class LearnedMemoryCandidateExtractor(Protocol):
    """Extract a candidate batch for exact supplied source text."""

    def extract(
        self,
        source_text: str,
        *,
        recent_session_context: str = "",
    ) -> LearnedMemoryCandidateBatch:
        """Return candidates for the supplied source text.

        ``recent_session_context`` is optional, bounded, same-session prior
        conversation offered only so an implementation can judge whether the
        user received a hint or answer before this turn. It is never itself
        a source a candidate can be extracted from.
        """
