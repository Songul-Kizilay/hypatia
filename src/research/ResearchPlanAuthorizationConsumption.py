"""The one execution an approval was spent on.

An approval permits one attempt. Recording which attempt is what makes that
sentence checkable: without an execution identity the audit trail can only say
that permission was used at some point, which is exactly the claim nobody can
verify afterwards.

There is no way back from here. No reset, no refund, no renewal. An attempt
that failed, blocked, was cancelled, or died with the process still consumed
the approval, because the approval was for the attempt rather than for its
success — and an approval that came back after a failure would be an approval
that could be spent twice by failing once on purpose.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.Exceptions import ResearchError

MAX_CONSUMPTION_EXECUTION_ID_CHARACTERS = 200


@dataclass(frozen=True, slots=True)
class ResearchPlanAuthorizationConsumption:
    """Name the exact execution one approval was spent on, and when."""

    execution_id: str
    consumed_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.execution_id, str) or not self.execution_id.strip():
            raise ResearchError("A consumed approval must name its execution.")
        execution_id = self.execution_id.strip()
        if len(execution_id) > MAX_CONSUMPTION_EXECUTION_ID_CHARACTERS:
            raise ResearchError("A consumed approval execution ID is too long.")
        if (
            not isinstance(self.consumed_at, datetime)
            or self.consumed_at.tzinfo is None
        ):
            raise ResearchError("A consumption time must be timezone-aware.")
        object.__setattr__(self, "execution_id", execution_id)
