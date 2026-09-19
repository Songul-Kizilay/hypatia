"""What two recorded observations prove about their stored content versions."""

from enum import StrEnum


class ResearchSourceRevalidationOutcome(StrEnum):
    """Bounded equality result for one intentionally recorded observation pair."""

    CONTENT_UNCHANGED = "content_unchanged"
    CONTENT_CHANGED = "content_changed"
