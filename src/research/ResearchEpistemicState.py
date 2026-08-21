"""Explicit epistemic states for user-authored research claims."""

from __future__ import annotations

from enum import StrEnum


class ResearchEpistemicState(StrEnum):
    """Describe what persisted evidence currently supports about one claim."""

    FACT = "fact"
    STRONG_EVIDENCE = "strong_evidence"
    LIKELY = "likely"
    HYPOTHESIS = "hypothesis"
    SPECULATION = "speculation"
    UNKNOWN = "unknown"
    CONTRADICTED = "contradicted"
