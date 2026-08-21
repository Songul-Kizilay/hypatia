"""User-authored information-trust labels for accepted research sources."""

from __future__ import annotations

from enum import StrEnum


class ResearchInformationTrust(StrEnum):
    """Describe authored confidence in source information without a numeric score."""

    UNASSESSED = "unassessed"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
