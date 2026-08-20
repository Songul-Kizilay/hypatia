"""Lifecycle states for a persisted research run."""

from enum import StrEnum


class ResearchRunStatus(StrEnum):
    """Current bounded lifecycle for source-collection work."""

    COLLECTING = "collecting"
