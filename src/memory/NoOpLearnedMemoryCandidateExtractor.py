"""Learned-memory candidate extractor that never proposes candidates."""

from memory.LearnedMemoryCandidate import LearnedMemoryCandidateBatch


class NoOpLearnedMemoryCandidateExtractor:
    """Return an exact-source empty candidate batch."""

    def extract(
        self,
        source_text: str,
        *,
        recent_session_context: str = "",
    ) -> LearnedMemoryCandidateBatch:
        """Return no candidates for the supplied source text."""
        del recent_session_context
        return LearnedMemoryCandidateBatch(
            source_text=source_text,
            candidates=(),
        )
