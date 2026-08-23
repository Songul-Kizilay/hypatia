"""Replaceable persistence boundary for authored research hypotheses."""

from typing import Protocol

from research.ResearchHypothesis import ResearchHypothesis


class HypothesisStore(Protocol):
    """Load and atomically replace the complete hypothesis set."""

    def load(self) -> list[ResearchHypothesis]:
        """Return every persisted hypothesis, or an empty list when absent."""

    def save(self, hypotheses: list[ResearchHypothesis]) -> None:
        """Atomically replace the persisted hypothesis set."""
