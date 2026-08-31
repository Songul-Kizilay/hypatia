"""One bounded record of what a person did about an unseen attempt.

Deliberately not a `ResearchEvidenceRecord`. That model is anchored to an
accepted source document and a chunk of it, and those anchors are what give it
its authority: the excerpt can be found again in something Hypatia fetched and
kept. A result an operator recovered by hand has none of that. Filing it there
would borrow provenance it does not have, and every consumer of evidence would
then read a person's account as a document Hypatia had verified.

So this is its own small thing, and it never stops saying who it came from.
`recorded_by` is the human who reported it. `claimed_operation` is only what
that person says produced it — carried as context, never as proof that the
provider said anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.Exceptions import ResearchError
from research.ResearchAttemptRecoveryDecision import ResearchAttemptRecoveryDecision
from research.ResearchAuthorizer import ResearchAuthorizer

MAX_RECOVERY_SUMMARY_CHARACTERS = 1000
MAX_CLAIMED_OPERATION_CHARACTERS = 120


@dataclass(frozen=True, slots=True)
class ResearchAttemptRecovery:
    """What one operator decided, when, and what they reported."""

    decision: ResearchAttemptRecoveryDecision
    recorded_at: datetime
    recorded_by: ResearchAuthorizer = ResearchAuthorizer.HUMAN
    #: What the operator reports having found. Their account, bounded, and never
    #: promoted to something the provider is held to have returned.
    summary: str = ""
    #: The operation the operator says produced it. Context for a reader, not a
    #: claim Hypatia makes, and never matched against the registry.
    claimed_operation: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.decision, ResearchAttemptRecoveryDecision):
            raise ResearchError("Attempt recovery decision is invalid.")
        if self.decision is ResearchAttemptRecoveryDecision.NONE:
            raise ResearchError("Attempt recovery needs an explicit decision.")
        if not isinstance(self.recorded_at, datetime):
            raise ResearchError("Attempt recovery must record when it was made.")
        if not isinstance(self.recorded_by, ResearchAuthorizer):
            raise ResearchError("Attempt recovery must record who made it.")
        for name, limit in (
            ("summary", MAX_RECOVERY_SUMMARY_CHARACTERS),
            ("claimed_operation", MAX_CLAIMED_OPERATION_CHARACTERS),
        ):
            value = getattr(self, name)
            if not isinstance(value, str):
                raise ResearchError(f"Attempt recovery {name} must be text.")
            stripped = value.strip()
            if len(stripped) > limit:
                raise ResearchError(f"Attempt recovery {name} is too long.")
            object.__setattr__(self, name, stripped)
        if (
            self.decision is ResearchAttemptRecoveryDecision.OPERATOR_SUPPLIED_RESULT
            and not self.summary
        ):
            raise ResearchError(
                "Supplying a recovered result needs the operator's account of it."
            )

    @property
    def human_supplied(self) -> bool:
        """Return whether a person, rather than a provider, is the source.

        Always true today, and asked rather than assumed so that no reader has
        to remember it. Nothing in this milestone can produce a recovery record
        that a provider vouched for.
        """
        return self.recorded_by is ResearchAuthorizer.HUMAN
