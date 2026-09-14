"""How consistently our own assessments have treated one origin.

Every value here is a statement about the pattern in our judgements, not about
the publisher. CONSISTENTLY_LOW means we have repeatedly assessed sources from
that host as low trust; it does not mean the host is bad, and it must never
decide anything on its own.

PROVISIONAL exists because reputation is where a system quietly builds
prejudice. Two bad experiences is a coincidence, and calling it a reputation
would let one unlucky pair of pages permanently colour how everything from that
host is read. Below the threshold the standing says so out loud.
"""

from __future__ import annotations

from enum import StrEnum

MIN_ASSESSMENTS_FOR_STANDING = 3


class SourceStanding(StrEnum):
    """Name one bounded pattern in our assessments of an origin."""

    UNKNOWN = "unknown"
    PROVISIONAL = "provisional"
    MIXED = "mixed"
    CONSISTENTLY_LOW = "consistently_low"
    CONSISTENTLY_TRUSTED = "consistently_trusted"

    @property
    def established(self) -> bool:
        """Return whether enough assessments exist to call this a pattern."""
        return self in (
            SourceStanding.MIXED,
            SourceStanding.CONSISTENTLY_LOW,
            SourceStanding.CONSISTENTLY_TRUSTED,
        )

    @property
    def decides_anything(self) -> bool:
        """Return whether this standing gates any operation. It never does.

        Kept as an explicit property so the answer is asserted in a test rather
        than merely intended in a comment.
        """
        return False
