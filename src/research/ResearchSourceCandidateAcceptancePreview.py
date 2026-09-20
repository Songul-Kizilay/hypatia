"""Read-only decision for accepting one discovered research-source candidate."""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchSourceCandidate import ResearchSourceCandidate


@dataclass(frozen=True, slots=True)
class ResearchSourceCandidateAcceptancePreview:
    """Explain whether one persisted candidate may be explicitly accepted."""

    run_id: str
    discovery_id: str
    candidate: ResearchSourceCandidate
    allowed: bool
    reason: str
    #: The recorded identity of the previewed candidate, when its discovery
    #: recorded identities; carried into acceptance, never matched by URL.
    candidate_id: str | None = None

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.run_id, "Research candidate preview run ID"),
            (self.discovery_id, "Research candidate preview discovery ID"),
            (self.reason, "Research candidate preview reason"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ResearchError(f"{field_name} cannot be empty.")
        if not isinstance(self.candidate, ResearchSourceCandidate):
            raise ResearchError("Research candidate preview candidate is invalid.")
        if not isinstance(self.allowed, bool):
            raise ResearchError("Research candidate preview decision must be boolean.")
        object.__setattr__(self, "run_id", self.run_id.strip())
        object.__setattr__(self, "discovery_id", self.discovery_id.strip())
        object.__setattr__(self, "reason", self.reason.strip())
