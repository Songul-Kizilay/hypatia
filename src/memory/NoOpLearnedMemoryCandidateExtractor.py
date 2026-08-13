"""Learned-memory candidate extractor that never proposes candidates."""

from memory.LearnedMemoryCandidate import LearnedMemoryCandidateBatch


class NoOpLearnedMemoryCandidateExtractor:
    """Return an exact-source empty candidate batch."""

    def extract(
        self,
        source_text: str,
    ) -> LearnedMemoryCandidateBatch:
        """Return no candidates for the supplied source text."""
        return LearnedMemoryCandidateBatch(
            source_text=source_text,
            candidates=(),
        )
