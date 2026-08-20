"""Bounded read-only result of accepted research content restoration."""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError


@dataclass(frozen=True, slots=True)
class ResearchSourceContentRestorationStatus:
    """Expose only aggregate startup restoration health and counts."""

    available: bool
    restored_document_count: int
    restored_paragraph_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.available, bool):
            raise ResearchError("Research content restoration availability is invalid.")
        for value, label in (
            (self.restored_document_count, "document count"),
            (self.restored_paragraph_count, "paragraph count"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ResearchError(f"Research content restoration {label} is invalid.")
        if not self.available and (
            self.restored_document_count != 0 or self.restored_paragraph_count != 0
        ):
            raise ResearchError(
                "Unavailable research content restoration cannot report counts."
            )

    @property
    def state(self) -> str:
        """Return the safe user-facing runtime state."""
        return "ready" if self.available else "unavailable"

    @classmethod
    def unavailable(cls) -> ResearchSourceContentRestorationStatus:
        """Create the bounded state used when no restoration result is wired."""
        return cls(False, 0, 0)
