"""An exact program and target scope, not ownership or permission evidence."""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchTargetScope import ResearchTargetScope

MAX_TARGET_PROGRAM_ID_CHARACTERS = 200


@dataclass(frozen=True, slots=True)
class ResearchPlanTargetBinding:
    """Bind authored program identity to immutable target rules.

    This value grants no authority and records no confirmation or signature.
    The containing plan and its approval must establish execution permission.
    """

    program_id: str
    scope: ResearchTargetScope

    def __post_init__(self) -> None:
        if not isinstance(self.program_id, str) or not self.program_id.strip():
            raise ResearchError("Target program ID cannot be empty.")
        normalized = self.program_id.strip()
        if len(normalized) > MAX_TARGET_PROGRAM_ID_CHARACTERS:
            raise ResearchError("Target program ID is too long.")
        if not isinstance(self.scope, ResearchTargetScope):
            raise ResearchError("Target plan binding requires a validated scope.")
        object.__setattr__(self, "program_id", normalized)
