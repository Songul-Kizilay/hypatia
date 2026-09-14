"""Replaceable persistence boundary for proposed curiosity questions."""

from typing import Protocol

from research.ResearchCuriosityQuestion import ResearchCuriosityQuestion


class CuriosityQuestionStore(Protocol):
    """Load and atomically replace the complete curiosity question set."""

    def load(self) -> list[ResearchCuriosityQuestion]:
        """Return every persisted question, or an empty list when absent."""

    def save(self, questions: list[ResearchCuriosityQuestion]) -> None:
        """Atomically replace the persisted question set."""
