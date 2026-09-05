"""No-write view of one exact program-scope enrollment decision.

The immutable revision in this value is the record an explicit confirmation
would persist.  Keeping the complete value in the preview makes the operator's
decision content-addressed instead of relying on mutable form fields.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchProgramScopeRevision import ResearchProgramScopeRevision

PROGRAM_SCOPE_CREATE_ACTION = "create"
PROGRAM_SCOPE_REVOKE_ACTION = "revoke"
_ACTIONS = frozenset({PROGRAM_SCOPE_CREATE_ACTION, PROGRAM_SCOPE_REVOKE_ACTION})


@dataclass(frozen=True, slots=True)
class ResearchProgramScopeEnrollmentPreview:
    """Show the exact immutable revision awaiting human confirmation."""

    action: str
    revision: ResearchProgramScopeRevision

    def __post_init__(self) -> None:
        if self.action not in _ACTIONS:
            raise ResearchError("Program scope enrollment preview action is invalid.")
        if not isinstance(self.revision, ResearchProgramScopeRevision):
            raise ResearchError("Program scope enrollment preview requires a revision.")
        if self.action == PROGRAM_SCOPE_CREATE_ACTION and not self.revision.active:
            raise ResearchError("A scope creation preview must be active.")
        if self.action == PROGRAM_SCOPE_REVOKE_ACTION and self.revision.active:
            raise ResearchError("A scope revocation preview must be revoked.")

    @classmethod
    def create(
        cls, revision: ResearchProgramScopeRevision
    ) -> ResearchProgramScopeEnrollmentPreview:
        return cls(PROGRAM_SCOPE_CREATE_ACTION, revision)

    @classmethod
    def revoke(
        cls, revision: ResearchProgramScopeRevision
    ) -> ResearchProgramScopeEnrollmentPreview:
        return cls(PROGRAM_SCOPE_REVOKE_ACTION, revision)
