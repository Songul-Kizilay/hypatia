"""One thing the security agent found in Hypatia's own records.

A finding names the record it is about and says what is wrong with it. It never
names an external system, because the agent never looks at one, and the type
gives it nowhere to put such a name if it did.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from security.SecurityFindingKind import SecurityFindingKind, SecurityFindingSeverity

MAX_FINDING_DETAIL_LENGTH = 300


@dataclass(frozen=True, slots=True)
class SecurityFinding:
    """Record one bounded problem found in this system's own state."""

    kind: SecurityFindingKind
    run_id: str
    subject_id: str
    detail: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, SecurityFindingKind):
            raise ResearchError("Security finding kind must be a bounded category.")
        for value, label in (
            (self.run_id, "run ID"),
            (self.subject_id, "subject ID"),
            (self.detail, "detail"),
        ):
            if not value.strip():
                raise ResearchError(f"Security finding {label} cannot be empty.")
        if len(self.detail) > MAX_FINDING_DETAIL_LENGTH:
            raise ResearchError("Security finding detail is too long.")

    @property
    def severity(self) -> SecurityFindingSeverity:
        """Return the declared severity of this finding's kind."""
        return self.kind.severity

    @property
    def needs_action(self) -> bool:
        """Return whether someone should look at this before moving on."""
        return self.severity.needs_action
