"""Typed boundary for learned-memory candidate extraction."""

from typing import Protocol

from memory.LearnedMemoryCandidate import LearnedMemoryCandidateBatch


class LearnedMemoryCandidateExtractor(Protocol):
    """Extract a candidate batch for exact supplied source text."""

    def extract(
        self,
        source_text: str,
    ) -> LearnedMemoryCandidateBatch:
        """Return candidates for the supplied source text."""
