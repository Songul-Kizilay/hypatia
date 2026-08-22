"""Immutable outcome of one canonical source-acceptance transaction.

``transaction_attempted`` and ``accepted`` are deliberately separate. A
transaction can genuinely run and still not accept a source, and the two must
never be collapsed into one flag.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchRun import ResearchRun

MAX_ACCEPTANCE_FAILURE_REASON_CHARACTERS = 500


@dataclass(frozen=True, slots=True)
class ResearchSourceAcceptanceResult:
    """Report exactly what the acceptance transaction did."""

    accepted: bool
    transaction_attempted: bool
    document_id: str | None = None
    run: ResearchRun | None = None
    failure_reason: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.accepted, bool):
            raise ResearchError("Source acceptance decision must be boolean.")
        if not isinstance(self.transaction_attempted, bool):
            raise ResearchError("Source acceptance attempt flag must be boolean.")
        if self.accepted and not self.transaction_attempted:
            raise ResearchError("An accepted source requires an attempted transaction.")
        if not isinstance(self.failure_reason, str):
            raise ResearchError("Source acceptance failure reason must be text.")
        reason = self.failure_reason.strip()
        if len(reason) > MAX_ACCEPTANCE_FAILURE_REASON_CHARACTERS:
            raise ResearchError("Source acceptance failure reason is too long.")
        if self.accepted and reason:
            raise ResearchError("An accepted source cannot carry a failure reason.")
        if not self.accepted and not reason:
            raise ResearchError("A rejected source requires a failure reason.")
        object.__setattr__(self, "failure_reason", reason)
