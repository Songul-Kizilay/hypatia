"""Replaceable persistence boundary for remembered failure lessons."""

from typing import Protocol

from research.ResearchFailureLesson import ResearchFailureLesson


class FailureLessonStore(Protocol):
    """Load and atomically replace the complete failure lesson set."""

    def load(self) -> list[ResearchFailureLesson]:
        """Return every persisted lesson, or an empty list when absent."""

    def save(self, lessons: list[ResearchFailureLesson]) -> None:
        """Atomically replace the persisted lesson set."""
