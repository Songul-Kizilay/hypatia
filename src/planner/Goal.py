from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from core.Exceptions import PlannerError


@dataclass(slots=True)
class Goal:
    """Represents a user goal that can be transformed into a plan."""

    description: str
    goal_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self.description = self.description.strip()

        if not self.description:
            raise PlannerError("Goal description cannot be empty.")
