"""Explicit typed execution capability authorized for one plan step.

Capability identity is deliberately separate from the authored instruction
text. A step never gains an executable capability by what its instruction
happens to say; the capability must be declared explicitly, and an
unauthorized step blocks instead of guessing an operation.
"""

from enum import StrEnum


class ResearchPlanStepCapability(StrEnum):
    """Bounded set of capabilities a plan step may be authorized to run."""

    NONE = "none"
    LOCAL_KNOWLEDGE_SEARCH = "local_knowledge_search"
    ACCEPTED_SOURCE_LISTING = "accepted_source_listing"

    @property
    def executable(self) -> bool:
        """Return whether this capability authorizes any real operation."""
        return self is not ResearchPlanStepCapability.NONE
