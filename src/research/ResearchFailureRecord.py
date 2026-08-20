"""Safe diagnostic retained for a failed research-run step."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.Exceptions import ResearchError


@dataclass(frozen=True, slots=True)
class ResearchFailureRecord:
    """Keep a bounded safe reason without persisting rejected input URLs."""

    stage: str
    reason: str
    occurred_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.stage, str) or not self.stage.strip():
            raise ResearchError("Research failure stage cannot be empty.")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ResearchError("Research failure reason cannot be empty.")
        if len(self.reason.strip()) > 500:
            raise ResearchError("Research failure reason is too long.")
        if (
            not isinstance(self.occurred_at, datetime)
            or self.occurred_at.utcoffset() is None
        ):
            raise ResearchError("Research failure time must be timezone-aware.")
        object.__setattr__(self, "stage", self.stage.strip())
        object.__setattr__(self, "reason", self.reason.strip())
