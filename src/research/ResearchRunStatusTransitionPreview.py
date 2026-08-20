"""Read-only decision for one requested research-run status transition."""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchRunStatus import ResearchRunStatus


@dataclass(frozen=True, slots=True)
class ResearchRunStatusTransitionPreview:
    """Explain whether a terminal status transition is currently allowed."""

    run_id: str
    current_status: ResearchRunStatus
    target_status: ResearchRunStatus
    allowed: bool
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, str) or not self.run_id.strip():
            raise ResearchError("Research status preview run ID cannot be empty.")
        if not isinstance(self.current_status, ResearchRunStatus):
            raise ResearchError("Research status preview current status is invalid.")
        if not isinstance(self.target_status, ResearchRunStatus):
            raise ResearchError("Research status preview target status is invalid.")
        if not isinstance(self.allowed, bool):
            raise ResearchError("Research status preview decision must be boolean.")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ResearchError("Research status preview reason cannot be empty.")
        object.__setattr__(self, "run_id", self.run_id.strip())
        object.__setattr__(self, "reason", self.reason.strip())
