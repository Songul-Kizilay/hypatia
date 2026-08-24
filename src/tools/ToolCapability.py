"""The bounded set of things a tool can be asked to do.

Dispatch is a table lookup on one of these values, never a match against
authored text. That rule is inherited from research plan execution, where it
exists because instruction text arrives from places Hypatia does not control: a
fetched page, a model's output, a pasted message. A capability enum cannot be
talked into containing a new member, and text can be talked into anything.

The list is short on purpose. Every entry is a capability someone deliberately
added, reviewed, and gave an effect declaration to, and that cost is the point —
a tool layer that made adding capabilities cheap would accumulate them.
"""

from __future__ import annotations

from enum import StrEnum


class ToolCapability(StrEnum):
    """Name one bounded capability a registered tool can provide."""

    NONE = "none"
    CLOCK_READ = "clock_read"
    TEXT_STATISTICS = "text_statistics"
    RESEARCH_STATE_SUMMARY = "research_state_summary"
    KNOWLEDGE_DOCUMENT_LIST = "knowledge_document_list"

    @property
    def invocable(self) -> bool:
        """Return whether this capability can be registered and invoked.

        NONE exists so an absent capability is a value rather than a null that
        every caller has to remember to check.
        """
        return self is not ToolCapability.NONE
