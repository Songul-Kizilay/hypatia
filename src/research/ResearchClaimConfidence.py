"""Categorical confidence metadata for user-authored research claims."""

from __future__ import annotations

from enum import StrEnum


class ResearchClaimConfidence(StrEnum):
    """Avoid false numeric precision while keeping uncertainty explicit."""

    UNASSESSED = "unassessed"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
