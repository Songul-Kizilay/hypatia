"""Read-only persisted research-claim history."""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchClaimRecord import ResearchClaimRecord
from research.ResearchRunStatus import ResearchRunStatus


@dataclass(frozen=True, slots=True)
class ResearchClaimPreview:
    """Expose claim audit history without live inference or mutation."""

    run_id: str
    question: str
    run_status: ResearchRunStatus
    claims: tuple[ResearchClaimRecord, ...]
    reason: str

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.run_id, "Research claim preview run ID"),
            (self.question, "Research claim preview question"),
            (self.reason, "Research claim preview reason"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ResearchError(f"{field_name} cannot be empty.")
        if not isinstance(self.run_status, ResearchRunStatus):
            raise ResearchError("Research claim preview run status is invalid.")
        if not isinstance(self.claims, tuple) or not all(
            isinstance(record, ResearchClaimRecord) for record in self.claims
        ):
            raise ResearchError("Research claim preview history is invalid.")
        object.__setattr__(self, "run_id", self.run_id.strip())
        object.__setattr__(self, "question", self.question.strip())
        object.__setattr__(self, "reason", self.reason.strip())
