"""What a tool is allowed to do, declared by the tool and checked before use.

This is the part of the tool layer that matters. A tool that says up front "I
read local state and nothing else" can be refused before it runs when the caller
only authorised reading; a tool that discovers its effects as it goes cannot be
refused at all, because by the time anyone knows what it did it has done it.

The effects are declared by the tool, never by the caller. A caller declaring
its own tool's effects would be marking its own homework, and the first tool to
quietly acquire a network call would be the one that stopped mentioning it.

The set is deliberately coarse. Fine-grained permissions look rigorous and end
up unreadable, and a permission nobody reads is a permission everybody grants.

One effect is not about the outside world at all. A tool that only transforms
data it was handed still declares COMPUTES_LOCALLY, because the alternative —
letting a pure tool declare nothing — would make the empty declaration mean both
"I touch nothing" and "nobody filled this in". An empty set is a subset of every
grant, so the unfilled declaration would become the one declaration no
authorisation could refuse, which is exactly backwards. Saying purity out loud
also keeps "authorise nothing" and "authorise pure computation" different
sentences; with an empty set they would be the same one.
"""

from __future__ import annotations

from enum import StrEnum


class ToolEffect(StrEnum):
    """Name one bounded thing a tool does, to the world or to its own input."""

    COMPUTES_LOCALLY = "computes_locally"
    READS_LOCAL_STATE = "reads_local_state"
    WRITES_LOCAL_STATE = "writes_local_state"
    READS_NETWORK = "reads_network"
    SPENDS_MODEL = "spends_model"

    @property
    def observable_outside(self) -> bool:
        """Return whether this effect is visible beyond this machine."""
        return self is ToolEffect.READS_NETWORK

    @property
    def irreversible(self) -> bool:
        """Return whether this effect can leave something changed behind.

        Reading is recoverable; writing and spending are not. The distinction
        exists so an authorisation can grant the recoverable half on its own.
        """
        return self in (ToolEffect.WRITES_LOCAL_STATE, ToolEffect.SPENDS_MODEL)


READ_ONLY_EFFECTS = frozenset({ToolEffect.READS_LOCAL_STATE})
