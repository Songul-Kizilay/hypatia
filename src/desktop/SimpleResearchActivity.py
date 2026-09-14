"""What Simple mode is doing right now, which is not what it has achieved.

This is a separate type from `SimpleResearchStep` on purpose, and the separation
is the safety property rather than a tidiness preference. A step is a fact read
back from persisted state. An activity is a request that has been sent and has
not returned. Putting them in one enum would let "loading source" sit in the
same sequence as "source accepted", and then a spinner would be one refactor
away from being treated as progress.

An activity therefore never advances a step, never survives a refresh, and never
appears in any exported or persisted form. It exists so a person is not looking
at a frozen window, and it disappears the moment canonical state is re-read —
whether or not the work succeeded.
"""

from __future__ import annotations

from enum import StrEnum


class SimpleResearchActivity(StrEnum):
    """Name one in-flight operation, which has achieved nothing yet."""

    IDLE = "idle"
    CREATING_QUESTION = "creating_question"
    FINDING_SOURCES = "finding_sources"
    LOADING_SOURCE = "loading_source"

    @property
    def in_flight(self) -> bool:
        """Return whether something is currently running."""
        return self is not SimpleResearchActivity.IDLE

    @property
    def reaches_network(self) -> bool:
        """Return whether this activity involves an outbound request.

        Creating a question does not. Simple mode shows this so the one moment
        Hypatia goes to the network is visible rather than implied.
        """
        return self in (
            SimpleResearchActivity.FINDING_SOURCES,
            SimpleResearchActivity.LOADING_SOURCE,
        )
