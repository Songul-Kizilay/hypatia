"""Lifecycle of one proposed curiosity question.

A proposed question is a suggestion for a human, never a scheduled action.
Accepting one records that the question is worth pursuing; it starts no
research, creates no plan, and queues no background task.
"""

from __future__ import annotations

from enum import StrEnum


class CuriosityQuestionStatus(StrEnum):
    """Bounded states a curiosity question can occupy."""

    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    DISMISSED = "dismissed"

    @property
    def decided(self) -> bool:
        """Return whether a human already ruled on this question."""
        return self is not CuriosityQuestionStatus.PROPOSED
